"""In-app mention notifications with a pluggable hook surface.

Core ships a no-op registry.  Downstream surfaces (email, Slack, WebSocket
delivery, an ``in_app_notifications`` table, etc.) register handlers via
:func:`register_notification_hook`.  The comment routers call
:func:`dispatch_mention_notifications` once per comment with one
:class:`MentionNotification` per resolved recipient.
"""
from __future__ import annotations

import inspect
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MentionNotification:
    """Payload delivered to each registered notification hook."""

    recipient_username: str
    recipient_id: uuid.UUID | None
    actor_username: str | None
    resource_type: str  # "alert" | "incident"
    resource_id: str
    comment_id: str
    comment_text: str


NotificationHook = Callable[
    [MentionNotification],
    Awaitable[None] | None,
]

_hooks: list[NotificationHook] = []


def register_notification_hook(hook: NotificationHook) -> None:
    """Register ``hook`` to receive every future mention notification."""
    _hooks.append(hook)


def clear_notification_hooks() -> None:
    """Remove all registered hooks (primarily for tests)."""
    _hooks.clear()


def _iter_hooks() -> list[NotificationHook]:
    # Snapshot so hooks can register/unregister during dispatch.
    return list(_hooks)


async def dispatch_mention_notifications(
    notifications: list[MentionNotification],
) -> None:
    """Fire every registered hook for every notification.

    Hook exceptions are logged but never propagated — one misbehaving sink must
    not break the comment write path.
    """
    if not notifications:
        return
    for notification in notifications:
        for hook in _iter_hooks():
            try:
                result = hook(notification)
                if inspect.isawaitable(result):
                    await result
            # Hook registry is a plugin surface: we deliberately isolate one
            # misbehaving sink from the rest of the comment write path. Any
            # ``Exception`` subclass is fine to log-and-continue; BaseException
            # still propagates.
            except Exception:  # noqa: BLE001 - isolate plugin hooks  # pragma: no cover
                logger.exception(
                    "Mention notification hook %r raised", hook
                )
