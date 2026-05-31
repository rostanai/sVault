"""In-app notification feed schemas (bell icon)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    """A single notification feed item (alert or approval)."""

    id: str
    type: str
    title: str
    subtitle: str | None = None
    href: str
    created_at: datetime


class NotificationFeed(BaseModel):
    """Bell-feed response — unread count + newest items (capped at 20)."""

    unread_count: int
    items: list[NotificationItem]
