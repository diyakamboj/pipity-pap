"""Unit tests for EventStore and MCP backend persistence.

Tests:
1. Initialization from seed data without destroying IDs or schemas.
2. Lookup accuracy and case-insensitive/substring matching.
3. Normalized domain record serialization (to_dict/from_dict) and confirmation states.
4. Updates (tasks, schedule items, briefings, venue constraints).
5. Persistence across store reopening (simulating MCP subprocess restart).
6. Safe error recovery when handling corrupt or invalid JSON.
7. Compatibility with MockBackend and MCP server tool contracts.
"""

from __future__ import annotations

import copy
import json
import multiprocessing as mp
import os
import sys
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

# Mock fastmcp with a proper decorator if fastmcp is not installed in test environment
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

from event_store import (
    Briefing,
    ConfirmationState,
    CorruptedStoreError,
    EventStore,
    OperationalTask,
    ScheduleItem,
    VenueConstraints,
    get_event_store,
)


def _mp_task_worker(storage_path: str, worker_id: int, num_tasks: int, barrier: Any, result_queue: Any):
    """Top-level worker function for multiprocessing task insertion test."""
    try:
        store = EventStore(storage_path=storage_path)
        barrier.wait(timeout=10)
        for i in range(num_tasks):
            task_id = f"tsk-mp-{worker_id}-{i}"
            store.add_task({
                "id": task_id,
                "title": f"MP Task {task_id}",
                "owner": f"Worker-{worker_id}",
                "status": "open",
                "due_date": "2026-11-10",
                "depends_on": [],
            })
        result_queue.put({"worker_id": worker_id, "success": True, "count": num_tasks})
    except Exception as e:
        result_queue.put({"worker_id": worker_id, "success": False, "error": str(e)})


def _mp_approval_worker(storage_path: str, proposal: dict[str, Any], context_dict: dict[str, Any], barrier: Any, result_queue: Any):
    """Top-level worker function for multiprocessing duplicate proposal approval test."""
    try:
        from approval_engine import ApprovalContext, execute_approved_schedule_change_transaction
        store = EventStore(storage_path=storage_path)
        context = ApprovalContext(
            actor_id=context_dict["actor_id"],
            actor_name=context_dict["actor_name"],
            actor_role=context_dict["actor_role"],
            session_id=context_dict.get("session_id", ""),
            timestamp=context_dict.get("timestamp", ""),
            override_confirmed_commitments=context_dict.get("override_confirmed_commitments", False),
            external_confirmations_verified=context_dict.get("external_confirmations_verified", False),
        )
        barrier.wait(timeout=10)
        res = execute_approved_schedule_change_transaction(store, proposal, context)
        result_queue.put({"worker": os.getpid(), "success": True, "res": res})
    except Exception as e:
        result_queue.put({"worker": os.getpid(), "success": False, "error_type": type(e).__name__, "error": str(e)})

from seed_data import (
    BRIEFINGS,
    EVENT,
    SCHEDULE_ITEMS,
    SPEAKERS,
    SPONSORS,
    TASKS,
    VENDORS,
    VENUE_CONSTRAINTS,
)
from server import MockBackend, event_lookup, speaker_lookup, task_list, vendor_lookup


@pytest.fixture
def temp_store_path():
    """Create a temporary filepath for an isolated event store test."""
    fd, path = tempfile.mkstemp(prefix="test_event_store_", suffix=".json")
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
# 1. Initialization Tests
# ---------------------------------------------------------------------------
def test_initialization_from_seed(isolated_store, temp_store_path):
    """EventStore initializes from seed data and creates JSON file."""
    assert os.path.exists(temp_store_path)
    with open(temp_store_path, "r", encoding="utf-8") as f:
        persisted = json.load(f)

    assert persisted["event"]["id"] == "evt-001"
    assert persisted["event"]["name"] == EVENT["name"]
    assert len(persisted["speakers"]) == len(SPEAKERS)
    assert len(persisted["vendors"]) == len(VENDORS)
    assert len(persisted["sponsors"]) == len(SPONSORS)
    assert len(persisted["tasks"]) == len(TASKS)
    assert len(persisted["schedule"]) == len(SCHEDULE_ITEMS)
    assert len(persisted["briefings"]) == len(BRIEFINGS)
    assert persisted["venue_constraints"]["venue_name"] == VENUE_CONSTRAINTS["venue_name"]


