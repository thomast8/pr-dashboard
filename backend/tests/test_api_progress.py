"""Tests for the progress tracking API."""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import PullRequest, TeamMember, TrackedRepo


@pytest_asyncio.fixture
async def seed_data(client: AsyncClient, db_session: AsyncSession):
    """Create a repo, PR, and team member for progress tests.

    Uses db_session directly so all data is in the shared in-memory DB
    that the client fixture also reads from.
    """
    repo = TrackedRepo(
        owner="prog", name="repo", full_name="prog/repo", default_branch="main"
    )
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

    member = TeamMember(display_name="Alice", github_login="alice")
    db_session.add(member)
    await db_session.commit()

    return {"repo": repo, "pr": pr, "member": member}


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
            "team_member_id": data["member"].id,
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
    assert body["team_member_name"] == "Alice"


@pytest.mark.asyncio
async def test_update_progress_upserts(client, seed_data):
    """Second update should modify, not duplicate."""
    data = seed_data
    pr_id = data["pr"].id
    member_id = data["member"].id

    # First update
    await client.put(
        f"/api/pulls/{pr_id}/progress",
        json={"team_member_id": member_id, "reviewed": True},
    )

    # Second update — approve
    await client.put(
        f"/api/pulls/{pr_id}/progress",
        json={"team_member_id": member_id, "approved": True},
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
        json={"team_member_id": data["member"].id, "reviewed": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_progress_nonexistent_member(client, seed_data):
    data = seed_data
    resp = await client.put(
        f"/api/pulls/{data['pr'].id}/progress",
        json={"team_member_id": 99999, "reviewed": True},
    )
    assert resp.status_code == 404
