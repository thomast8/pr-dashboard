"""Tests for the team (users) API endpoints."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import User


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession):
    """Create a user for team tests."""
    user = User(github_id=100, login="alice", name="Alice")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_list_team_empty(client):
    resp = await client.get("/api/team")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_team_with_user(client, seed_user):
    resp = await client.get("/api/team")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 1
    assert users[0]["login"] == "alice"
    assert users[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_update_user(client, seed_user):
    resp = await client.put(
        f"/api/team/{seed_user.id}",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_nonexistent_user(client):
    resp = await client.put("/api/team/99999", json={"is_active": False})
    assert resp.status_code == 404