def test_initialization_preserves_existing_ids(isolated_store):
    """Original IDs must remain completely unchanged."""
    speaker_ids = {s["id"] for s in isolated_store.all_speakers()}
    assert {"spk-001", "spk-002", "spk-003"}.issubset(speaker_ids)

    vendor_ids = {v["id"] for v in isolated_store.all_vendors()}
    assert {"vnd-001", "vnd-002", "vnd-003"}.issubset(vendor_ids)

    sponsor_ids = {s["id"] for s in isolated_store.all_sponsors()}
    assert {"spo-001", "spo-002"}.issubset(sponsor_ids)

    task_ids = {t["id"] for t in isolated_store.all_tasks()}
    assert {"tsk-001", "tsk-002", "tsk-003", "tsk-004", "tsk-005", "tsk-006", "tsk-007"}.issubset(task_ids)


# ---------------------------------------------------------------------------
# 2. Lookups Tests
# ---------------------------------------------------------------------------
def test_lookups_speaker(isolated_store):
    """Speaker lookups support exact ID, exact name, and case-insensitive substrings."""
    assert isolated_store.find_speaker("spk-003")["name"] == "Prof. Sara Kim"
    assert isolated_store.find_speaker("sara kim")["id"] == "spk-003"
    assert isolated_store.find_speaker("DeepMind")["id"] == "spk-001"
    assert isolated_store.find_speaker("CivicTech")["id"] == "spk-002"
    assert isolated_store.find_speaker("nonexistent") is None
    assert isolated_store.find_speaker("") is None


def test_lookups_vendor(isolated_store):
    """Vendor lookups support ID, exact name, and category substrings."""
    assert isolated_store.find_vendor("vnd-003")["name"] == "Taste of Seoul"
    assert isolated_store.find_vendor("Taste of Seoul")["id"] == "vnd-003"
    assert isolated_store.find_vendor("Campus Catering")["id"] == "vnd-001"
    assert isolated_store.find_vendor("badges")["id"] == "vnd-002"
    assert isolated_store.find_vendor("food")["id"] in ("vnd-001", "vnd-003")
    assert isolated_store.find_vendor("") is None


def test_lookups_sponsor(isolated_store):
    """Sponsor lookups support ID, name, and tier substrings."""
    assert isolated_store.find_sponsor("spo-001")["name"] == "Acme AI Labs"
    assert isolated_store.find_sponsor("gold")["id"] == "spo-001"
    assert isolated_store.find_sponsor("silver")["id"] == "spo-002"
    assert isolated_store.find_sponsor("") is None


def test_lookups_schedule_and_venue(isolated_store):
    """Schedule and venue constraint lookups."""
    venue = isolated_store.get_venue_constraints()
    assert venue["access_start"] == "08:00"
    assert venue["access_end"] == "18:00"
    assert venue["max_capacity"] == 100

    items = isolated_store.all_schedule_items()
    assert len(items) == 10

    keynote = isolated_store.find_schedule_item("sch-003")
    assert keynote is not None
    assert keynote["title"] == "Welcome & Keynote: Fairness in Machine Learning"
    assert keynote["speaker_id"] == "spk-003"


