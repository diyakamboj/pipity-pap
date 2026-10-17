"""Minimal critic model surface.

The ``HRAgent.sdk.critic`` subsystem was removed during the repository cleanup.
The surviving code only references a few of its types:

* :class:`CriticBase` — type of the optional ``critic`` attribute on agents.
* :class:`CriticResult` — optional field on action/message events.
* :class:`IterativeRefinementConfig` — settings for the (removed) API critic.

Critics are optional everywhere; since the implementation is gone, the
``critic`` attribute stays ``None`` and ``critic_result`` stays ``None``.
These lightweight models keep that contract without rebuilding the subsystem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from rich.text import Text


class CriticBase(BaseModel):
    """Base class for a critic that evaluates agent actions.

    Only the ``mode`` attribute is preserved; subclasses that actually
    evaluate were removed with the critic subsystem.
    """

    mode: str = Field(
        default="finish_and_message",
        description=(
            "Which actions trigger critic evaluation "
            "(e.g. 'all_actions' or 'finish_and_message')."
        ),
    )


class CriticResult(BaseModel):
    """Result of a critic evaluation attached to an action or message event."""

    label: str = Field(
        default="critic",
        description="Short label describing the evaluation outcome.",
    )
    score: float | None = Field(
        default=None,
        description="Optional numeric score produced by the critic.",
    )
    rationale: str | None = Field(
        default=None,
        description="Optional free-text rationale for the evaluation.",
    )

    @property
    def visualize(self) -> "Text":
        """A Rich text rendering of this result for event visualization."""
        from rich.text import Text

        return Text(self.rationale or self.label)


class IterativeRefinementConfig(BaseModel):
    """Configuration for iterative refinement of critic feedback."""

    success_threshold: float | None = Field(
        default=None,
        description="Score threshold above which refinement stops.",
    )
    max_iterations: int = Field(
        default=0,
        description="Maximum number of refinement iterations.",
    )
