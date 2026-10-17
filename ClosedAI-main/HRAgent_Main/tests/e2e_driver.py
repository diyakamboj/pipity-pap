"""End-to-end agent test driver against the local mock LLM.

Exercises: startup, agent/conversation construction, basic turns, tool
calling + execution + observation, streaming, error handling.
"""
from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr

JOB_TMP = os.environ.get("JOB_TMP", ".")
MOCK_BASE = "http://127.0.0.1:8347/v1"

sys.path.insert(0, ".")

# ---------------------------------------------------------------- imports
from core.agent import Agent
from core.conversation import Conversation
from core.conversation.exceptions import ConversationRunError
from core.conversation.state import ConversationExecutionStatus as CES
from core.execution.event import (
    ActionEvent,
    AgentErrorEvent,
    ConversationErrorEvent,
    MessageEvent,
    ObservationEvent,
)
from models.llm import LLM
from tools import Tool, register_tool
from tools.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)

from rich.text import Text  # noqa: F401  (used implicitly by visualizer attr)

# ------------------------------------------------------- custom echo tool
class EchoAction(Action):
    payload: str = Field(description="Text to echo back.")

    @property
    def visualize(self) -> Text:
        return Text(self.payload)


class EchoObservation(Observation):
    """Result of echoing."""

    @property
    def visualize(self) -> Text:
        return Text("")


class EchoExecutor(ToolExecutor):
    def __call__(self, action, conversation=None):
        if action.payload == "boom":
            raise RuntimeError("echo tool exploded on purpose")
        return EchoObservation.from_text(text=f"echoed:{action.payload}")


class EchoTool(ToolDefinition[EchoAction, EchoObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence[Self]:
        return [
            cls(
                action_type=EchoAction,
                observation_type=EchoObservation,
                description="Echo the given text back to the user.",
                executor=EchoExecutor(),
                annotations=ToolAnnotations(
                    title="echo", readOnlyHint=True, destructiveHint=False,
                    idempotentHint=True, openWorldHint=False,
                ),
            )
        ]


register_tool("echo", EchoTool)

# ------------------------------------------------------------- test utils
PASSED = []
FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def make_llm(**kw) -> LLM:
    base = dict(
        model="gpt-4o-mini",
        api_key=SecretStr("sk-mock"),
        base_url=MOCK_BASE,
        usage_id="e2e",
        num_retries=0,
        timeout=30,
    )
    base.update(kw)
    return LLM(**base)


def make_agent(llm: LLM, tools=None) -> Agent:
    return Agent(llm=llm, tools=tools or [Tool(name="echo")])


def collect_events(events: list):
    events.append


def run_conversation(llm: LLM, message: str, ws: str, **conv_kw):
    events: list = []
    agent = make_agent(llm)
    conv = Conversation(
        agent=agent,
        workspace=str(Path(JOB_TMP) / ws),
        callbacks=[lambda ev: events.append(ev)],
        visualizer=None,
        delete_on_close=False,
        **conv_kw,
    )
    conv.send_message(message)
    conv.run()
    return conv, events


def event_types(events) -> list[str]:
    return [type(e).__name__ for e in events]


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


def main() -> int:
    print("=" * 70)
    print("E2E 1: basic conversation (plain text response)")
    print("=" * 70)
    conv, events = run_conversation(make_llm(), "Hello mock! What is 2+2?", "ws_basic")
    check("status FINISHED", conv.state.execution_status == CES.FINISHED,
          str(conv.state.execution_status))
    check("system prompt emitted", "SystemPromptEvent" in event_types(events))
    check("user message emitted", "MessageEvent" in event_types(events))
    text = final_message_text(events)
    check("final assistant text present", bool(text), text[:80])
    check("no tool calls in basic turn", "ActionEvent" not in event_types(events))

    print("=" * 70)
    print("E2E 2: tool calling -> execution -> observation -> finish")
    print("=" * 70)
    conv2, events2 = run_conversation(
        make_llm(), '[[TOOL:echo:{"payload":"hello via tool"}]]', "ws_tool"
    )
    check("status FINISHED", conv2.state.execution_status == CES.FINISHED,
          str(conv2.state.execution_status))
    types2 = event_types(events2)
    check("ActionEvent emitted", "ActionEvent" in types2)
    check("ObservationEvent emitted", "ObservationEvent" in types2)
    obs_text = ""
    for ev in events2:
        if isinstance(ev, ObservationEvent):
            obs_text = content_text(getattr(ev.observation, "content", None))
    check("tool result surfaced", "echoed:hello via tool" in obs_text, obs_text[:80])
    check("no AgentErrorEvent", "AgentErrorEvent" not in types2)
    text2 = final_message_text(events2)
    check("final assistant text present", bool(text2), text2[:80])

    print("=" * 70)
    print("E2E 3: streaming token callbacks")
    print("=" * 70)
    token_events: list = []
    llm_s = make_llm(stream=True)
    agent_s = make_agent(llm_s)
    conv3 = Conversation(
        agent=agent_s,
        workspace=str(Path(JOB_TMP) / "ws_stream"),
        callbacks=[lambda ev: None],
        token_callbacks=[lambda ev: token_events.append(ev)],
        visualizer=None,
        delete_on_close=False,
    )
    conv3.send_message("stream this response please")
    conv3.run()
    check("token callbacks fired", len(token_events) > 0, f"{len(token_events)} chunks")
    chunk_text = ""
    for ev in token_events:
        try:
            chunk_text += ev.choices[0].delta.content or ""
        except Exception:  # noqa: BLE001
            pass
    check("token chunks concatenate to response", "Echo: stream this response please" in chunk_text,
          chunk_text[:80])
    check("stream finished", conv3.state.execution_status == CES.FINISHED)

    print("=" * 70)
    print("E2E 4: tool error -> AgentErrorEvent -> agent continues")
    print("=" * 70)
    conv4, events4 = run_conversation(
        make_llm(), '[[TOOL:echo:{"payload":"boom"}]]', "ws_toolerr"
    )
    types4 = event_types(events4)
    check("status FINISHED", conv4.state.execution_status == CES.FINISHED,
          str(conv4.state.execution_status))
    check("AgentErrorEvent emitted", "AgentErrorEvent" in types4)
    check("run did not crash", True)
    err_detail = ""
    for ev in events4:
        if isinstance(ev, AgentErrorEvent):
            err_detail = content_text(getattr(ev, "content", None)) or getattr(ev, "error", "") or ""
    check("error detail mentions explosion", "exploded on purpose" in err_detail, err_detail[:80])

    print("=" * 70)
    print("E2E 5: persistent LLM failure -> ConversationRunError (designed)")
    print("=" * 70)
    try:
        run_conversation(make_llm(num_retries=1), "[[FAIL]]", "ws_llmfail")
        check("ConversationRunError raised", False, "no exception")
    except ConversationRunError as e:
        check("ConversationRunError raised", True, str(e)[:120])
        check("error message mentions failure", "mock forced failure" in str(e))
    except Exception as e:  # noqa: BLE001
        check("ConversationRunError raised", False, f"wrong type {type(e).__name__}: {e}")

    print("=" * 70)
    print("E2E 6: transient LLM failure -> retry -> success")
    print("=" * 70)
    conv6, events6 = run_conversation(make_llm(num_retries=2), "[[FAIL_ONCE]] retry me", "ws_retry")
    check("status FINISHED after retry", conv6.state.execution_status == CES.FINISHED,
          str(conv6.state.execution_status))
    check("retry recovered", "Echo: [[FAIL_ONCE]] retry me" in final_message_text(events6),
          final_message_text(events6)[:80])

    print("=" * 70)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())