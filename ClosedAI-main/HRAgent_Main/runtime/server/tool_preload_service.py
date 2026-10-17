"""Service which preloads chromium."""

from __future__ import annotations

from runtime.server.config import get_default_config
from runtime.telemetry.logger import get_logger
from tools.schema import Action
from tools.tool import create_action_type_with_risk
from utilities.models import get_known_concrete_subclasses


_logger = get_logger(__name__)


class ToolPreloadService:
    """Service which preloads tools / chromium reducing time to
    start first conversation"""

    running: bool = False

    async def start(self) -> bool:
        """Preload tools"""

        # Skip if already running
        if self.running:
            return True

        self.running = True
        try:
            # The browser toolset (which needed chromium preloading) was removed
            # during the cleanup. Pre-creating action classes still prevents
            # processing that would otherwise cost time per tool on the first
            # conversation invocation.
            for action_type in get_known_concrete_subclasses(Action):
                create_action_type_with_risk(action_type)

            return True
        except Exception:
            _logger.exception("Error preloading tools")
            return False

    async def stop(self) -> None:
        """Stop the tool preload process."""
        self.running = False

    def is_running(self) -> bool:
        """Check if tool preload is running."""
        return self.running


_tool_preload_service: ToolPreloadService | None = None


def get_tool_preload_service() -> ToolPreloadService | None:
    """Get the tool preload service instance if preload is enabled."""
    global _tool_preload_service
    config = get_default_config()

    if not config.preload_tools:
        _logger.info("Tool preload is disabled in configuration")
        return None

    if _tool_preload_service is None:
        _tool_preload_service = ToolPreloadService()
    return _tool_preload_service
