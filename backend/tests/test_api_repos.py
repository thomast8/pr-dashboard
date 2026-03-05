"""Tests for the repos API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import PullRequest, TrackedRepo


@pytest.mark.asyncio
async def test_list_repos_empty(client):
    resp = await client.get("/api/repos")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_repo(client):
    """POST /api/repos should create a tracked repo (mocking GitHub)."""
    mock_gh_repo = {"default_branch": "main", "full_name": "org/repo"}

    with patch(
        "src.api.repos.GitHubClient.get_repo",
        new_callable=AsyncMock,
        return_value=mock_gh_repo,
    ), patch(
        "src.api.repos.GitHubClient.close",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            "/api/repos", json={"owner": "org", "name": "repo"}
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "org/repo"
    assert data["is_active"] is True
    assert data["default_branch"] == "main"


@pytest.mark.asyncio
async def test_add_duplicate_repo(client):
    """Adding the same repo twice should return 409."""
    mock_gh_repo = {"default_branch": "main"}

    with patch(
        "src.api.repos.GitHubClient.get_repo",
        new_callable=AsyncMock,
        return_value=mock_gh_repo,
    ), patch(
        "src.api.repos.GitHubClient.close",
        new_callable=AsyncMock,
    ):
        resp1 = await client.post(
            "/api/repos", json={"owner": "dup", "name": "repo"}
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/repos", json={"owner": "dup", "name": "repo"}
        )
        assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_repos_with_stats(client, db_session: AsyncSession):
    """Repos should include open_pr_count and other stats."""
    repo = TrackedRepo(
        owner="stats", name="repo", full_name="stats/repo", default_branch="main"
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
    repo = TrackedRepo(
        owner="del", name="repo", full_name="del/repo", default_branch="main"
    )
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
