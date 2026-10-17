"""Minimal workspace models.

The full ``HRAgent.sdk.workspace`` package was removed during the repository
cleanup. The surviving code only needs a small path-holding model used for
typing, serialization, and working-directory access, so this module preserves
just that surface instead of rebuilding the deleted subsystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BaseWorkspace(BaseModel):
    """A directory the agent reads/writes and runs commands in.

    Only the path is tracked here; command/file execution is handled by the
    tool layer. Remaining code accesses ``working_dir`` directly and passes
    the model around for typing and serialization.
    """

    working_dir: str = Field(
        ...,
        description=(
            "Absolute or relative path to the workspace directory the agent "
            "operates in."
        ),
    )

    @field_validator("working_dir", mode="before")
    @classmethod
    def _coerce_working_dir(cls, v: Any) -> str:
        """Accept both ``str`` and ``Path`` for ``working_dir``."""
        return str(v) if isinstance(v, Path) else v


class LocalWorkspace(BaseWorkspace):
    """A workspace rooted at a directory on the local filesystem."""


class RemoteWorkspace(BaseWorkspace):
    """A workspace hosted by a remote agent server."""

    default_conversation_tags: dict[str, str] | None = Field(
        default=None,
        description="Default tags applied to conversations using this workspace.",
    )


class AsyncRemoteWorkspace(RemoteWorkspace):
    """Compatibility alias for the asynchronous remote workspace type."""


# Backwards-compatible name for the abstract workspace base.
Workspace = BaseWorkspace
