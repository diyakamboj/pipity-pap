from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Self

from pydantic import Field
from rich.text import Text

from tools.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


if TYPE_CHECKING:
    from core.conversation.base import BaseConversation
    from core.conversation.state import ConversationState


class ActivateIntegrationAction(Action):
    integration: str = Field(
        description="Name of the integration to activate, from the catalog below."
    )

    @property
    def visualize(self) -> Text:
        t = Text()
        t.append("Activate integration: ", style="bold blue")
        t.append(self.integration)
        return t


class ActivateIntegrationObservation(Observation):
    integration: str = Field(
        description="Name of the integration this observation corresponds to."
    )

    @property
    def visualize(self) -> Text:
        t = Text()
        t.append(f"[integration: {self.integration}]\n", style="bold green")
        t.append(self.text)
        return t


TOOL_DESCRIPTION_TEMPLATE = """Activate an installed integration so its tools become available to call.

Installed integrations are NOT all loaded by default -- their full tool
catalogs can be large, and most conversations only need a few. Call this
once with the integration's name before using any of its tools; the tools
then appear for you to call directly on your next turn. Calling this again
for an already-active integration is safe (no-op, returns its tool names).

This only makes tools *callable* -- it does not perform any action by
itself, and every tool call (from this or any other source) still goes
through the normal security/approval flow before it executes anything.

Available integrations:
{catalog}"""


class ActivateIntegrationExecutor(ToolExecutor):
    def __call__(
        self,
        action: ActivateIntegrationAction,
        conversation: "BaseConversation | None" = None,
    ) -> ActivateIntegrationObservation:
        name = action.integration.strip()
        activate = getattr(conversation, "activate_mcp_server", None)
        if not callable(activate):
            return ActivateIntegrationObservation.from_text(
                text=(
                    "Integration activation is unavailable in this "
                    "conversation context."
                ),
                is_error=True,
                integration=name,
            )

        tool_names, error = activate(name)
        if error:
            return ActivateIntegrationObservation.from_text(
                text=error, is_error=True, integration=name
            )

        return ActivateIntegrationObservation.from_text(
            text=(
                f"Integration '{name}' is active. Available tools: "
                f"{', '.join(sorted(tool_names)) if tool_names else '<none>'}."
            ),
            integration=name,
        )


class ActivateIntegrationTool(ToolDefinition[ActivateIntegrationAction, ActivateIntegrationObservation]):
    """Built-in tool for lazily activating an installed MCP integration.

    Mirrors ``InvokeSkillTool``'s progressive-disclosure pattern: a short
    catalog of what's *available* is shown up front, and full tool schemas
    for a given integration only enter the model's context once explicitly
    requested -- instead of every installed MCP server's entire tool catalog
    being materialized into every conversation regardless of relevance.
    """

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        **params,
    ) -> Sequence[Self]:
        if params:
            raise ValueError("ActivateIntegrationTool doesn't accept parameters")
        if conv_state is None:
            raise ValueError("ActivateIntegrationTool requires conv_state")

        mcp_config = conv_state.agent.mcp_config
        lines = []
        for name in sorted(mcp_config):
            server = mcp_config[name]
            desc = (server.description or "").strip()
            lines.append(f"- {name}: {desc}" if desc else f"- {name}")
        catalog = "\n".join(lines) if lines else "(none installed)"

        return [
            cls(
                action_type=ActivateIntegrationAction,
                observation_type=ActivateIntegrationObservation,
                description=TOOL_DESCRIPTION_TEMPLATE.format(catalog=catalog),
                executor=ActivateIntegrationExecutor(),
                annotations=ToolAnnotations(
                    title="activate_integration",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]
