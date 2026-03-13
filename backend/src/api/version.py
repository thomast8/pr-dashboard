"""API route for version info and release notes."""

import time
from pathlib import Path

import httpx
from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select

from src.db.engine import get_session
from src.models.tables import GitHubAccount
from src.services.crypto import decrypt_token

router = APIRouter(prefix="/api", tags=["version"])

REPO_OWNER = "ADG-Projects"
REPO_NAME = "pr-dashboard"
CACHE_TTL_SECONDS = 3600  # 1 hour

# Read version from pyproject.toml at import time
_PYPROJECT = Path(__file__).parent.parent.parent / "pyproject.toml"


def _read_version() -> str:
    """Read version from pyproject.toml."""
    try:
        for line in _PYPROJECT.read_text().splitlines():
            if line.startswith("version"):
                return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    return "unknown"


_APP_VERSION = _read_version()


class VersionInfo(BaseModel):
    version: str
    release_notes: str | None = None
    release_url: str | None = None
    release_name: str | None = None
    published_at: str | None = None


_cache: dict[str, object] = {"data": None, "timestamp": 0.0}


async def _get_any_github_token() -> str | None:
    """Get a token from any linked GitHub account for API access."""
    async for session in get_session():
        result = await session.execute(
            select(GitHubAccount.encrypted_token)
            .where(GitHubAccount.encrypted_token.isnot(None))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            return decrypt_token(row)
    return None


async def _fetch_release_info() -> dict:
    """Fetch latest release info from GitHub, with caching."""
    now = time.monotonic()
    cached_ts = _cache["timestamp"]
    if _cache["data"] and (now - cached_ts) < CACHE_TTL_SECONDS:  # type: ignore[operator]
        return _cache["data"]  # type: ignore[return-value]

    token = await _get_any_github_token()
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            # Token from a different org may 403; retry unauthenticated for public repos
            if resp.status_code == 403 and token:
                headers.pop("Authorization", None)
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "release_notes": data.get("body"),
                    "release_url": data.get("html_url"),
                    "release_name": data.get("name"),
                    "published_at": data.get("published_at"),
                }
                _cache["data"] = result
                _cache["timestamp"] = now
                return result
            logger.warning(f"GitHub releases API returned {resp.status_code}")
    except Exception:
        logger.warning("Failed to fetch release info from GitHub")

    return {"release_notes": None, "release_url": None, "release_name": None, "published_at": None}


@router.get("/version")
async def get_version() -> VersionInfo:
    release_info = await _fetch_release_info()
    return VersionInfo(version=_APP_VERSION, **release_info)