# ---------------------------------------------------------------------------
# 3. Serialization and Confirmation States
# ---------------------------------------------------------------------------
def test_confirmation_state_distinction(isolated_store):
    """Confirmed speaker attendance must remain distinct from tentative session timing."""
    # Speaker attendance is confirmed on Nov 15
    speaker = isolated_store.find_speaker("spk-003")
    assert speaker["status"] == "confirmed"
    assert speaker["availability"] == "Nov 15 confirmed"

    # But exact run-of-show timing for the keynote is a tentative planning assumption
    keynote = isolated_store.find_schedule_item("sch-003")
    assert keynote["confirmation_state"] == ConfirmationState.TENTATIVE.value

    # Operational buffers are assumed
    setup = isolated_store.find_schedule_item("sch-001")
    assert setup["confirmation_state"] == ConfirmationState.ASSUMED.value

    workshop = isolated_store.find_schedule_item("sch-005")
    assert workshop["confirmation_state"] == ConfirmationState.TENTATIVE.value

    lunch = isolated_store.find_schedule_item("sch-006")
    assert lunch["confirmation_state"] == ConfirmationState.TENTATIVE.value

    # Venue constraints are operational assumptions
    venue = isolated_store.get_venue_constraints()
    assert venue["confirmation_state"] == ConfirmationState.ASSUMED.value


def test_domain_record_dataclasses():
    """Test roundtrip serialization of domain dataclasses."""
    sched = ScheduleItem(
        id="sch-999",
        title="Closing Social",
        start_time="17:00",
        end_time="18:00",
        room="Lobby",
        item_type="social",
        confirmation_state=ConfirmationState.PROPOSED.value,
        notes="Proposed evening reception",
    )
    d = sched.to_dict()
    assert d["id"] == "sch-999"
    assert d["confirmation_state"] == "proposed"
    restored = ScheduleItem.from_dict(d)
    assert restored.title == "Closing Social"
    assert restored.confirmation_state == ConfirmationState.PROPOSED.value

    task = OperationalTask(
        id="tsk-999",
        title="Distribute Badges",
        owner="Diya",
        status="open",
        due_date="2026-11-15",
        depends_on=["tsk-002"],
        category="logistics",
    )
    t_dict = task.to_dict()
    assert t_dict["owner"] == "Diya"
    restored_task = OperationalTask.from_dict(t_dict)
    assert restored_task.depends_on == ["tsk-002"]

    briefing = Briefing(
        id="brf-999",
        role="volunteer",
        recipient_id="vol-001",
        recipient_name="Alex Volunteer",
        recipient_email="alex@uw.edu",
        session_title="General Support",
        notes="Check in at 08:30",
    )
    b_dict = briefing.to_dict()
    restored_briefing = Briefing.from_dict(b_dict)
    assert restored_briefing.recipient_name == "Alex Volunteer"

    vc = VenueConstraints(
        venue_name="Test Hall",
        access_start="07:00",
        access_end="19:00",
        max_capacity=150,
        av_provisions=["Projector"],
    )
    vc_dict = vc.to_dict()
    restored_vc = VenueConstraints.from_dict(vc_dict)
    assert restored_vc.max_capacity == 150


# ---------------------------------------------------------------------------
# 4. Updates & Mutations
# ---------------------------------------------------------------------------
def test_task_mutations(isolated_store):
    """Add and update operational tasks."""
    new_task = {
        "id": "tsk-008",
        "title": "Print emergency contact sheets",
        "owner": "Gurt",
        "status": "open",
        "due_date": "2026-11-14",
        "depends_on": [],
        "notes": "Emergency numbers and hospital maps.",
    }
    created = isolated_store.add_task(new_task)
    assert created["id"] == "tsk-008"
    assert len(isolated_store.all_tasks()) == 8

    # Verify duplicate prevention
    with pytest.raises(ValueError):
        isolated_store.add_task(new_task)

    # Update task
    updated = isolated_store.update_task("tsk-008", {"status": "done"})
    assert updated is not None
    assert updated["status"] == "done"
    assert isolated_store.find_task("tsk-008")["status"] == "done"


