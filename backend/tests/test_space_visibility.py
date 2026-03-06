"""Tests for space visibility (private/shared) filtering and ownership enforcement."""

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import _sign
from src.models.tables import GitHubAccount, Space, TrackedRepo, User
from src.services.discovery import _upsert_space


def _auth_cookie(user_id: int) -> dict:
    """Return cookies dict that injects a signed github_user identity cookie."""
    expires = int(time.time()) + 3600
    payload = f"{user_id}:{expires}"
    return {"cookies": {"github_user": _sign(payload)}}


async def _make_user(session: AsyncSession, github_id: int, login: str) -> User:
    user = User(github_id=github_id, login=login, name=login)
    session.add(user)
    await session.flush()
    return user


async def _make_account(session: AsyncSession, user: User) -> GitHubAccount:
    account = GitHubAccount(
        user_id=user.id,
        github_id=user.github_id,
        login=user.login,
        encrypted_token="fake-encrypted",
        base_url="https://api.github.com",
    )
    session.add(account)
    await session.flush()
    return account


async def _make_space(
    session: AsyncSession,
    name: str,
    slug: str,
    user_id: int,
    account_id: int,
    visibility: str = "private",
    space_type: str = "org",
) -> Space:
    space = Space(
        name=name,
        slug=slug,
        space_type=space_type,
        github_account_id=account_id,
        user_id=user_id,
        visibility=visibility,
        is_active=True,
    )
    session.add(space)
    await session.flush()
    return space


# ── A. Visibility filtering — GET /api/spaces ──────────────────


@pytest.mark.asyncio
async def test_user_sees_own_private_and_shared_spaces(client, db_session: AsyncSession):
    """User A sees own private spaces + all shared spaces."""
    user_a = await _make_user(db_session, 100, "alice")
    user_b = await _make_user(db_session, 200, "bob")
    acct_a = await _make_account(db_session, user_a)
    acct_b = await _make_account(db_session, user_b)

    await _make_space(db_session, "A-priv1", "a-priv1", user_a.id, acct_a.id, "private")
    await _make_space(db_session, "A-priv2", "a-priv2", user_a.id, acct_a.id, "private")
    await _make_space(db_session, "B-shared", "b-shared", user_b.id, acct_b.id, "shared")
    await db_session.commit()

    resp = await client.get("/api/spaces", **_auth_cookie(user_a.id))
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert names == {"A-priv1", "A-priv2", "B-shared"}


@pytest.mark.asyncio
async def test_user_cannot_see_other_private_spaces(client, db_session: AsyncSession):
    """User B does NOT see User A's private spaces."""
    user_a = await _make_user(db_session, 101, "alice2")
    user_b = await _make_user(db_session, 201, "bob2")
    acct_a = await _make_account(db_session, user_a)

    await _make_space(db_session, "A-secret", "a-secret", user_a.id, acct_a.id, "private")
    await db_session.commit()

    resp = await client.get("/api/spaces", **_auth_cookie(user_b.id))
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert "A-secret" not in names


@pytest.mark.asyncio
async def test_anonymous_sees_only_shared_spaces(client, db_session: AsyncSession):
    """No cookie → only shared spaces returned."""
    user = await _make_user(db_session, 102, "alice3")
    acct = await _make_account(db_session, user)

    await _make_space(db_session, "priv", "priv", user.id, acct.id, "private")
    await _make_space(db_session, "pub", "pub", user.id, acct.id, "shared")
    await db_session.commit()

    resp = await client.get("/api/spaces")  # no cookie
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert "pub" in names
    assert "priv" not in names


@pytest.mark.asyncio
async def test_new_spaces_default_to_private(db_session: AsyncSession):
    """Spaces created via _upsert_space default to 'private'."""
    user = await _make_user(db_session, 103, "alice4")
    acct = await _make_account(db_session, user)

    space = await _upsert_space(
        db_session,
        account_id=acct.id,
        user_id=user.id,
        slug="new-org",
        name="New Org",
        space_type="org",
    )
    await db_session.flush()
    assert space.visibility == "private"


# ── B. Visibility filtering — GET /api/repos ──────────────────


@pytest.mark.asyncio
async def test_repos_in_private_space_hidden_from_others(client, db_session: AsyncSession):
    """Repos in User A's private space are hidden from User B."""
    user_a = await _make_user(db_session, 110, "alice-r1")
    user_b = await _make_user(db_session, 210, "bob-r1")
    acct_a = await _make_account(db_session, user_a)

    space = await _make_space(db_session, "A-priv", "a-priv-r", user_a.id, acct_a.id, "private")
    repo = TrackedRepo(
        owner="a-priv-r", name="repo1", full_name="a-priv-r/repo1",
        default_branch="main", space_id=space.id,
    )
    db_session.add(repo)
    await db_session.commit()

    resp = await client.get("/api/repos", **_auth_cookie(user_b.id))
    assert resp.status_code == 200
    names = {r["full_name"] for r in resp.json()}
    assert "a-priv-r/repo1" not in names


