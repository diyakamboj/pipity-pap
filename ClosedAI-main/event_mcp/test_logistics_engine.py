"""Unit tests for L1 Logistics Engine and FastMCP tools.

Tests:
1. Chronological run-of-show generation from store.
2. Confirmation-state preservation, audit, and distinction in run-of-show.
3. Missing information detection (unconfirmed slots, vendor booking, lead times).
4. Task generation structure (owners, due dates, dependencies, session links).
5. Strictly read-only & preview-only MCP task generation (NO approval bypass; cannot mutate store).
6. Internal backend commit_task_plan (reserved for future human-in-the-loop client approval).
7. Confirmation-state accuracy on operational tasks:
   - Distinguishes operational tasks from confirmed external commitments.
   - Assumed venue AV equipment and unconfirmed catering delivery labeled tentative/assumed.
   - Clear confirmation_requirement attached to all assumptions.
   - No task is falsely labeled 'confirmed'.
8. Non-colliding task IDs (seed tasks tsk-001..tsk-007 preserved; generated tasks tsk-008..tsk-012).
9. Dependency validation and cycle detection (valid DAG, catches unknown IDs, self-deps, and cycles).
10. Dynamic critical path calculation based on DAG longest path (not hardcoded).
11. Preservation of manual organizer edits, custom notes, and completion statuses.
12. Task board grouping and category/owner/status filtering.
13. FastMCP server tools contracts and _canvas metadata.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock
import pytest

# Mock fastmcp if not present in environment
if "fastmcp" not in sys.modules:
    fastmcp_mock = MagicMock()
    class DummyFastMCP:
        def __init__(self, *args, **kwargs):
            pass
        def tool(self, fn=None):
            if fn is not None:
                return fn
            return lambda f: f
        def run(self, *args, **kwargs):
            pass
    fastmcp_mock.FastMCP = DummyFastMCP
    sys.modules["fastmcp"] = fastmcp_mock

# Ensure event_mcp directory is on path
EVENT_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
if EVENT_MCP_DIR not in sys.path:
    sys.path.insert(0, EVENT_MCP_DIR)

from event_store import ConfirmationState, EventStore
from logistics_engine import (
    build_run_of_show,
    calculate_critical_path,
    commit_task_plan,
    generate_operational_tasks,
    get_task_board,
    validate_task_dependencies,
)
from seed_data import TASKS
from server import (
    MockBackend,
    logistics_generate_tasks,
    logistics_run_of_show,
    logistics_task_board,
)


@pytest.fixture
def temp_store_path():
    """Create a temporary filepath for an isolated event store test."""
    fd, path = tempfile.mkstemp(prefix="test_logistics_", suffix=".json")
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture
def isolated_store(temp_store_path):
    """Instantiate a fresh EventStore on a clean temporary path."""
    return EventStore(storage_path=temp_store_path)


# ---------------------------------------------------------------------------
# 1. Run-of-Show Generation Tests
# ---------------------------------------------------------------------------
def test_run_of_show_chronological_order(isolated_store):
    """Run-of-show timeline is sorted chronologically with valid durations."""
    ros = build_run_of_show(isolated_store)

    assert ros["event_name"] == "DubHacks Workshop 2026"
    assert ros["date"] == "2026-11-15"
    assert "Gates Hall 106" in ros["venue"]
    assert ros["operating_window"] == "08:00 - 18:00"

    timeline = ros["timeline"]
    assert len(timeline) == 10

    # Verify chronological ordering
    for i in range(len(timeline) - 1):
        curr_start = timeline[i]["start_time"]
        next_start = timeline[i + 1]["start_time"]
        assert curr_start <= next_start

    # Verify first and last slots match venue bounds
    assert timeline[0]["start_time"] == "08:00"
    assert timeline[0]["item_type"] == "setup"
    assert timeline[-1]["end_time"] == "18:00"
    assert timeline[-1]["item_type"] == "teardown"

    # Verify duration calculation
    for item in timeline:
        assert item["duration_minutes"] > 0
    # 09:30 to 10:30 is 60 minutes
    keynote = next(i for i in timeline if i["id"] == "sch-003")
    assert keynote["duration_minutes"] == 60


def test_run_of_show_confirmation_states(isolated_store):
    """Run-of-show distinguishes confirmed, tentative, and assumed items."""
    ros = build_run_of_show(isolated_store)
    summary = ros["summary"]

    assert summary["total_slots"] == 10
    assert summary["tentative_slots"] >= 4
    assert summary["assumed_slots"] >= 4

    timeline_by_id = {i["id"]: i for i in ros["timeline"]}

    # Keynote is tentative timing with confirmed speaker
    keynote = timeline_by_id["sch-003"]
    assert keynote["confirmation_state"] == ConfirmationState.TENTATIVE.value
    assert keynote["speaker"]["name"] == "Prof. Sara Kim"
    assert keynote["speaker"]["status"] == "confirmed"

    # Lunch is tentative timing with unconfirmed vendor
    lunch = timeline_by_id["sch-006"]
    assert lunch["confirmation_state"] == ConfirmationState.TENTATIVE.value
    assert lunch["vendor"]["name"] == "Taste of Seoul"
    assert lunch["vendor"]["confirmed"] is False

    # Setup and Teardown are operational assumptions
    assert timeline_by_id["sch-001"]["confirmation_state"] == ConfirmationState.ASSUMED.value
    assert timeline_by_id["sch-010"]["confirmation_state"] == ConfirmationState.ASSUMED.value


def test_run_of_show_missing_information(isolated_store):
    """Detects missing information, tentative assumptions, and action items."""
    ros = build_run_of_show(isolated_store)
    missing = ros["missing_information"]
    assert len(missing) >= 3

    types = {m["type"] for m in missing}
    # Unconfirmed exact keynote slot for confirmed speaker
    assert "unconfirmed_speaker_slot" in types
    # Unconfirmed vendor bookings
    assert "unconfirmed_vendor_booking" in types
    # Badge order lead-time cutoff
    assert "lead_time_deadline" in types

    badge_warning = next(m for m in missing if m["type"] == "lead_time_deadline")
    assert "Nov 11" in badge_warning["issue"]


# ---------------------------------------------------------------------------
# 2. Strictly Read-Only MCP Tool & Preview-First Tests (Issue 1)
# ---------------------------------------------------------------------------
def test_mcp_tool_cannot_mutate_store(isolated_store, monkeypatch):
    """Calling the MCP task-generation tool cannot mutate the persistent store.

    Proves that no argument or invocation of logistics_generate_tasks bypasses
    genuine human approval to persist tasks directly into the store.
    """
    backend = MockBackend(store=isolated_store)
    import server
    monkeypatch.setattr(server, "BACKEND", backend)

    initial_tasks = isolated_store.all_tasks()
    assert len(initial_tasks) == 7

    # Call the MCP tool
    resp = logistics_generate_tasks()

    # The tool returns a preview
    assert resp["is_preview"] is True
    assert "Store was NOT modified" in resp["message"]
    assert resp["total_tasks"] == 12

    # The store MUST remain completely unmodified
    stored_tasks = isolated_store.all_tasks()
    assert len(stored_tasks) == 7
    assert stored_tasks == initial_tasks

    # Repeated calls also never modify the store
    resp2 = logistics_generate_tasks()
    assert resp2["is_preview"] is True
    assert len(isolated_store.all_tasks()) == 7


def test_internal_backend_commit_task_plan(isolated_store):
    """Internal backend operation commits approved tasks to the store (reserved for client approval)."""
    assert len(isolated_store.all_tasks()) == 7

    # Commit via internal backend operation
    result = commit_task_plan(isolated_store)
    assert result["success"] is True
    assert result["persisted_count"] == 12
    assert len(isolated_store.all_tasks()) == 12

    # Repeated commit is strictly idempotent
    result2 = commit_task_plan(isolated_store)
    assert result2["success"] is True
    assert len(isolated_store.all_tasks()) == 12


# ---------------------------------------------------------------------------
# 3. Confirmation-State Accuracy & Source Audit Tests (Issue 2)
# ---------------------------------------------------------------------------
def test_confirmation_state_accuracy_in_generated_tasks(isolated_store):
    """Preserves confirmation-state accuracy on all operational tasks.

    - Distinguishes operational tasks from confirmed external commitments.
    - Tasks involving assumed AV equipment and unconfirmed catering are NOT 'confirmed'.
    - Explicit confirmation_requirements are attached to all assumptions.
    """
    plan = generate_operational_tasks(isolated_store)
    tasks = plan["tasks"]
    tasks_by_id = {t["id"]: t for t in tasks}

    # Verify no generated task is falsely marked as 'confirmed'
    for t in tasks:
        assert t["confirmation_state"] != ConfirmationState.CONFIRMED.value, (
            f"Task '{t['id']}' ({t['title']}) is falsely marked as 'confirmed'. "
            f"Operational tasks must reflect tentative or assumed states."
        )
        assert t.get("confirmation_requirement"), (
            f"Task '{t['id']}' lacks an explicit confirmation_requirement string."
        )

    # 1. AV verification (tsk-008): assumed venue equipment, not confirmed
    av_task = tasks_by_id["tsk-008"]
    assert av_task["confirmation_state"] == ConfirmationState.ASSUMED.value
    assert "facility coordinator" in av_task["confirmation_requirement"].lower()

    # 2. Catering delivery load-in (tsk-009): unconfirmed vendor booking and loading dock
    cat_task = tasks_by_id["tsk-009"]
    assert cat_task["confirmation_state"] == ConfirmationState.TENTATIVE.value
    assert "booking" in cat_task["confirmation_requirement"].lower()

    # 3. Teardown / Room Reset (tsk-012): assumed curfew requirement
    teardown = tasks_by_id["tsk-012"]
    assert teardown["confirmation_state"] == ConfirmationState.ASSUMED.value
    assert "lock-out" in teardown["confirmation_requirement"].lower()

    # 4. Check-in desk (tsk-011): assumed volunteer and scanner availability
    checkin = tasks_by_id["tsk-011"]
    assert checkin["confirmation_state"] == ConfirmationState.ASSUMED.value
    assert "volunteer" in checkin["confirmation_requirement"].lower()

    # 5. Keynote briefing (tsk-010): tentative morning schedule
    briefing_task = tasks_by_id["tsk-010"]
    assert briefing_task["confirmation_state"] == ConfirmationState.TENTATIVE.value
    assert "keynote" in briefing_task["confirmation_requirement"].lower()


# ---------------------------------------------------------------------------
# 4. Task ID Collision & Seed Data Consistency Tests
# ---------------------------------------------------------------------------
def test_task_ids_do_not_collide_with_seed_tasks(isolated_store):
    """Seed tasks retain their original IDs and titles; newly generated tasks use non-colliding IDs."""
    seed_tasks_by_id = {t["id"]: t for t in TASKS}
    assert len(seed_tasks_by_id) == 7

    plan = generate_operational_tasks(isolated_store)
    plan_tasks_by_id = {t["id"]: t for t in plan["tasks"]}

    # All 7 seed tasks exist in the plan with their authentic seed titles
    for seed_id, seed in seed_tasks_by_id.items():
        assert seed_id in plan_tasks_by_id
        plan_task = plan_tasks_by_id[seed_id]
        assert plan_task["title"] == seed["title"], (
            f"Seed task {seed_id} title '{seed['title']}' was overwritten with '{plan_task['title']}'"
        )
        assert plan_task["owner"] == seed["owner"]

    # Newly generated tasks have IDs tsk-008 through tsk-012, with no collisions
    generated_ids = {"tsk-008", "tsk-009", "tsk-010", "tsk-011", "tsk-012"}
    for g_id in generated_ids:
        assert g_id in plan_tasks_by_id
        assert g_id not in seed_tasks_by_id


# ---------------------------------------------------------------------------
# 5. Dependency Validation and Cycle Detection Tests
# ---------------------------------------------------------------------------
def test_dependency_validation_valid_dag(isolated_store):
    """Dependency graph is verified as an acyclic DAG with valid task references."""
    plan = generate_operational_tasks(isolated_store)
    validation = plan["dependency_validation"]

    assert validation["is_valid"] is True
    assert validation["errors"] == []

    # Verify all references point to existing tasks
    task_ids = {t["id"] for t in plan["tasks"]}
    for t in plan["tasks"]:
        for dep in t.get("depends_on", []):
            assert dep in task_ids


def test_dependency_validation_catches_invalid_id():
    """Detects references to non-existent task IDs."""
    invalid_tasks = [
        {"id": "tsk-001", "depends_on": ["tsk-999"]},
        {"id": "tsk-002", "depends_on": []},
    ]
    val = validate_task_dependencies(invalid_tasks)
    assert val["is_valid"] is False
    assert any("unknown dependency 'tsk-999'" in e for e in val["errors"])


def test_dependency_validation_catches_self_dependency():
    """Detects self-dependent task loops."""
    self_dep_tasks = [
        {"id": "tsk-001", "depends_on": ["tsk-001"]},
    ]
    val = validate_task_dependencies(self_dep_tasks)
    assert val["is_valid"] is False
    assert any("cannot depend on itself" in e for e in val["errors"])


def test_dependency_validation_catches_cycles():
    """Detects multi-task dependency cycles."""
    cyclic_tasks = [
        {"id": "tsk-001", "depends_on": ["tsk-003"]},
        {"id": "tsk-002", "depends_on": ["tsk-001"]},
        {"id": "tsk-003", "depends_on": ["tsk-002"]},
    ]
    val = validate_task_dependencies(cyclic_tasks)
    assert val["is_valid"] is False
    assert any("Cyclic dependency loop detected" in e for e in val["errors"])


# ---------------------------------------------------------------------------
# 6. Dynamic Critical Path Tests (Non-Hardcoded)
# ---------------------------------------------------------------------------
def test_dynamic_critical_path(isolated_store):
    """Critical path is computed dynamically via longest path on the task DAG."""
    plan = generate_operational_tasks(isolated_store)
    cp = plan["critical_path"]

    # In our DAG, the longest path is:
    # tsk-002 -> tsk-004 -> tsk-007 -> tsk-008 -> tsk-012 (length 5)
    assert cp == ["tsk-002", "tsk-004", "tsk-007", "tsk-008", "tsk-012"]
    assert len(cp) == 5

    # Verify dynamic behavior: if dependencies change, critical path updates accordingly
    custom_tasks = copy.deepcopy(plan["tasks"])
    tasks_map = {t["id"]: t for t in custom_tasks}
    # Add a longer chain starting at tsk-006:
    # tsk-006 -> tsk-005 -> tsk-011 -> tsk-008 -> tsk-012 (length 5)
    tasks_map["tsk-011"]["depends_on"] = ["tsk-005"]
    tasks_map["tsk-008"]["depends_on"] = ["tsk-011"]
    new_cp = calculate_critical_path(custom_tasks)
    assert new_cp == ["tsk-006", "tsk-005", "tsk-011", "tsk-008", "tsk-012"]


# ---------------------------------------------------------------------------
# 7. Manual Edits and Completion Status Preservation Tests
# ---------------------------------------------------------------------------
def test_task_generation_preserves_manual_edits(isolated_store):
    """Task plan generation preserves custom organizer status, owner, title, and notes."""
    # Organizer updates tsk-001 to done, changes owner to Yashika, and adds notes
    isolated_store.update_task(
        "tsk-001",
        {
            "status": "done",
            "owner": "Yashika",
            "title": "Confirmed Prof. Sara Kim Keynote",
            "notes": "Verified directly with speaker over email.",
        },
    )

    plan = generate_operational_tasks(isolated_store)
    tasks_by_id = {t["id"]: t for t in plan["tasks"]}
    p_task = tasks_by_id["tsk-001"]

    assert p_task["status"] == "done"
    assert p_task["owner"] == "Yashika"
    assert p_task["title"] == "Confirmed Prof. Sara Kim Keynote"
    assert p_task["notes"] == "Verified directly with speaker over email."


# ---------------------------------------------------------------------------
# 8. Task Board View Tests
# ---------------------------------------------------------------------------
def test_task_board_grouping_and_filtering(isolated_store):
    """Task board groups by category and respects filters."""
    # Commit tasks to store
    commit_task_plan(isolated_store)

    # Full board
    board = get_task_board(isolated_store)
    assert board["total"] == 12
    assert "categories" in board
    assert "catering" in board["categories"]
    assert "speakers" in board["categories"]
    assert "venue" in board["categories"]
    assert board["status_summary"]["open"] == 12

    # Filter by category
    venue_board = get_task_board(isolated_store, filter_category="venue")
    assert venue_board["total"] == 2
    assert all(t["category"] == "venue" for t in venue_board["tasks"])

    # Filter by owner
    diya_board = get_task_board(isolated_store, filter_owner="Diya")
    assert all("diya" in t["owner"].lower() for t in diya_board["tasks"])


# ---------------------------------------------------------------------------
# 9. FastMCP Server Tools Integration Tests & Canvas Hints
# ---------------------------------------------------------------------------
def test_server_logistics_tools_contracts(isolated_store, monkeypatch):
    """FastMCP tools expose L1 endpoints and return correct _canvas metadata."""
    backend = MockBackend(store=isolated_store)
    import server
    monkeypatch.setattr(server, "BACKEND", backend)

    # 1. logistics_run_of_show
    ros_resp = logistics_run_of_show()
    assert "timeline" in ros_resp
    assert "missing_information" in ros_resp
    assert "_canvas" in ros_resp
    assert ros_resp["_canvas"]["module"] == "run_of_show"
    assert "Run of Show" in ros_resp["_canvas"]["title"]

    # 2. logistics_generate_tasks (strictly preview-only)
    plan_resp = logistics_generate_tasks()
    assert plan_resp["is_preview"] is True
    assert plan_resp["_canvas"]["module"] == "task_board"
    assert "Proposed" in plan_resp["_canvas"]["title"]
    assert len(isolated_store.all_tasks()) == 7

    # 3. logistics_task_board
    board_resp = logistics_task_board(filter_category="catering")
    assert board_resp["found"] is True
    assert board_resp["total"] >= 1
    assert board_resp["_canvas"]["module"] == "task_board"
