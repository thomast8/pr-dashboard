"""Tests for the team API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_team_empty(client):
    resp = await client.get("/api/team")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_team_member(client):
    resp = await client.post(
        "/api/team",
        json={"display_name": "Alice", "github_login": "alice", "email": "alice@example.com"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Alice"
    assert data["github_login"] == "alice"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_update_team_member(client):
    # Create
    create_resp = await client.post(
        "/api/team", json={"display_name": "Bob"}
    )
    member_id = create_resp.json()["id"]

    # Update
    resp = await client.put(
        f"/api/team/{member_id}",
        json={"display_name": "Robert", "github_login": "robertb"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Robert"
    assert resp.json()["github_login"] == "robertb"


@pytest.mark.asyncio
async def test_deactivate_team_member(client):
    create_resp = await client.post(
        "/api/team", json={"display_name": "Charlie"}
    )
    member_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/team/{member_id}")
    assert resp.status_code == 204

    # Verify deactivated
    list_resp = await client.get("/api/team")
    members = list_resp.json()
    deactivated = [m for m in members if m["id"] == member_id]
    assert len(deactivated) == 1
    assert deactivated[0]["is_active"] is False


@pytest.mark.asyncio
async def test_update_nonexistent_member(client):
    resp = await client.put(
        "/api/team/99999", json={"display_name": "Nobody"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_nonexistent_member(client):
    resp = await client.delete("/api/team/99999")
    assert resp.status_code == 404
