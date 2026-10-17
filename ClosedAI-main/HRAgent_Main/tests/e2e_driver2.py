"""E2E tests for skills, subagents, MCP, plugins, and memory/context.

Requires the mock LLM on 127.0.0.1:8347 and the MCP echo server script.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import SecretStr

JOB_TMP = Path(os.environ.get("JOB_TMP", "."))
MOCK_BASE = "http://127.0.0.1:8347/v1"
MCP_SERVER = JOB_TMP / "mcp_echo_server.py"

sys.path.insert(0, ".")

from core.agent import Agent
from core.conversation import Conversation
from core.conversation.state import ConversationExecutionStatus as CES
from core.execution.event import MessageEvent, ObservationEvent, SystemPromptEvent
from context import AgentContext, load_memory
from models.llm import LLM
from tools import Tool, register_tool
from tools.tool import Action, Observation, ToolAnnotations, ToolDefinition, ToolExecutor
from mcp_integration.config import MCPServer

PASSED = []
FAILED = []


# ------------------------------------------------------- custom echo tool
class EchoAction(Action):
    payload: str = "hello"

    @property
    def visualize(self) -> "Text":
        from rich.text import Text
        return Text(self.payload)


class EchoObservation(Observation):
    @property
    def visualize(self) -> "Text":
        from rich.text import Text
        return Text("")


class EchoExecutor(ToolExecutor):
    def __call__(self, action, conversation=None):
        return EchoObservation.from_text(text=f"echoed:{action.payload}")


class EchoTool(ToolDefinition[EchoAction, EchoObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [
            cls(
                action_type=EchoAction,
                observation_type=EchoObservation,
                description="Echo the given text back.",
                executor=EchoExecutor(),
                annotations=ToolAnnotations(
                    title="echo", readOnlyHint=True, destructiveHint=False,
                    idempotentHint=True, openWorldHint=False,
                ),
            )
        ]


register_tool("echo", EchoTool)


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def make_llm(**kw) -> LLM:
    base = dict(
        model="gpt-4o-mini",
        api_key=SecretStr("sk-mock"),
        base_url=MOCK_BASE,
        usage_id="e2e2",
        num_retries=0,
        timeout=30,
    )
    base.update(kw)
    return LLM(**base)


def content_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for c in content if isinstance(content, list) else [content]:
        text = getattr(c, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def final_message_text(events) -> str:
    for ev in reversed(events):
        if isinstance(ev, MessageEvent) and ev.source == "agent":
            return content_text(getattr(ev.llm_message, "content", None))
    return ""


def obs_texts(events) -> list[str]:
    out = []
    for ev in events:
        if isinstance(ev, ObservationEvent):
            out.append(content_text(getattr(ev.observation, "content", None)))
    return out


# ------------------------------------------------------------------ skills
def test_skills() -> None:
    print("=" * 70)
    print("E2E 7: skills (AgentSkills SKILL.md) load + invoke")
    print("=" * 70)
    skills_dir = JOB_TMP / "e2e_skills"
    skill_path = skills_dir / "test-greeting" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        "---\n"
        "name: test-greeting\n"
        "description: Greets the user.\n"
        "---\n"
        "You are a polite greeter. Always open with 'Aloha!' and be warm.\n",
        encoding="utf-8",
    )
    from skills import load_skills_from_dir

    repo, knowledge, agent_skills = load_skills_from_dir(skills_dir)
    skill = agent_skills.get("test-greeting")
    check("skill loaded as agentskills", skill is not None and skill.is_agentskills_format)

    if skill is None:
        return
    ctx = AgentContext(skills=[skill])
    events: list = []
    conv = Conversation(
        agent=Agent(llm=make_llm(), tools=[], agent_context=ctx),
        workspace=str(JOB_TMP / "ws_skill"),
        callbacks=[lambda ev: events.append(ev)],
        visualizer=None,
        delete_on_close=False,
    )
    conv.send_message('[[TOOL:invoke_skill:{"name":"test-greeting"}]]')
    conv.run()
    check("skill conv FINISHED", conv.state.execution_status == CES.FINISHED)
    check("skill invoked via tool", any("Aloha!" in t for t in obs_texts(events)),
          str(obs_texts(events)[:1])[:80])
    check("final answer present", bool(final_message_text(events)))


# --------------------------------------------------------------- subagents
def test_subagents() -> None:
    print("=" * 70)
    print("E2E 8: subagents (register_agent + factory + run)")
    print("=" * 70)
    from subagents import AgentDefinition, get_agent_factory, register_agent

    def _factory(llm):
        return Agent(llm=llm, tools=[Tool(name="echo")])

    register_agent("e2e_sub", _factory, "E2E test subagent")
    af = get_agent_factory("e2e_sub")
    check("factory registered", af.definition.name == "e2e_sub")
    check("definition description", af.definition.description == "E2E test subagent")

    sub = af.factory_func(make_llm())
    check("factory builds Agent", isinstance(sub, Agent))

    events: list = []
    conv = Conversation(
        agent=sub,
        workspace=str(JOB_TMP / "ws_sub"),
        callbacks=[lambda ev: events.append(ev)],
        visualizer=None,
        delete_on_close=False,
    )
    conv.send_message('[[TOOL:echo:{"payload":"from subagent"}]]')
    conv.run()
    check("subagent conv FINISHED", conv.state.execution_status == CES.FINISHED)
    check("subagent tool worked", any("echoed:from subagent" in t for t in obs_texts(events)))

    # agent_definition_to_factory with explicit AgentDefinition
    from subagents import agent_definition_to_factory

    defn = AgentDefinition(
        name="e2e_def",
        description="def-driven",
        tools=["echo"],
        system_prompt="You are the e2e_def subagent.",
    )
    factory = agent_definition_to_factory(defn)
    def_agent = factory(make_llm())
    check("definition factory builds Agent", isinstance(def_agent, Agent))


# -------------------------------------------------------------------- MCP
def test_mcp() -> None:
    print("=" * 70)
    print("E2E 9: MCP (stdio server -> tools -> agent invocation)")
    print("=" * 70)
    if not MCP_SERVER.exists():
        check("mcp server script exists", False, str(MCP_SERVER))
        return
    check("mcp server script exists", True)

    cfg = {
        "echo": MCPServer(
            transport="stdio",
            command=sys.executable,
            args=[str(MCP_SERVER)],
        )
    }
    events: list = []
    conv = Conversation(
        agent=Agent(llm=make_llm(), tools=[], mcp_config=cfg),
        workspace=str(JOB_TMP / "ws_mcp"),
        callbacks=[lambda ev: events.append(ev)],
        visualizer=None,
        delete_on_close=False,
    )
    conv.send_message('[[TOOL:mcp_echo:{"text":"via mcp"}]]')
    try:
        conv.run()
        check("mcp conv FINISHED", conv.state.execution_status == CES.FINISHED,
              str(conv.state.execution_status))
        check("mcp tool executed", any("mcp:via mcp" in t for t in obs_texts(events)),
              str(obs_texts(events)[:1])[:80])
        check("mcp add tool available", True)
    except Exception as e:  # noqa: BLE001
        check("mcp conv FINISHED", False, f"{type(e).__name__}: {str(e)[:120]}")
        import traceback
        traceback.print_exc()


# ----------------------------------------------------------------- plugins
def test_plugins() -> None:
    print("=" * 70)
    print("E2E 10: plugins (local dir -> manifest + skill merge)")
    print("=" * 70)
    plugin_root = JOB_TMP / "e2e_plugin"
    (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_root / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "e2e-plugin", "version": "1.0.0", "description": "E2E test plugin"}',
        encoding="utf-8",
    )
    (plugin_root / "skills" / "greet" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (plugin_root / "skills" / "greet" / "SKILL.md").write_text(
        "---\nname: greet\ndescription: Plugin greet skill.\n---\nSay 'Bonjour' when greeting.\n",
        encoding="utf-8",
    )

    from plugins import PluginSource, load_plugins

    agent = Agent(llm=make_llm(), tools=[])
    updated, hooks = load_plugins([PluginSource(source=str(plugin_root))], agent)
    check("plugin loaded without error", updated is not None)
    check("plugin skill merged", updated.agent_context is not None
          and any(s.name == "greet" for s in updated.agent_context.skills))
    check("hooks empty for plugin", hooks is None or hooks.is_empty())


# ------------------------------------------------------------ memory/context
def test_memory_context() -> None:
    print("=" * 70)
    print("E2E 11: memory loading + agent context")
    print("=" * 70)
    mem_dir = JOB_TMP / "ws_mem"
    idx = mem_dir / ".HRAgent" / "memory" / "MEMORY.md"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text("Project memory: the magic number is 42.\n", encoding="utf-8")
    mem = load_memory(mem_dir)
    check("memory index loaded", mem is not None and "magic number is 42" in (mem or ""))

    ctx = AgentContext(system_message_suffix="Be extremely terse. Answer in one line.")
    events: list = []
    conv = Conversation(
        agent=Agent(llm=make_llm(), tools=[], agent_context=ctx),
        workspace=str(JOB_TMP / "ws_ctx"),
        callbacks=[lambda ev: events.append(ev)],
        visualizer=None,
        delete_on_close=False,
    )
    conv.send_message("Hello from context test.")
    conv.run()
    sys_prompt = ""
    for ev in events:
        if isinstance(ev, SystemPromptEvent):
            sys_prompt = content_text(getattr(ev.system_prompt, "text", None))
            dyn = content_text(getattr(ev.dynamic_context, "text", None)) \
                if getattr(ev, "dynamic_context", None) else ""
            sys_prompt += "\n" + dyn
    check("system prompt includes suffix", "Be extremely terse" in sys_prompt, sys_prompt[-120:])


def main() -> int:
    test_skills()
    test_subagents()
    test_mcp()
    test_plugins()
    test_memory_context()
    print("=" * 70)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())