@pytest.mark.asyncio
async def test_repos_in_shared_space_visible_to_all(client, db_session: AsyncSession):
    """Repos in a shared space are visible to everyone."""
    user_a = await _make_user(db_session, 111, "alice-r2")
    user_b = await _make_user(db_session, 211, "bob-r2")
    acct_a = await _make_account(db_session, user_a)

    space = await _make_space(db_session, "A-shared", "a-shared-r", user_a.id, acct_a.id, "shared")
    repo = TrackedRepo(
        owner="a-shared-r", name="repo2", full_name="a-shared-r/repo2",
        default_branch="main", space_id=space.id,
    )
    db_session.add(repo)
    await db_session.commit()

    resp = await client.get("/api/repos", **_auth_cookie(user_b.id))
    assert resp.status_code == 200
    names = {r["full_name"] for r in resp.json()}
    assert "a-shared-r/repo2" in names


@pytest.mark.asyncio
async def test_repos_without_space_always_visible(client, db_session: AsyncSession):
    """Repos with space_id=NULL appear for everyone."""
    repo = TrackedRepo(
        owner="orphan", name="repo3", full_name="orphan/repo3",
        default_branch="main", space_id=None,
    )
    db_session.add(repo)
    await db_session.commit()

    # Check as anonymous
    resp = await client.get("/api/repos")
    assert resp.status_code == 200
    names = {r["full_name"] for r in resp.json()}
    assert "orphan/repo3" in names


@pytest.mark.asyncio
async def test_anonymous_repos_only_shared_spaces(client, db_session: AsyncSession):
    """Anonymous sees repos from shared spaces only (+ orphan repos)."""
    user = await _make_user(db_session, 112, "alice-r4")
    acct = await _make_account(db_session, user)

    priv_space = await _make_space(db_session, "priv-s", "priv-sr", user.id, acct.id, "private")
    shared_space = await _make_space(db_session, "shared-s", "shared-sr", user.id, acct.id, "shared")

    db_session.add(TrackedRepo(
        owner="priv-sr", name="r1", full_name="priv-sr/r1",
        default_branch="main", space_id=priv_space.id,
    ))
    db_session.add(TrackedRepo(
        owner="shared-sr", name="r2", full_name="shared-sr/r2",
        default_branch="main", space_id=shared_space.id,
    ))
    await db_session.commit()

    resp = await client.get("/api/repos")  # no cookie
    assert resp.status_code == 200
    names = {r["full_name"] for r in resp.json()}
    assert "shared-sr/r2" in names
    assert "priv-sr/r1" not in names


# ── C. Ownership enforcement — PATCH /api/spaces/{id}/visibility ──


@pytest.mark.asyncio
async def test_owner_can_change_visibility(client, db_session: AsyncSession):
    """Owner can switch visibility to shared."""
    user = await _make_user(db_session, 120, "owner1")
    acct = await _make_account(db_session, user)
    space = await _make_space(db_session, "my-org", "my-org", user.id, acct.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/visibility",
        json={"visibility": "shared"},
        **_auth_cookie(user.id),
    )
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "shared"


