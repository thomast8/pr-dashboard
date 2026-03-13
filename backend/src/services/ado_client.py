"""Azure DevOps API client for work item operations."""

import base64
from urllib.parse import quote

import httpx
from loguru import logger

from src.config.settings import settings

API_VERSION = "7.1"


def _auth_header() -> dict[str, str]:
    """Basic auth with empty username + PAT (ADO standard)."""
    encoded = base64.b64encode(f":{settings.ado_pat}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _work_item_url(item_id: int) -> str:
    """Build a clickable URL to a work item in the ADO web UI."""
    return f"{settings.ado_org_url}/{settings.ado_project}/_workitems/edit/{item_id}"


def _parse_work_item(item: dict) -> dict:
    """Extract relevant fields from an ADO work item response."""
    fields = item.get("fields", {})
    item_id = item["id"]
    return {
        "work_item_id": item_id,
        "title": fields.get("System.Title", ""),
        "state": fields.get("System.State", ""),
        "work_item_type": fields.get("System.WorkItemType", ""),
        "url": _work_item_url(item_id),
        "assigned_to": (fields.get("System.AssignedTo") or {}).get("displayName"),
    }


async def is_configured() -> bool:
    """Check if ADO integration is configured."""
    return bool(settings.ado_org_url and settings.ado_pat and settings.ado_project)


async def list_work_items(limit: int = 100) -> list[dict]:
    """Fetch recent work items ordered by ChangedDate DESC."""
    base_url = f"{settings.ado_org_url}/{quote(settings.ado_project)}/_apis"
    wiql = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "ORDER BY [System.ChangedDate] DESC"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        wiql_resp = await client.post(
            f"{base_url}/wit/wiql?api-version={API_VERSION}&$top={limit}",
            headers={**_auth_header(), "Content-Type": "application/json"},
            json={"query": wiql},
        )
        wiql_resp.raise_for_status()
        work_items = wiql_resp.json().get("workItems", [])

        if not work_items:
            return []

        ids = [str(wi["id"]) for wi in work_items[:limit]]

        fields = "System.Id,System.Title,System.State,System.WorkItemType,System.AssignedTo"
        detail_resp = await client.get(
            f"{base_url}/wit/workitems?ids={','.join(ids)}&fields={fields}&api-version={API_VERSION}",
            headers=_auth_header(),
        )
        detail_resp.raise_for_status()

        return [_parse_work_item(item) for item in detail_resp.json().get("value", [])]


async def search_work_items(query: str) -> list[dict]:
    """Search ADO work items by ID or title substring using WIQL."""
    base_url = f"{settings.ado_org_url}/{quote(settings.ado_project)}/_apis"

    # If query is a pure number, search by ID; otherwise by title
    if query.strip().isdigit():
        wiql = f"SELECT [System.Id] FROM WorkItems WHERE [System.Id] = {query.strip()}"
    else:
        escaped = query.replace("'", "''")
        wiql = (
            f"SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.Title] CONTAINS '{escaped}' "
            f"ORDER BY [System.ChangedDate] DESC"
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Run WIQL query to get work item IDs
        wiql_resp = await client.post(
            f"{base_url}/wit/wiql?api-version={API_VERSION}",
            headers={**_auth_header(), "Content-Type": "application/json"},
            json={"query": wiql},
        )
        wiql_resp.raise_for_status()
        work_items = wiql_resp.json().get("workItems", [])

        if not work_items:
            return []

        # Limit to 20 results
        ids = [str(wi["id"]) for wi in work_items[:20]]

        # Step 2: Fetch full details for those IDs
        fields = "System.Id,System.Title,System.State,System.WorkItemType,System.AssignedTo"
        detail_resp = await client.get(
            f"{base_url}/wit/workitems?ids={','.join(ids)}&fields={fields}&api-version={API_VERSION}",
            headers=_auth_header(),
        )
        detail_resp.raise_for_status()

        return [_parse_work_item(item) for item in detail_resp.json().get("value", [])]


async def get_work_item(item_id: int) -> dict | None:
    """Fetch a single work item's current details."""
    base_url = f"{settings.ado_org_url}/{quote(settings.ado_project)}/_apis"
    fields = "System.Id,System.Title,System.State,System.WorkItemType,System.AssignedTo"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{base_url}/wit/workitems/{item_id}?fields={fields}&api-version={API_VERSION}",
                headers=_auth_header(),
            )
            resp.raise_for_status()
            return _parse_work_item(resp.json())
        except httpx.HTTPStatusError as exc:
            logger.warning(f"Failed to fetch ADO work item {item_id}: {exc}")
            return None
