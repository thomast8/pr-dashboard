"""Tests for authentication (HMAC-signed cookies)."""

import pytest

from src.api.auth import _sign, _verify


class TestHmacSigning:
    def test_sign_and_verify_roundtrip(self):
        payload = "12345"
        token = _sign(payload)
        assert _verify(token) == payload

    def test_verify_rejects_tampered_token(self):
        token = _sign("12345")
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        assert _verify(tampered) is None

    def test_verify_rejects_no_dot(self):
        assert _verify("nodothere") is None

    def test_verify_rejects_empty(self):
        assert _verify("") is None


class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_auth_status_no_password(self, client):
        """When DASHBOARD_PASSWORD is empty, auth is disabled."""
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["auth_enabled"] is False

    @pytest.mark.asyncio
    async def test_login_no_password_always_succeeds(self, client):
        resp = await client.post("/api/auth/login", json={"password": "anything"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
