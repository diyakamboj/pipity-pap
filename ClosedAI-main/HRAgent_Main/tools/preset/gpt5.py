"""GPT-5 preset configuration for HRAgents agents.

This preset uses ApplyPatchTool for file edits instead of the default
claude-style FileEditorTool. It mirrors the Gemini preset pattern by
providing optional helpers without changing global defaults.
"""

from core.agent import Agent
from context.condenser import LLMSummarizingCondenser
from context.condenser.base import CondenserBase
from models.llm.llm import LLM
from runtime.telemetry.logger import get_logger
from tools import BROWSER_TOOL_NAME, Tool


logger = get_logger(__name__)

# Canonical GPT-5 style tool names (implementations were removed during the
# cleanup; specs are resolved at runtime via the registry when available).
GPT5_TOOL_NAMES: tuple[str, ...] = (
    "terminal",
    "apply_patch",
    "task_tracker",
)


def register_gpt5_tools(enable_browser: bool = True) -> None:
    """Register the GPT-5 tool set (terminal, apply_patch, task_tracker, browser)."""
    logger.debug("No gpt5 tool implementations to register.")


def get_gpt5_tools(enable_browser: bool = True) -> list[Tool]:
    """Get the GPT-5 tool specifications using ApplyPatchTool for edits.

    Args:
        enable_browser: Whether to include browser tools.
    """
    tools: list[Tool] = [Tool(name=name) for name in GPT5_TOOL_NAMES]
    if enable_browser:
        tools.append(Tool(name=BROWSER_TOOL_NAME))
    return tools


def get_gpt5_condenser(llm: LLM) -> CondenserBase:
    """Get the default condenser for the GPT-5 preset."""
    return LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)


def get_gpt5_agent(llm: LLM, cli_mode: bool = False) -> Agent:
    """Get an agent with ApplyPatchTool for unified-diff style file editing."""
    tools = get_gpt5_tools(enable_browser=not cli_mode)
    agent = Agent(
        llm=llm,
        tools=tools,
        system_prompt_kwargs={"cli_mode": cli_mode},
        condenser=get_gpt5_condenser(
            llm=llm.model_copy(update={"usage_id": "condenser"})
        ),
    )
    return agent
