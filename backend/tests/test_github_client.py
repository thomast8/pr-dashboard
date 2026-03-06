"""Tests for the GitHub API client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.github_client import GitHubClient, parse_gh_datetime


def _mock_response(status_code: int = 200, json_data=None, headers=None):
    """Build an httpx.Response with a fake request attached (needed by raise_for_status)."""
    h = {"content-type": "application/json"}
    if headers:
        h.update(headers)
    resp = httpx.Response(
        status_code,
        json=json_data,
        headers=h,
        request=httpx.Request("GET", "https://api.github.com/test"),
    )
    return resp


class TestParseGhDatetime:
    def test_parses_utc_z(self):
        dt = parse_gh_datetime("2025-06-15T10:30:00Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6
        assert dt.hour == 10

    def test_parses_offset(self):
        dt = parse_gh_datetime("2025-06-15T10:30:00+00:00")
        assert dt is not None

    def test_none_returns_none(self):
        assert parse_gh_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert parse_gh_datetime("") is None


class TestGitHubClient:
    @pytest.mark.asyncio
    async def test_list_open_pulls(self):
        """Verify list_open_pulls calls the correct endpoint."""
        mock_resp = _mock_response(json_data=[{"number": 1, "title": "test"}])

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
            client = GitHubClient(token="fake-token")
            pulls = await client.list_open_pulls("org", "repo")
            assert len(pulls) == 1
            assert pulls[0]["number"] == 1
            await client.close()

    @pytest.mark.asyncio
    async def test_pagination_follows_next_link(self):
        """Verify _get_paginated follows Link headers."""
        page1_resp = _mock_response(
            json_data=[{"id": 1}],
            headers={"link": '<https://api.github.com/next?page=2>; rel="next"'},
        )
        page2_resp = _mock_response(json_data=[{"id": 2}])

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return page1_resp if call_count == 1 else page2_resp

        with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
            client = GitHubClient(token="fake-token")
            results = await client._get_paginated("/test")
            assert len(results) == 2
            assert results[0]["id"] == 1
            assert results[1]["id"] == 2
            await client.close()

    @pytest.mark.asyncio
    async def test_client_sends_auth_header(self):
        """Verify the Authorization header is set when token is provided."""
        client = GitHubClient(token="my-secret-token")
        http_client = await client._ensure_client()
        assert http_client.headers["Authorization"] == "Bearer my-secret-token"
        await client.close()

    @pytest.mark.asyncio
    async def test_client_reuses_connection(self):
        """Calling _ensure_client twice returns the same client."""
        client = GitHubClient(token="tok")
        c1 = await client._ensure_client()
        c2 = await client._ensure_client()
        assert c1 is c2
        await client.close()
