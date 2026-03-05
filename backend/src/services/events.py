"""Server-Sent Events (SSE) broadcast service."""

import asyncio
import json
from typing import Any

from loguru import logger

# Subscribers: each is an asyncio.Queue that receives (event_type, data) tuples
_subscribers: list[asyncio.Queue[tuple[str, str]]] = []
_lock = asyncio.Lock()


async def subscribe() -> asyncio.Queue[tuple[str, str]]:
    """Register a new SSE subscriber and return its queue."""
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    async with _lock:
        _subscribers.append(queue)
    return queue


async def unsubscribe(queue: asyncio.Queue[tuple[str, str]]) -> None:
    """Remove a subscriber."""
    async with _lock:
        try:
            _subscribers.remove(queue)
        except ValueError:
            pass


async def broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Push an event to all connected SSE clients."""
    payload = json.dumps(data)
    async with _lock:
        for q in _subscribers:
            try:
                q.put_nowait((event_type, payload))
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full, dropping event")
