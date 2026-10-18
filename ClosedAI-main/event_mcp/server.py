"""event-mcp: read-only event operations data tools exposed over MCP (stdio).

The Gurt backend launches this as a subprocess (see frontend's
app/api/chat/route.ts -> agent.mcp_config) and exposes each function below to
the agent as a tool. Every tool is READ-ONLY by design: this server never sends
messages, mutates records, or takes irreversible actions. Action/"send" tools
are handled separately as client_tools so a human approves them on the canvas.

Data backend is swappable via the EVENT_MCP_DATA_BACKEND env var:
  - "mock"   (default) -> realistic seed data, fully testable today.
  - "cosmos"           -> Azure Cosmos DB (events collection). Stubbed until
                          credentials are provided; see CosmosBackend below.

Each tool returns a JSON object that includes a "_canvas" hint describing how
the frontend Side Canvas should render the result (module type + title). The
agent reads the data fields; the canvas reads "_canvas" + the payload.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastmcp import FastMCP

# The backend spawns this script via an absolute path and may use its own cwd,
# so make the sibling module importable regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_store import EventStore, get_event_store  # noqa: E402
from logistics_engine import (  # noqa: E402
    build_run_of_show,
    generate_operational_tasks,
    get_task_board,
)
from seed_data import (  # noqa: E402
    BRIEFINGS,
    EVENT,
    SCHEDULE_ITEMS,
    SPEAKERS,
    SPONSORS,
    TASKS,
    VENDORS,
    VENUE_CONSTRAINTS,
)


mcp = FastMCP(name="event-mcp")


# ---------------------------------------------------------------------------
# Data backends
# ---------------------------------------------------------------------------
class MockBackend:
    """Seed-data / JSON-backed event store backend. Deterministic, offline, safe for demos/tests."""

    def __init__(self, store: EventStore | None = None) -> None:
        self.store = store or get_event_store()

    def get_event(self) -> dict[str, Any]:
        return self.store.get_event()

    def find_speaker(self, query: str) -> dict[str, Any] | None:
        return self.store.find_speaker(query)

    def all_speakers(self) -> list[dict[str, Any]]:
        return self.store.all_speakers()

    def find_vendor(self, query: str) -> dict[str, Any] | None:
        return self.store.find_vendor(query)

    def all_vendors(self) -> list[dict[str, Any]]:
        return self.store.all_vendors()

    def find_sponsor(self, query: str) -> dict[str, Any] | None:
        return self.store.find_sponsor(query)

    def all_sponsors(self) -> list[dict[str, Any]]:
        return self.store.all_sponsors()

    def all_tasks(self) -> list[dict[str, Any]]:
        return self.store.all_tasks()


class CosmosBackend(MockBackend):
    """Placeholder for the Cosmos DB production backend.

    Until implemented, falls back to seed data (inherited from MockBackend)
    but logs a clear warning so the gap is obvious.
    """

    def __init__(self) -> None:
        missing = [
            name
            for name in ("COSMOS_URI", "COSMOS_DATABASE", "COSMOS_CONTAINER")
            if not os.environ.get(name)
        ]
        if missing:
            print(
                f"[event-mcp] WARNING: EVENT_MCP_DATA_BACKEND=cosmos but missing {missing}; "
                "falling back to seed data.",
                flush=True,
            )


def _backend() -> MockBackend:
    kind = (os.environ.get("EVENT_MCP_DATA_BACKEND") or "mock").lower()
    return CosmosBackend() if kind == "cosmos" else MockBackend()


BACKEND = _backend()


def _not_found(query: str, resource: str = "record") -> dict[str, Any]:
    return {
        "found": False,
        "query": query,
        "message": (
            f"No {resource} matched '{query}'. Ask the organizer to confirm the "
            "name or ID."
        ),
    }


# ---------------------------------------------------------------------------
# Tools (read-only)
# ---------------------------------------------------------------------------
@mcp.tool
def event_lookup() -> dict[str, Any]:
    """Return the current event profile: name, date, venue, theme, headcount, and budget.

    Read-only. Use for event context questions and to anchor outreach or
    logistics work to the correct event details.
    """
    ev = BACKEND.get_event()
    return {
        "found": True,
        "event": ev,
        "_canvas": {"module": "event_profile", "title": f"{ev['name']} \u2014 Event Brief"},
    }


@mcp.tool
def speaker_lookup(name: str) -> dict[str, Any]:
    """Look up a speaker candidate or list all candidates for the event.

    Pass a name, org, topic keyword, or speaker ID to find a specific record.
    Pass an empty string to list all candidates.

    Returns profile, topic, fit notes, outreach status, and availability.
    Read-only. Use when researching or confirming speaker assignments.
    """
    if not name or not name.strip():
        speakers = BACKEND.all_speakers()
        return {
            "found": True,
            "speakers": speakers,
            "_canvas": {"module": "speaker_profile", "title": "Speaker Candidates"},
        }
    spk = BACKEND.find_speaker(name)
    if not spk:
        return _not_found(name, "speaker")
    return {
        "found": True,
        "speaker": spk,
        "_canvas": {
            "module": "speaker_profile",
            "title": f"{spk['name']} \u2014 Speaker Profile",
        },
    }


@mcp.tool
def vendor_lookup(query: str) -> dict[str, Any]:
    """Look up a vendor by name or category (e.g. "food", "badges", "AV").

    Pass an empty string to list all vendors.

    Returns vendor name, category, quote, per-head/unit cost, dietary options,
    and confirmation status. Read-only. Use when comparing quotes or confirming
    a vendor booking.
    """
    if not query or not query.strip():
        vendors = BACKEND.all_vendors()
        return {
            "found": True,
            "vendors": vendors,
            "_canvas": {"module": "vendor_profile", "title": "Vendor Quotes"},
        }
    vendor = BACKEND.find_vendor(query)
    if not vendor:
        return _not_found(query, "vendor")
    return {
        "found": True,
        "vendor": vendor,
        "_canvas": {
            "module": "vendor_profile",
            "title": f"{vendor['name']} \u2014 Vendor Quote",
        },
    }


@mcp.tool
def sponsor_lookup(query: str) -> dict[str, Any]:
    """Look up a sponsor by name or tier (e.g. "gold", "silver").

    Pass an empty string to list all sponsors.

    Returns sponsor name, tier, amount, outreach status, and contact. Read-only.
    Use when preparing outreach or tracking commitment status.
    """
    if not query or not query.strip():
        sponsors = BACKEND.all_sponsors()
        return {
            "found": True,
            "sponsors": sponsors,
            "_canvas": {"module": "sponsor_profile", "title": "Sponsor Pipeline"},
        }
    sponsor = BACKEND.find_sponsor(query)
    if not sponsor:
        return _not_found(query, "sponsor")
    return {
        "found": True,
        "sponsor": sponsor,
        "_canvas": {
            "module": "sponsor_profile",
            "title": f"{sponsor['name']} \u2014 Sponsor",
        },
    }


@mcp.tool
def task_list(filter_owner: str = "", filter_status: str = "") -> dict[str, Any]:
    """Return the logistics task list for the event.

    Optionally filter by owner name (e.g. "Diya", "Gurt", "Team") or status
    ("open", "done"). Pass empty strings to return all tasks.

    Returns tasks with title, owner, due date, dependencies, and status.
    Read-only. Use when building a run-of-show, checking blockers, or briefing
    participants on their responsibilities.
    """
    tasks = BACKEND.all_tasks()
    if filter_owner:
        tasks = [t for t in tasks if filter_owner.lower() in t["owner"].lower()]
    if filter_status:
        tasks = [t for t in tasks if t["status"].lower() == filter_status.lower()]
    return {
        "found": True,
        "tasks": tasks,
        "total": len(tasks),
        "_canvas": {"module": "task_board", "title": "Logistics Task Board"},
    }


@mcp.tool
def logistics_run_of_show() -> dict[str, Any]:
    """Generate or retrieve the chronological day-of run-of-show timeline for the event.

    Returns the complete day-of agenda from setup to teardown, including session times,
    rooms, linked speakers/vendors, confirmation states (confirmed, tentative, assumed, proposed),
    dependencies, and missing information needing organizer confirmation.

    Read-only. Use to review day-of timing, check gaps, and present the timeline on Canvas.
    """
    return build_run_of_show(BACKEND.store)


@mcp.tool
def logistics_generate_tasks() -> dict[str, Any]:
    """Generate a preview of the proposed operational task plan for event logistics.

    Strictly read-only and preview-only. This tool NEVER persists tasks to the
    event store, regardless of arguments. It returns proposed tasks with owners,
    deadlines, dependencies, critical path analysis, and underlying confirmation
    requirements for organizer review on Canvas.

    Persisting tasks is an internal backend operation reserved for future
    human-in-the-loop approval actions.
    """
    return generate_operational_tasks(BACKEND.store)


@mcp.tool
def logistics_task_board(
    filter_category: str = "", filter_owner: str = "", filter_status: str = ""
) -> dict[str, Any]:
    """Retrieve the active logistics task board grouped by category and owner.

    Optionally filter by category ('logistics', 'catering', 'speakers', 'venue', 'sponsors'),
    owner ('Diya', 'Gurt', 'Team'), or status ('open', 'done', 'in_progress').
    Pass empty strings to return all tasks with full category summaries.

    Read-only. Use to inspect operational progress and render the task board on Canvas.
    """
    return get_task_board(
        BACKEND.store,
        filter_category=filter_category,
        filter_owner=filter_owner,
        filter_status=filter_status,
    )


if __name__ == "__main__":
    # stdio transport: the Gurt backend spawns this process and speaks MCP
    # over stdin/stdout. No network port is opened.
    mcp.run(transport="stdio", show_banner=False)