def test_schedule_mutations(isolated_store):
    """Add and update schedule items."""
    new_slot = {
        "id": "sch-011",
        "title": "After-hours Volunteer Debrief",
        "start_time": "18:00",
        "end_time": "18:30",
        "room": "Gates Hall 106 Patio",
        "item_type": "debrief",
        "speaker_id": None,
        "vendor_id": None,
        "confirmation_state": "assumed",
        "dependencies": ["sch-010"],
        "notes": "Review attendee feedback and logistics wins.",
    }
    isolated_store.add_schedule_item(new_slot)
    assert len(isolated_store.all_schedule_items()) == 11

    updated = isolated_store.update_schedule_item(
        "sch-011", {"confirmation_state": "confirmed", "title": "Confirmed Volunteer Debrief"}
    )
    assert updated is not None
    assert updated["confirmation_state"] == "confirmed"


def test_briefing_mutations(isolated_store):
    """Add and update participant briefings."""
    new_b = {
        "id": "brf-003",
        "role": "speaker",
        "recipient_id": "spk-001",
        "recipient_name": "Dr. Alicia Chen",
        "recipient_email": "alicia@deepmind.com",
        "session_id": "sch-005",
        "session_title": "Morning Workshop: Responsible AI in Practice",
        "notes": "Draft briefing pending confirmation.",
        "confirmation_state": "tentative",
    }
    isolated_store.add_briefing(new_b)
    assert len(isolated_store.all_briefings()) == 3

    updated = isolated_store.update_briefing("brf-003", {"is_stale": True})
    assert updated["is_stale"] is True


# ---------------------------------------------------------------------------
# 5. Persistence Across Subprocess Restarts
# ---------------------------------------------------------------------------
def test_persistence_across_store_reopening(temp_store_path):
    """Data modified in one EventStore instance persists when reopened in a new instance."""
    store1 = EventStore(storage_path=temp_store_path)

    # Perform updates in first store instance
    store1.update_event({"headcount": 95, "budget": 12000})
    store1.add_task(
        {
            "id": "tsk-persist-test",
            "title": "Persistent Task",
            "owner": "Diya",
            "status": "in_progress",
            "due_date": "2026-11-10",
            "depends_on": [],
            "notes": "Should survive restart.",
        }
    )
    store1.update_schedule_item("sch-004", {"title": "Confirmed Sponsor Spotlight", "confirmation_state": "confirmed"})

    # Simulate process exit: store1 is dropped
    del store1

    # Simulate new MCP subprocess starting up with same storage path
    store2 = EventStore(storage_path=temp_store_path)

    ev = store2.get_event()
    assert ev["headcount"] == 95
    assert ev["budget"] == 12000

    task = store2.find_task("tsk-persist-test")
    assert task is not None
    assert task["status"] == "in_progress"

    sch = store2.find_schedule_item("sch-004")
    assert sch["title"] == "Confirmed Sponsor Spotlight"
    assert sch["confirmation_state"] == "confirmed"


# ---------------------------------------------------------------------------
# 6. Error Handling & Recovery
# ---------------------------------------------------------------------------
def test_recovery_from_corrupted_file(temp_store_path):
    """Corrupted JSON file does not crash the server and is preserved as a backup."""
    corrupt_content = "{ invalid json corrupted content ..."
    with open(temp_store_path, "w", encoding="utf-8") as f:
        f.write(corrupt_content)

    store = EventStore(storage_path=temp_store_path)
    # Store recovers to valid working state
    assert store.get_event()["id"] == "evt-001"
    assert len(store.all_speakers()) == len(SPEAKERS)

    # Corrupted file is preserved in a backup file for forensic investigation
    dir_name = os.path.dirname(temp_store_path)
    base_name = os.path.basename(temp_store_path)
    backups = [
        f for f in os.listdir(dir_name)
        if f.startswith(f"{base_name}.corrupted.")
    ]
    assert len(backups) >= 1
    backup_file = os.path.join(dir_name, backups[0])
    with open(backup_file, "r", encoding="utf-8") as f:
        assert f.read() == corrupt_content
    # Clean up backup
    try:
        os.remove(backup_file)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 7. MockBackend & Server Tool Contracts Compatibility
