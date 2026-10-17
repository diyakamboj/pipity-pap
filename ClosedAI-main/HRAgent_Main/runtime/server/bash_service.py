"""Minimal ``BashEventService`` shim.

The full ``runtime.server.bash_service`` module was removed during the
repository cleanup (its only event producer, ``tools.terminal``, was removed at
the same time). The server lifespan, deferred-init flow, websocket layer, and
auth dependencies still reference ``BashEventService``, so this module preserves
the small API surface those paths use. The service is intentionally inert: bash
commands cannot be executed, but subscriptions and the ``/sockets/bash-events``
endpoint still work so existing clients do not break.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

from runtime.server.models import (
    BashEventBase,
    BashEventPage,
    ExecuteBashRequest,
)
from runtime.server.pub_sub import PubSub, Subscriber
from runtime.telemetry.logger import get_logger


logger = get_logger(__name__)


class BashEventService:
    """Inert bash event service (see module docstring).

    Args:
        bash_events_dir: Directory bash events were persisted to. Kept for
            signature compatibility with the removed implementation; no events
            are written anymore.
        max_subscribers: Cap on concurrent websocket subscribers.
    """

    def __init__(
        self,
        bash_events_dir: str | Path | None = None,
        max_subscribers: int = 100,
    ) -> None:
        self._bash_events_dir = Path(bash_events_dir) if bash_events_dir else None
        self._pubsub: PubSub[BashEventBase] = PubSub(max_subscribers=max_subscribers)

    # -- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> "BashEventService":
        if self._bash_events_dir is not None:
            self._bash_events_dir.mkdir(parents=True, exist_ok=True)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._pubsub.close()

    # -- pub/sub -----------------------------------------------------------

    def subscribe_to_events(self, subscriber: Subscriber[BashEventBase]) -> UUID:
        """Subscribe a websocket subscriber to bash events."""
        return self._pubsub.subscribe(subscriber)

    def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        """Remove a previously-registered bash event subscriber."""
        return self._pubsub.unsubscribe(subscriber_id)

    # -- search ------------------------------------------------------------

    async def search_bash_events(
        self, page_id: str | None = None, **kwargs: Any
    ) -> BashEventPage:
        """Return a page of recorded bash events.

        No commands can run, so the event log is always empty.
        """
        return BashEventPage(items=[], next_page_id=None)

    # -- execution ---------------------------------------------------------

    async def start_bash_command(self, request: ExecuteBashRequest) -> None:
        """Accept a bash command request.

        The terminal runtime was removed during the cleanup, so no command is
        actually executed. The request is logged so operators can see that a
        client attempted to run bash.
        """
        logger.warning(
            "Bash execution unavailable (terminal runtime removed); command "
            "ignored: %s",
            request.command,
        )

    async def run_retention_cleanup_loop(self, retention_seconds: int) -> None:
        """Loop forever until cancelled.

        Kept so the lifespan's retention task keeps running; there are no
        recorded events to prune.
        """
        while True:
            await asyncio.sleep(retention_seconds)


_bash_event_service = BashEventService()


def get_default_bash_event_service() -> BashEventService:
    """Return the module-level singleton bash event service."""
    return _bash_event_service
