"""Tests for the repos API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import GitHubAccount, PullRequest, Space, TrackedRepo, User
from src.services.crypto import encrypt_token


@pytest_asyncio.fixture
async def space_with_account(db_session: AsyncSession):
    """Create a user, GitHub account, and space for repo tests."""
    user = User(github_id=1, login="testuser", name="Test User")
    db_session.add(user)
    await db_session.flush()

    account = GitHubAccount(
        user_id=user.id,
        github_id=1,
        login="testuser",
        encrypted_token=encrypt_token("fake-token"),
        base_url="https://api.github.com",
    )
    db_session.add(account)
    await db_session.flush()

    space = Space(
        slug="org",
        name="org",
        space_type="org",
        github_account_id=account.id,
        user_id=user.id,
        is_active=True,
    )
    db_session.add(space)
    await db_session.commit()

    return {"user": user, "account": account, "space": space}


@pytest.mark.asyncio
async def test_list_repos_empty(client):
    resp = await client.get("/api/repos")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_repo(client, space_with_account):
    """POST /api/repos should create a tracked repo (mocking GitHub)."""
    space = space_with_account["space"]
    mock_gh_repo = {"default_branch": "main", "full_name": "org/repo"}

    with (
        patch(
            "src.api.repos.GitHubClient.get_repo",
            new_callable=AsyncMock,
            return_value=mock_gh_repo,
        ),
        patch(
            "src.api.repos.GitHubClient.close",
            new_callable=AsyncMock,
        ),
    ):
        resp = await client.post(
            "/api/repos",
            json={"owner": "org", "name": "repo", "space_id": space.id},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "org/repo"
    assert data["is_active"] is True
    assert data["default_branch"] == "main"


@pytest.mark.asyncio
async def test_add_duplicate_repo(client, space_with_account):
    """Adding the same repo twice should return 409."""
    space = space_with_account["space"]
    mock_gh_repo = {"default_branch": "main", "full_name": "dup/repo"}

    with (
        patch(
            "src.api.repos.GitHubClient.get_repo",
            new_callable=AsyncMock,
            return_value=mock_gh_repo,
        ),
        patch(
            "src.api.repos.GitHubClient.close",
            new_callable=AsyncMock,
        ),
    ):
        resp1 = await client.post(
            "/api/repos",
            json={"owner": "dup", "name": "repo", "space_id": space.id},
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/repos",
            json={"owner": "dup", "name": "repo", "space_id": space.id},
        )
        assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_repos_with_stats(client, db_session: AsyncSession):
    """Repos should include open_pr_count and other stats."""
    repo = TrackedRepo(
        owner="stats",
        name="repo",
        full_name="stats/repo",
        default_branch="main",
        visibility="shared",
    )
    db_session.add(repo)
    await db_session.flush()

    now = datetime.now(UTC)
    db_session.add(
        PullRequest(
            repo_id=repo.id,
            number=1,
            title="Open PR",
            state="open",
            draft=False,
            head_ref="feature",
            base_ref="main",
            author="dev",
            additions=5,
            deletions=3,
            changed_files=1,
            html_url="https://github.com/stats/repo/pull/1",
            created_at=now,
            updated_at=now,
            last_synced_at=now,
        )
    )
    await db_session.commit()

    resp = await client.get("/api/repos")
    assert resp.status_code == 200
    repos = resp.json()
    assert len(repos) == 1
    assert repos[0]["open_pr_count"] == 1


@pytest.mark.asyncio
async def test_delete_repo_soft_deletes(client, db_session: AsyncSession):
    """DELETE should soft-delete (set is_active=False)."""
    repo = TrackedRepo(owner="del", name="repo", full_name="del/repo", default_branch="main")
    db_session.add(repo)
    await db_session.commit()

    resp = await client.delete(f"/api/repos/{repo.id}")
    assert resp.status_code == 204

    await db_session.refresh(repo)
    assert repo.is_active is False


@pytest.mark.asyncio
async def test_delete_nonexistent_repo(client):
    resp = await client.delete("/api/repos/99999")
    assert resp.status_code == 404
