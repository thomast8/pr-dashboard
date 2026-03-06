"""Tests for the progress tracking API."""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import PullRequest, TrackedRepo, User


@pytest_asyncio.fixture
async def seed_data(client: AsyncClient, db_session: AsyncSession):
    """Create a repo, PR, and user for progress tests."""
    repo = TrackedRepo(owner="prog", name="repo", full_name="prog/repo", default_branch="main")
    db_session.add(repo)
    await db_session.flush()

    now = datetime.now(UTC)
    pr = PullRequest(
        repo_id=repo.id,
        number=42,
        title="Test PR",
        state="open",
        draft=False,
        head_ref="feature",
        base_ref="main",
        author="dev",
        additions=10,
        deletions=5,
        changed_files=3,
        html_url="https://github.com/prog/repo/pull/42",
        created_at=now,
        updated_at=now,
        last_synced_at=now,
    )
    db_session.add(pr)
    await db_session.flush()

    user = User(github_id=12345, login="alice", name="Alice")
    db_session.add(user)
    await db_session.commit()

    return {"repo": repo, "pr": pr, "user": user}


@pytest.mark.asyncio
async def test_get_progress_empty(client, seed_data):
    data = seed_data
    resp = await client.get(f"/api/pulls/{data['pr'].id}/progress")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_update_progress_creates_entry(client, seed_data):
    data = seed_data
    resp = await client.put(
        f"/api/pulls/{data['pr'].id}/progress",
        json={
            "user_id": data["user"].id,
            "reviewed": True,
            "approved": False,
            "notes": "Looks good so far",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reviewed"] is True
    assert body["approved"] is False
    assert body["notes"] == "Looks good so far"
    assert body["user_name"] == "Alice"


@pytest.mark.asyncio
async def test_update_progress_upserts(client, seed_data):
    """Second update should modify, not duplicate."""
    data = seed_data
    pr_id = data["pr"].id
    user_id = data["user"].id

    # First update
    await client.put(
        f"/api/pulls/{pr_id}/progress",
        json={"user_id": user_id, "reviewed": True},
    )

    # Second update — approve
    await client.put(
        f"/api/pulls/{pr_id}/progress",
        json={"user_id": user_id, "approved": True},
    )

    # Verify only one entry exists
    resp = await client.get(f"/api/pulls/{pr_id}/progress")
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["reviewed"] is True
    assert entries[0]["approved"] is True


@pytest.mark.asyncio
async def test_progress_nonexistent_pr(client, seed_data):
    data = seed_data
    resp = await client.put(
        "/api/pulls/99999/progress",
        json={"user_id": data["user"].id, "reviewed": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_progress_nonexistent_user(client, seed_data):
    data = seed_data
    resp = await client.put(
        f"/api/pulls/{data['pr'].id}/progress",
        json={"user_id": 99999, "reviewed": True},
    )
    assert resp.status_code == 404