# ---------------------------------------------------------------------------
def test_mock_backend_compatibility(isolated_store):
    """MockBackend delegates cleanly to EventStore without altering contracts."""
    backend = MockBackend(store=isolated_store)

    # Event profile
    ev = backend.get_event()
    assert ev["name"] == EVENT["name"]

    # Speakers
    assert len(backend.all_speakers()) == len(SPEAKERS)
    spk = backend.find_speaker("sara kim")
    assert spk is not None
    assert spk["id"] == "spk-003"

    # Vendors
    assert len(backend.all_vendors()) == len(VENDORS)
    vnd = backend.find_vendor("taste of seoul")
    assert vnd is not None
    assert vnd["id"] == "vnd-003"

    # Sponsors
    assert len(backend.all_sponsors()) == len(SPONSORS)
    spo = backend.find_sponsor("acme ai labs")
    assert spo is not None
    assert spo["id"] == "spo-001"

    # Tasks
    assert len(backend.all_tasks()) == len(TASKS)


def test_server_tools_response_contracts(isolated_store, monkeypatch):
    """MCP tools (event_lookup, speaker_lookup, vendor_lookup, task_list) preserve response contracts."""
    backend = MockBackend(store=isolated_store)
    import server
    monkeypatch.setattr(server, "BACKEND", backend)

    # event_lookup
    ev_resp = event_lookup()
    assert ev_resp["found"] is True
    assert ev_resp["event"]["id"] == "evt-001"
    assert "_canvas" in ev_resp
    assert ev_resp["_canvas"]["module"] == "event_profile"

    # speaker_lookup by query
    spk_resp = speaker_lookup("Sara Kim")
    assert spk_resp["found"] is True
    assert spk_resp["speaker"]["id"] == "spk-003"
    assert spk_resp["_canvas"]["module"] == "speaker_profile"

    # speaker_lookup all
    all_spk_resp = speaker_lookup("")
    assert all_spk_resp["found"] is True
    assert len(all_spk_resp["speakers"]) == len(SPEAKERS)

    # vendor_lookup query
    vnd_resp = vendor_lookup("food")
    assert vnd_resp["found"] is True
    assert vnd_resp["vendor"]["id"] in ("vnd-001", "vnd-003")
    assert vnd_resp["_canvas"]["module"] == "vendor_profile"

    # task_list with filter
    task_resp = task_list(filter_owner="Diya")
    assert task_resp["found"] is True
    assert all("diya" in t["owner"].lower() for t in task_resp["tasks"])
    assert "_canvas" in task_resp
    assert task_resp["_canvas"]["module"] == "task_board"


# ---------------------------------------------------------------------------
# 8. Phase 5B.1: Cross-Process Consistency & Multi-Process Tests
# ---------------------------------------------------------------------------
def test_two_instances_share_json_file_immediate_visibility(temp_store_path):
    """Updates from store instance A are immediately visible through store instance B without process restart."""
    store_a = EventStore(storage_path=temp_store_path)
    store_b = EventStore(storage_path=temp_store_path)

    # 1. Schedule addition in A visible in B
    item = store_a.add_schedule_item({
        "id": "sch-cross-001",
        "title": "Cross-Process Workshop",
        "start_time": "14:00",
        "end_time": "15:00",
        "room": "Kane 120",
        "item_type": "workshop",
    })
    item_in_b = store_b.find_schedule_item("sch-cross-001")
    assert item_in_b is not None
    assert item_in_b["title"] == "Cross-Process Workshop"

    # 2. Task status update in B visible in A
    store_b.update_task("tsk-001", {"status": "done"})
    assert store_a.find_task("tsk-001")["status"] == "done"

    # 3. Event update in A visible in B
    store_a.update_event({"headcount": 150})
    assert store_b.get_event()["headcount"] == 150

    # 4. Audit trail entry in B visible in A
    store_b.record_audit_event({
        "event_id": "evt-cross-001",
        "proposal_id": "prop-cross-001",
        "action_type": "cross_proc_test",
        "actor_id": "usr-diya",
        "actor_role": "lead_organizer",
        "auth_source": "test",
        "timestamp": "2026-10-17T19:00:00Z",
        "target_id": "sch-001",
    })
    assert store_a.find_audit_by_proposal("prop-cross-001") is not None
    assert store_a.get_audit_event("evt-cross-001")["actor_id"] == "usr-diya"


