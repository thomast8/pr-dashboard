"""Tests for OAuth duplicate user prevention.

When a GitHub identity is already linked as a GitHubAccount under an existing user,
OAuth sign-in with that identity should sign in as the existing user, not create a new one.
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.api.auth import _sign, github_oauth_callback
from src.models.tables import GitHubAccount, User
from src.services.crypto import encrypt_token

# Shared GitHub user templates
PERSONAL_GH = {"id": 1000, "login": "primary-user", "name": "Primary User", "avatar_url": None}
KYNDRYL_GH = {"id": 2000, "login": "linked-kyndryl", "name": "Kyndryl User", "avatar_url": None}
NEW_GH = {"id": 9999, "login": "brand-new-user", "name": "New User", "avatar_url": None}


def _make_oauth_state(mode: str = "oauth") -> str:
    """Build a valid signed OAuth state parameter."""
    payload = f"{mode}:{int(time.time())}:testnonce"
    return _sign(payload)


def _fake_request(user_id: int | None = None):
    """Build a fake Request with optional github_user cookie."""
    req = MagicMock()
    if user_id is not None:
        expires = int(time.time()) + 86400
        cookie_payload = f"{user_id}:{expires}"
        token = _sign(cookie_payload)
        req.cookies = {"github_user": token}
    else:
        req.cookies = {}
    return req


def _mock_httpx_client(gh_user: dict):
    """Patch httpx.AsyncClient to return fake GitHub token + user responses."""

    async def fake_post(*args, **kwargs):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"access_token": "gho_fake_token"}
        return resp

    async def fake_get(*args, **kwargs):
        resp = MagicMock(status_code=200)
        resp.json.return_value = gh_user
        return resp

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest_asyncio.fixture
async def seeded_session(async_engine):
    """Seed a User with primary github_id=1000 and a linked GitHubAccount with github_id=2000."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            github_id=1000,
            login="primary-user",
            name="Primary User",
            avatar_url="https://example.com/primary.png",
            last_login_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()

        linked_account = GitHubAccount(
            user_id=user.id,
            github_id=2000,
            login="linked-kyndryl",
            avatar_url="https://example.com/kyndryl.png",
            encrypted_token=encrypt_token("old_token"),
            base_url="https://api.github.com",
            last_login_at=datetime.now(UTC),
        )
        session.add(linked_account)
        await session.commit()
        yield factory


async def _call_oauth_callback(session_factory, gh_user: dict, request=None):
    """Call the OAuth callback directly with mocked dependencies."""
    if request is None:
        request = _fake_request()

    state = _make_oauth_state("oauth")
    mock_client = _mock_httpx_client(gh_user)

    with (
        patch("src.api.auth.async_session_factory", session_factory),
        patch("src.api.auth.httpx.AsyncClient", return_value=mock_client),
        patch("src.api.auth._discover_spaces_background", new_callable=AsyncMock),
    ):
        response = await github_oauth_callback(code="test_code", state=state, request=request)

    return response


class TestOAuthDuplicatePrevention:
    @pytest.mark.asyncio
    async def test_oauth_signin_with_linked_account_reuses_user(self, seeded_session):
        """OAuth sign-in with a github_id that exists only as a GitHubAccount
        should sign in as the owning user, not create a duplicate."""
        resp = await _call_oauth_callback(seeded_session, KYNDRYL_GH)
        assert resp.status_code == 307

        async with seeded_session() as session:
            users = (await session.execute(select(User))).scalars().all()
            assert len(users) == 1, f"Expected 1 user, got {len(users)}: {[u.login for u in users]}"
            assert users[0].github_id == 1000  # Primary identity unchanged

    @pytest.mark.asyncio
    async def test_oauth_signin_with_primary_id_works_normally(self, seeded_session):
        """OAuth sign-in with the user's primary github_id should work as before."""
        resp = await _call_oauth_callback(seeded_session, PERSONAL_GH)
        assert resp.status_code == 307

        async with seeded_session() as session:
            users = (await session.execute(select(User))).scalars().all()
            assert len(users) == 1

    @pytest.mark.asyncio
    async def test_oauth_truly_new_user_creates_account(self, seeded_session):
        """OAuth sign-in with an unknown github_id should create a new user."""
        resp = await _call_oauth_callback(seeded_session, NEW_GH)
        assert resp.status_code == 307

        async with seeded_session() as session:
            users = (await session.execute(select(User))).scalars().all()
            assert len(users) == 2, f"Expected 2 users, got {len(users)}"
            logins = {u.login for u in users}
            assert "brand-new-user" in logins
            assert "primary-user" in logins

    @pytest.mark.asyncio
    async def test_auto_link_mode_with_existing_session(self, seeded_session):
        """When user already has a session cookie, OAuth should auto-upgrade to link mode."""
        # Get the seeded user's ID
        async with seeded_session() as session:
            user = (await session.execute(select(User))).scalar_one()
            user_id = user.id

        # OAuth with a new identity while already logged in
        request = _fake_request(user_id=user_id)
        new_identity = {"id": 3000, "login": "third-account", "name": "Third", "avatar_url": None}
        resp = await _call_oauth_callback(seeded_session, new_identity, request=request)
        assert resp.status_code == 307

        async with seeded_session() as session:
            # Should still be 1 user (linked, not created new)
            users = (await session.execute(select(User))).scalars().all()
            assert len(users) == 1

            # The new identity should be linked as a GitHubAccount
            accounts = (await session.execute(select(GitHubAccount))).scalars().all()
            gh_ids = {a.github_id for a in accounts}
            assert 3000 in gh_ids
            assert all(a.user_id == user_id for a in accounts)

    @pytest.mark.asyncio
    async def test_multiple_accounts_with_same_github_id(self, async_engine):
        """When multiple GitHubAccount rows share the same github_id (linked to
        different users), the lookup should not crash."""
        factory = async_sessionmaker(async_engine, expire_on_commit=False)
        async with factory() as session:
            user_a = User(github_id=5000, login="user-a", name="A", last_login_at=datetime.now(UTC))
            user_b = User(github_id=5001, login="user-b", name="B", last_login_at=datetime.now(UTC))
            session.add_all([user_a, user_b])
            await session.flush()

            # Both users have a GitHubAccount with github_id=6000
            for user in (user_a, user_b):
                session.add(
                    GitHubAccount(
                        user_id=user.id,
                        github_id=6000,
                        login="shared-identity",
                        encrypted_token=encrypt_token("tok"),
                        base_url="https://api.github.com",
                        last_login_at=datetime.now(UTC),
                    )
                )
            await session.commit()

        gh_user = {"id": 6000, "login": "shared-identity", "name": "Shared", "avatar_url": None}
        resp = await _call_oauth_callback(factory, gh_user)
        # Should not crash with MultipleResultsFound
        assert resp.status_code == 307

        async with factory() as session:
            users = (await session.execute(select(User))).scalars().all()
            # No new user created; signed in as one of the existing ones
            assert len(users) == 2