@pytest.mark.asyncio
async def test_non_owner_gets_403(client, db_session: AsyncSession):
    """Non-owner cannot change visibility."""
    user_a = await _make_user(db_session, 121, "owner2")
    user_b = await _make_user(db_session, 221, "intruder")
    acct_a = await _make_account(db_session, user_a)
    space = await _make_space(db_session, "owned", "owned", user_a.id, acct_a.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/visibility",
        json={"visibility": "shared"},
        **_auth_cookie(user_b.id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_visibility_change_gets_401(client, db_session: AsyncSession):
    """No cookie → 401."""
    user = await _make_user(db_session, 122, "owner3")
    acct = await _make_account(db_session, user)
    space = await _make_space(db_session, "no-auth", "no-auth", user.id, acct.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/visibility",
        json={"visibility": "shared"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_visibility_value_rejected(client, db_session: AsyncSession):
    """Invalid visibility value → 400."""
    user = await _make_user(db_session, 123, "owner4")
    acct = await _make_account(db_session, user)
    space = await _make_space(db_session, "bad-vis", "bad-vis", user.id, acct.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/visibility",
        json={"visibility": "public"},
        **_auth_cookie(user.id),
    )
    assert resp.status_code == 400


# ── D. Security / penetration scenarios ──────────────────


@pytest.mark.asyncio
async def test_forged_cookie_treated_as_anonymous(client, db_session: AsyncSession):
    """Tampered HMAC cookie → treated as anonymous (only shared spaces)."""
    user = await _make_user(db_session, 130, "victim")
    acct = await _make_account(db_session, user)
    await _make_space(db_session, "secret", "secret", user.id, acct.id, "private")
    await db_session.commit()

    # Forge a cookie with invalid HMAC
    forged = f"{user.id}:{int(time.time()) + 3600}.forgedsignature"
    resp = await client.get(
        "/api/spaces",
        cookies={"github_user": forged},
    )
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert "secret" not in names


@pytest.mark.asyncio
async def test_expired_cookie_treated_as_anonymous(client, db_session: AsyncSession):
    """Signed cookie with past timestamp → anonymous."""
    user = await _make_user(db_session, 131, "expired-user")
    acct = await _make_account(db_session, user)
    await _make_space(db_session, "hidden", "hidden", user.id, acct.id, "private")
    await db_session.commit()

    # Sign a cookie that expired 1 hour ago
    expired_ts = int(time.time()) - 3600
    payload = f"{user.id}:{expired_ts}"
    expired_cookie = _sign(payload)

    resp = await client.get(
        "/api/spaces",
        cookies={"github_user": expired_cookie},
    )
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert "hidden" not in names


@pytest.mark.asyncio
async def test_sql_injection_via_visibility_field(client, db_session: AsyncSession):
    """SQL injection attempt in visibility value → 400."""
    user = await _make_user(db_session, 132, "sqli-user")
    acct = await _make_account(db_session, user)
    space = await _make_space(db_session, "sqli", "sqli", user.id, acct.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/visibility",
        json={"visibility": "shared' OR 1=1--"},
        **_auth_cookie(user.id),
    )
    assert resp.status_code == 400


# ── E. Discovery integration ──────────────────────────────


@pytest.mark.asyncio
async def test_upsert_space_sets_user_id(db_session: AsyncSession):
    """_upsert_space sets user_id on new spaces."""
    user = await _make_user(db_session, 140, "disco1")
    acct = await _make_account(db_session, user)

    space = await _upsert_space(
        db_session,
        account_id=acct.id,
        user_id=user.id,
        slug="disco-org",
        name="Disco Org",
        space_type="org",
    )
    await db_session.flush()
    assert space.user_id == user.id


@pytest.mark.asyncio
async def test_upsert_space_backfills_user_id(db_session: AsyncSession):
    """_upsert_space backfills user_id on existing space if null."""
    user = await _make_user(db_session, 141, "disco2")
    acct = await _make_account(db_session, user)

    # Create space with user_id=None directly
    space = Space(
        name="Orphan",
        slug="orphan-org",
        space_type="org",
        github_account_id=acct.id,
        user_id=None,
        is_active=False,
    )
    db_session.add(space)
    await db_session.flush()
    assert space.user_id is None

    # Now call _upsert_space which should backfill
    updated = await _upsert_space(
        db_session,
        account_id=acct.id,
        user_id=user.id,
        slug="orphan-org",
        name="Orphan Updated",
        space_type="org",
    )
    await db_session.flush()
    assert updated.user_id == user.id


# ── F. Toggle ownership check ──────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_toggle_own_private_space(client, db_session: AsyncSession):
    """Owner can toggle their own private space."""
    user = await _make_user(db_session, 150, "toggler1")
    acct = await _make_account(db_session, user)
    space = await _make_space(db_session, "my-toggle", "my-toggle", user.id, acct.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/toggle",
        json={"is_active": False},
        **_auth_cookie(user.id),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_non_owner_cannot_toggle_private_space(client, db_session: AsyncSession):
    """Non-owner cannot toggle another user's private space."""
    user_a = await _make_user(db_session, 151, "toggler2")
    user_b = await _make_user(db_session, 251, "intruder2")
    acct_a = await _make_account(db_session, user_a)
    space = await _make_space(db_session, "a-toggle", "a-toggle", user_a.id, acct_a.id, "private")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/toggle",
        json={"is_active": False},
        **_auth_cookie(user_b.id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_anyone_can_toggle_shared_space(client, db_session: AsyncSession):
    """Any authenticated user can toggle a shared space."""
    user_a = await _make_user(db_session, 152, "toggler3")
    user_b = await _make_user(db_session, 252, "friend")
    acct_a = await _make_account(db_session, user_a)
    space = await _make_space(db_session, "shared-toggle", "shared-toggle", user_a.id, acct_a.id, "shared")
    await db_session.commit()

    resp = await client.patch(
        f"/api/spaces/{space.id}/toggle",
        json={"is_active": False},
        **_auth_cookie(user_b.id),
    )
    assert resp.status_code == 200
