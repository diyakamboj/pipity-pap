"""Gemini preset configuration for HRAgents agents.

This preset uses gemini-style file editing tools instead of the default
claude-style file_editor tool.
"""

from core.agent import Agent
from context.condenser import (
    LLMSummarizingCondenser,
)
from context.condenser.base import CondenserBase
from models.llm.llm import LLM
from runtime.telemetry.logger import get_logger
from tools import BROWSER_TOOL_NAME, Tool


logger = get_logger(__name__)

# Canonical gemini-style tool names (implementations were removed during the
# cleanup; specs are resolved at runtime via the registry when available).
GEMINI_TOOL_NAMES: tuple[str, ...] = (
    "terminal",
    "read_file",
    "write_file",
    "edit",
    "list_directory",
    "task_tracker",
)


def register_gemini_tools(enable_browser: bool = True) -> None:
    """Register the gemini set of tools."""
    logger.debug("No gemini tool implementations to register.")


def get_gemini_tools(
    enable_browser: bool = True,
) -> list[Tool]:
    """Get the gemini set of tool specifications.

    This uses gemini-style file editing tools (read_file, write_file, edit,
    list_directory) instead of the default claude-style file_editor tool.

    Args:
        enable_browser: Whether to include browser tools.
    """
    tools = [Tool(name=name) for name in GEMINI_TOOL_NAMES]
    if enable_browser:
        tools.append(Tool(name=BROWSER_TOOL_NAME))
    return tools


def get_gemini_condenser(llm: LLM) -> CondenserBase:
    """Get the default condenser for gemini preset."""
    condenser = LLMSummarizingCondenser(llm=llm, max_size=80, keep_first=4)
    return condenser


def get_gemini_agent(
    llm: LLM,
    cli_mode: bool = False,
) -> Agent:
    """Get an agent with gemini-style tools: read_file, write_file, edit,
    list_directory."""
    tools = get_gemini_tools(
        enable_browser=not cli_mode,
    )
    agent = Agent(
        llm=llm,
        tools=tools,
        system_prompt_kwargs={"cli_mode": cli_mode},
        condenser=get_gemini_condenser(
            llm=llm.model_copy(update={"usage_id": "condenser"})
        ),
    )
    return agent