def test_atomic_file_replacement_detected_by_stat_signature(temp_store_path):
    """Store detects atomic file replacement via inode/size/mtime change without strict mtime > previous."""
    store = EventStore(storage_path=temp_store_path)
    initial_stat = store._cached_stat
    assert initial_stat is not None

    # Externally rewrite file using atomic temp file replacement (simulating external process)
    with open(temp_store_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["tasks"].append({
        "id": "tsk-ext-atomic-001",
        "title": "Externally Replaced Task",
        "owner": "ExternalProcess",
        "status": "open",
        "due_date": "2026-11-10",
        "depends_on": [],
    })
    data["version"] = 100

    dir_name = os.path.dirname(temp_store_path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".test_tmp_", suffix=".json")
    with open(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, temp_store_path)

    # Calling read method triggers freshness check and reloads because st_ino changed
    task = store.find_task("tsk-ext-atomic-001")
    assert task is not None
    assert task["owner"] == "ExternalProcess"
    assert store._cached_version == 100


def test_no_reload_during_active_transaction(temp_store_path):
    """Store must not reload from disk in the middle of an active transaction."""
    store = EventStore(storage_path=temp_store_path)

    with store.transaction() as staged:
        # Inside transaction, _ensure_fresh must be a no-op
        staged_items = store.all_schedule_items()
        assert len(staged_items) == len(SCHEDULE_ITEMS)
        assert store._in_transaction is True


def test_lock_file_never_replaces_lock_inode(temp_store_path):
    """Lock file inode remains permanent and is never replaced by atomic save."""
    store = EventStore(storage_path=temp_store_path)
    # Ensure lock exists
    with store._file_lock(exclusive=True):
        pass

    assert os.path.exists(store.lock_path)
    initial_lock_ino = os.stat(store.lock_path).st_ino

    # Execute multiple updates and transactions that perform atomic os.replace on storage_path
    store.update_event({"notes": "Lock test"})
    store.add_task({
        "id": "tsk-lock-test",
        "title": "Lock Inode Test",
        "owner": "Tester",
        "status": "open",
        "due_date": "2026-11-10",
        "depends_on": [],
    })
    with store.transaction() as staged:
        staged["event"]["headcount"] = 180

    # Lock file inode MUST NOT have changed
    current_lock_ino = os.stat(store.lock_path).st_ino
    assert current_lock_ino == initial_lock_ino


def test_corrupted_file_handling_without_silent_data_loss(temp_store_path):
    """Runtime corrupted file detection preserves backup and raises CorruptedStoreError without resetting disk."""
    store = EventStore(storage_path=temp_store_path)
    store.update_event({"headcount": 199})

    # Simulate catastrophic file corruption while store is running
    corrupt_content = "{ this is invalid json corrupted by another process ..."
    with open(temp_store_path, "w", encoding="utf-8") as f:
        f.write(corrupt_content)

    # Calling read methods must detect corrupted data, preserve it, and raise CorruptedStoreError
    with pytest.raises(CorruptedStoreError) as exc_info:
        store.get_event()

    assert "Corrupted file backed up" in str(exc_info.value)

    # Verify that the corrupt content on disk was NOT silently replaced with seed data
    with open(temp_store_path, "r", encoding="utf-8") as f:
        assert f.read() == corrupt_content

    # Verify backup exists
    dir_name = os.path.dirname(temp_store_path)
    base_name = os.path.basename(temp_store_path)
    backups = [f for f in os.listdir(dir_name) if f.startswith(f"{base_name}.corrupted.")]
    assert len(backups) >= 1
    # Cleanup backups
    for b in backups:
        try:
            os.remove(os.path.join(dir_name, b))
        except OSError:
            pass


def test_failed_transaction_rollback_persists_unchanged(temp_store_path):
    """Failed transaction rolls back in-memory and leaves persistent data unchanged on disk."""
    store = EventStore(storage_path=temp_store_path)
    initial_event = store.get_event()

    with pytest.raises(ValueError):
        with store.transaction() as staged:
            staged["event"]["name"] = "Should Not Persist"
            raise ValueError("Deliberate failure inside transaction")

    # In-memory must be rolled back
    assert store.get_event()["name"] == initial_event["name"]

    # On-disk must also remain unchanged
    store_second = EventStore(storage_path=temp_store_path)
    assert store_second.get_event()["name"] == initial_event["name"]


def test_multiprocessing_concurrent_updates_no_lost_updates(temp_store_path):
    """Concurrent updates from separate OS processes yield no lost updates or corrupted state."""
    # Ensure file is initialized
    store = EventStore(storage_path=temp_store_path)
    initial_tasks_count = len(store.all_tasks())

    ctx = mp.get_context("spawn")
    num_workers = 4
    tasks_per_worker = 5
    barrier = ctx.Barrier(num_workers)
    result_queue = ctx.Queue()

    processes = []
    for worker_id in range(num_workers):
        p = ctx.Process(
            target=_mp_task_worker,
            args=(temp_store_path, worker_id, tasks_per_worker, barrier, result_queue),
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join(timeout=15)
        assert p.exitcode == 0

    results = []
    while not result_queue.empty():
        results.append(result_queue.get_nowait())

    assert len(results) == num_workers
    assert all(r["success"] is True for r in results)

    # Verify in fresh store that all tasks from all workers were durably recorded without lost updates
    final_store = EventStore(storage_path=temp_store_path)
    all_final_tasks = final_store.all_tasks()
    assert len(all_final_tasks) == initial_tasks_count + (num_workers * tasks_per_worker)

    for worker_id in range(num_workers):
        for i in range(tasks_per_worker):
            task_id = f"tsk-mp-{worker_id}-{i}"
            assert final_store.find_task(task_id) is not None


def test_multiprocessing_proposal_approval_duplicate_rejection(temp_store_path):
    """Concurrent approval attempts from separate OS processes on the same proposal result in exactly 1 success and 1 duplicate rejection."""
    store = EventStore(storage_path=temp_store_path)

    proposal = {
        "proposal_id": "prop-mp-dup-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    context_dict = {
        "actor_id": "usr-lead-diya",
        "actor_name": "Diya",
        "actor_role": "lead_organizer",
        "session_id": "sess-mp-test",
        "timestamp": "2026-10-17T19:00:00Z",
        "override_confirmed_commitments": True,
        "external_confirmations_verified": True,
    }

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    result_queue = ctx.Queue()

    p1 = ctx.Process(
        target=_mp_approval_worker,
        args=(temp_store_path, proposal, context_dict, barrier, result_queue),
    )
    p2 = ctx.Process(
        target=_mp_approval_worker,
        args=(temp_store_path, proposal, context_dict, barrier, result_queue),
    )

    p1.start()
    p2.start()

    p1.join(timeout=15)
    p2.join(timeout=15)

    assert p1.exitcode == 0
    assert p2.exitcode == 0

    results = []
    while not result_queue.empty():
        results.append(result_queue.get_nowait())

    assert len(results) == 2
    successes = [r for r in results if r["success"] is True]
    failures = [r for r in results if r["success"] is False]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"
    assert failures[0]["error_type"] == "DuplicateProposalError"

    # Verify audit trail contains exactly 1 event for this proposal
    final_store = EventStore(storage_path=temp_store_path)
    matching_audits = [a for a in final_store.all_audit_events() if a.get("proposal_id") == "prop-mp-dup-001"]
    assert len(matching_audits) == 1
    assert matching_audits[0]["outcome"] == "success"

    # Verify schedule item was moved to 09:15-10:15
    item = final_store.find_schedule_item("sch-003")
    assert item["start_time"] == "09:15"
    assert item["end_time"] == "10:15"
