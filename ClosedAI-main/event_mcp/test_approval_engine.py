from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import threading
from unittest.mock import MagicMock, patch
import pytest

# Ensure FastMCP is mocked consistently across test runner
if "fastmcp" not in sys.modules or not isinstance(sys.modules.get("fastmcp"), MagicMock):
    fastmcp_mock = MagicMock()
    class DummyFastMCP:
        def __init__(self, *args, **kwargs):
            self._tools = {}
            self._tool_manager = MagicMock(_tools=self._tools)
        def tool(self, fn=None):
            if fn is not None:
                name = getattr(fn, "__name__", str(fn))
                self._tools[name] = fn
                return fn
            def decorator(f):
                name = getattr(f, "__name__", str(f))
                self._tools[name] = f
                return f
            return decorator
        def run(self, *args, **kwargs):
            pass
    fastmcp_mock.FastMCP = DummyFastMCP
    sys.modules["fastmcp"] = fastmcp_mock

# Ensure event_mcp directory is on path
EVENT_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
if EVENT_MCP_DIR not in sys.path:
    sys.path.insert(0, EVENT_MCP_DIR)

import multiprocessing

from approval_engine import (
    ApprovalContext,
    ConfirmedCommitmentError,
    ConflictingProposalError,
    DuplicateProposalError,
    InternalTestApprovalAdapter,
    InvalidProposalError,
    InvalidProposalStateError,
    ProposalExpiredError,
    ProposalNotFoundError,
    ProposalRejectedError,
    ScheduleItemNotFoundError,
    StaleProposalError,
    TamperedProposalError,
    UnauthorizedApprovalError,
    UntrustedApprovalContextError,
    apply_approved_proposal_by_id,
    apply_approved_schedule_change,
    apply_rejected_proposal_by_id,
    create_trusted_proposal,
    create_trusted_proposal_from_conflict,
    execute_approved_proposal_by_id,
    execute_approved_schedule_change_transaction,
    expire_proposal,
    get_proposal,
    is_proposal_expired,
    list_pending_proposals,
    parse_iso_timestamp,
    reject_proposal,
)
from conflict_engine import ConflictType, detect_schedule_conflicts, propose_conflict_resolutions
from event_store import ConfirmationState, EventStore, ProposalRecord, ProposalStatus
import server


def _concurrent_proposal_by_id_worker(storage_path: str, proposal_id: str, context_dict: dict[str, Any], barrier: Any, result_queue: Any):
    """Top-level worker function for multiprocessing proposal-by-ID approval test."""
    try:
        from approval_engine import (
            ApprovalContext,
            InternalTestApprovalAdapter,
            apply_approved_proposal_by_id,
        )
        from event_store import EventStore

        proc_store = EventStore(storage_path=storage_path)
        ctx = ApprovalContext(
            actor_id=context_dict["actor_id"],
            actor_name=context_dict["actor_name"],
            actor_role=context_dict["actor_role"],
            session_id=context_dict.get("session_id", ""),
            timestamp=context_dict.get("timestamp", ""),
            override_confirmed_commitments=context_dict.get("override_confirmed_commitments", True),
            external_confirmations_verified=context_dict.get("external_confirmations_verified", True),
        )
        adapter = InternalTestApprovalAdapter(ctx)
        if barrier:
            barrier.wait(timeout=10)
        res = apply_approved_proposal_by_id(proc_store, proposal_id, adapter=adapter)
        result_queue.put({"worker": os.getpid(), "success": True, "res": res})
    except Exception as e:
        result_queue.put({"worker": os.getpid(), "success": False, "error_type": type(e).__name__, "error": str(e)})


@pytest.fixture
def isolated_store(tmp_path):
    """Provide a fresh, isolated EventStore in a temporary directory for each test."""
    store_file = tmp_path / "test_event_data.json"
    store = EventStore(storage_path=str(store_file))
    return store


@pytest.fixture
def lead_organizer_context():
    """Internal test approval context representing Lead Organizer Diya."""
    return ApprovalContext(
        actor_id="usr-diya-001",
        actor_name="Diya",
        actor_role="lead_organizer",
        session_id="sess-test-lead",
        timestamp="2026-10-17T18:00:00Z",
        override_confirmed_commitments=True,
        external_confirmations_verified=True,
    )


@pytest.fixture
def organizer_context():
    """Internal test approval context representing an Organizer."""
    return ApprovalContext(
        actor_id="usr-org-002",
        actor_name="Alex Organizer",
        actor_role="organizer",
        session_id="sess-test-org",
        timestamp="2026-10-17T18:00:00Z",
        override_confirmed_commitments=False,
        external_confirmations_verified=False,
    )


# ===========================================================================
# 1. Successful Approved Schedule Mutation
# ===========================================================================
def test_successful_approved_schedule_mutation(isolated_store, lead_organizer_context):
    """Applying an approved schedule change updates the schedule, briefings, and audit trail."""
    proposal = {
        "proposal_id": "prop-test-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
            {"record_id": "sch-003", "field": "room", "before": "Gates Hall 106", "after": "Gates Hall 106"},
        ],
    }

    # Execute via InternalTestApprovalAdapter through the public API boundary
    adapter = InternalTestApprovalAdapter(lead_organizer_context)
    result = apply_approved_schedule_change(isolated_store, proposal, adapter=adapter)

    assert result["success"] is True
    assert result["target_schedule_id"] == "sch-003"
    assert result["mutation"]["after"]["start_time"] == "09:15"
    assert result["mutation"]["after"]["end_time"] == "10:15"

    # Verify live store state
    sch_item = isolated_store.find_schedule_item("sch-003")
    assert sch_item["start_time"] == "09:15"
    assert sch_item["end_time"] == "10:15"

    # Verify audit event in store
    audit_events = isolated_store.all_audit_events()
    assert len(audit_events) == 1
    assert audit_events[0]["proposal_id"] == "prop-test-001"
    assert audit_events[0]["actor_id"] == "usr-diya-001"
    assert audit_events[0]["actor_role"] == "lead_organizer"
    assert audit_events[0]["outcome"] == "success"


# ===========================================================================
# 2. Self-Declared Trusted Context Rejected at Production Boundary
# ===========================================================================
def test_self_declared_trusted_context_rejected_at_production_boundary(isolated_store, lead_organizer_context):
    """Production entrypoint fails closed when callers pass self-declared contexts or flags without an adapter."""
    proposal = {
        "proposal_id": "prop-test-untrusted",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # Case A: Self-declared ApprovalContext passed directly without adapter
    with pytest.raises(UntrustedApprovalContextError) as exc_a:
        apply_approved_schedule_change(isolated_store, proposal, lead_organizer_context)
    assert "Production mutation entrypoint fails closed in Phase 5A" in str(exc_a.value)

    # Case B: Arbitrary caller dict with approved=True
    with pytest.raises(UntrustedApprovalContextError):
        apply_approved_schedule_change(isolated_store, proposal, {"approved": True, "actor": "Diya"})

    # Case C: Spoofed headers or string
    with pytest.raises(UntrustedApprovalContextError):
        apply_approved_schedule_change(isolated_store, proposal, "X-Auth-Role: lead_organizer")

    # Case D: None context without adapter
    with pytest.raises(UntrustedApprovalContextError):
        apply_approved_schedule_change(isolated_store, proposal, None)

    # Case E: Invalid adapter object
    with pytest.raises(UntrustedApprovalContextError):
        apply_approved_schedule_change(isolated_store, proposal, adapter="not_an_adapter")


# ===========================================================================
# 3. Rejection of Untrusted or Unauthorized Context at Executor
# ===========================================================================
def test_rejection_of_untrusted_or_unauthorized_context_at_executor(isolated_store):
    """Transaction executor rejects non-ApprovalContext objects and unauthorized roles."""
    proposal = {
        "proposal_id": "prop-test-exec",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # Not an ApprovalContext instance
    with pytest.raises(UntrustedApprovalContextError):
        execute_approved_schedule_change_transaction(isolated_store, proposal, {"actor": "spoof"})

    # Missing actor_id
    with pytest.raises(UntrustedApprovalContextError):
        execute_approved_schedule_change_transaction(
            isolated_store, proposal, ApprovalContext(actor_id="", actor_name="A", actor_role="lead_organizer")
        )

    # Unauthorized role (e.g. volunteer, attendee, speaker)
    unauthorized_ctx = ApprovalContext(
        actor_id="usr-vol-001",
        actor_name="Volunteer Val",
        actor_role="volunteer",
    )
    with pytest.raises(UnauthorizedApprovalError):
        execute_approved_schedule_change_transaction(isolated_store, proposal, unauthorized_ctx)


# ===========================================================================
# 4. Validation and Commit Protected by Same Lock
# ===========================================================================
def test_validation_and_commit_protected_by_same_lock(isolated_store, lead_organizer_context):
    """Verify that state validation, impact check, and mutation execute under store.transaction() lock."""
    # Verify premature save raises inside an active transaction
    with isolated_store.transaction():
        assert isolated_store._in_transaction is True
        with pytest.raises(RuntimeError) as exc_info:
            isolated_store.save()
        assert "Premature save called while an atomic transaction is active" in str(exc_info.value)

    assert isolated_store._in_transaction is False

    # Verify that during execute_approved_schedule_change_transaction, store._lock is held
    lock_verified = False
    original_analyze = sys.modules["approval_engine"].analyze_schedule_impact

    def hook_analyze(store, *args, **kwargs):
        nonlocal lock_verified
        # The store lock is reentrant (RLock); attempting to acquire non-blocking in another thread must fail
        lock_held_in_other_thread = []
        def probe_lock():
            # If store._lock is held by the main thread, another thread cannot acquire it without waiting
            acquired = store._lock.acquire(blocking=False)
            if acquired:
                store._lock.release()
                lock_held_in_other_thread.append(False)
            else:
                lock_held_in_other_thread.append(True)

        t = threading.Thread(target=probe_lock)
        t.start()
        t.join()

        lock_verified = lock_held_in_other_thread[0] and store._in_transaction
        return original_analyze(store, *args, **kwargs)

    with patch("approval_engine.analyze_schedule_impact", side_effect=hook_analyze):
        proposal = {
            "proposal_id": "prop-lock-test",
            "target_schedule_id": "sch-003",
            "proposed_changes": [
                {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
                {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
            ],
        }
        execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)

    assert lock_verified is True


# ===========================================================================
# 5. Concurrent Attempts to Approve Same Proposal
# ===========================================================================
def test_concurrent_attempts_to_approve_same_proposal(isolated_store, lead_organizer_context):
    """Multiple concurrent threads attempting to approve the same proposal result in exactly one commit."""
    proposal = {
        "proposal_id": "prop-race-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    successes = []
    duplicate_errors = []

    def worker():
        try:
            res = execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)
            successes.append(res)
        except DuplicateProposalError as e:
            duplicate_errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread must have succeeded; the other 4 must have been rejected
    assert len(successes) == 1
    assert len(duplicate_errors) == 4

    # The audit trail must contain exactly one record for this proposal
    audits = [a for a in isolated_store.all_audit_events() if a.get("proposal_id") == "prop-race-001"]
    assert len(audits) == 1


# ===========================================================================
# 6. Intervening Schedule Modification Rejected
# ===========================================================================
def test_intervening_schedule_modification_rejected(isolated_store, lead_organizer_context):
    """A proposal prepared against an older baseline is rejected when an intervening modification occurs."""
    proposal = {
        "proposal_id": "prop-stale-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # Simulate an intervening modification in the store before proposal approval
    isolated_store.update_schedule_item("sch-003", {"start_time": "09:45"})

    with pytest.raises(StaleProposalError) as exc_info:
        execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)

    assert "Proposal baseline is stale for schedule item 'sch-003' field 'start_time'" in str(exc_info.value)
    assert "current live value is '09:45'" in str(exc_info.value)

    # Audit trail must not have recorded this rejected proposal
    assert isolated_store.find_audit_by_proposal("prop-stale-001") is None


# ===========================================================================
# 7. New Conflict Rejection
# ===========================================================================
def test_new_conflict_rejection(isolated_store, lead_organizer_context):
    """Proposals that introduce newly detected conflicts are rejected."""
    # Moving sch-003 to 08:45-09:45 overlaps with sch-001 (08:00-09:00) in Gates Hall 106
    conflict_proposal = {
        "proposal_id": "prop-conflict-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "08:45"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "09:45"},
        ],
    }

    with pytest.raises(ConflictingProposalError) as exc_info:
        execute_approved_schedule_change_transaction(isolated_store, conflict_proposal, lead_organizer_context)

    assert "Proposal introduces" in str(exc_info.value)
    assert "Room contention" in str(exc_info.value)

    # Schedule item must remain unchanged
    item = isolated_store.find_schedule_item("sch-003")
    assert item["start_time"] == "09:30"
    assert item["end_time"] == "10:30"


# ===========================================================================
# 8. Confirmed Commitment Protection
# ===========================================================================
def test_confirmed_commitment_protection(isolated_store, organizer_context, lead_organizer_context):
    """Modifying confirmed commitments requires lead organizer authority and explicit override flags."""
    # Ensure sch-003 is marked confirmed
    isolated_store.update_schedule_item("sch-003", {"confirmation_state": ConfirmationState.CONFIRMED.value})

    proposal = {
        "proposal_id": "prop-confirmed-001",
        "target_schedule_id": "sch-003",
        "affects_confirmed_commitments": True,
        "required_confirmations": ["Speaker agreement from Prof. Sara Kim"],
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # Non-lead organizer cannot modify confirmed commitments
    with pytest.raises(ConfirmedCommitmentError) as exc_a:
        execute_approved_schedule_change_transaction(isolated_store, proposal, organizer_context)
    assert "Modifying confirmed commitments requires 'lead_organizer' authority" in str(exc_a.value)

    # Lead organizer without override_confirmed_commitments is rejected
    no_override_lead = ApprovalContext(
        actor_id="usr-diya-001",
        actor_name="Diya",
        actor_role="lead_organizer",
        override_confirmed_commitments=False,
    )
    with pytest.raises(ConfirmedCommitmentError) as exc_b:
        execute_approved_schedule_change_transaction(isolated_store, proposal, no_override_lead)
    assert "override_confirmed_commitments=True" in str(exc_b.value)

    # Lead organizer with unverified external confirmations is rejected
    unverified_lead = ApprovalContext(
        actor_id="usr-diya-001",
        actor_name="Diya",
        actor_role="lead_organizer",
        override_confirmed_commitments=True,
        external_confirmations_verified=False,
    )
    with pytest.raises(ConfirmedCommitmentError) as exc_c:
        execute_approved_schedule_change_transaction(isolated_store, proposal, unverified_lead)
    assert "external_confirmations_verified=True" in str(exc_c.value)


# ===========================================================================
# 9. Duplicate Proposal Rejection (Sequential Idempotency)
# ===========================================================================
def test_duplicate_proposal_rejection(isolated_store, lead_organizer_context):
    """An approved proposal cannot be executed twice."""
    proposal = {
        "proposal_id": "prop-dup-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # First attempt succeeds
    res1 = execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)
    assert res1["success"] is True

    # Second attempt with identical proposal ID is rejected
    with pytest.raises(DuplicateProposalError) as exc_info:
        execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)
    assert "was already approved and executed" in str(exc_info.value)


# ===========================================================================
# 10. Strengthened Atomicity & Persistence Failure Rollback
# ===========================================================================
def test_persistence_failure_rollback(isolated_store, lead_organizer_context):
    """Failure during persistence leaves schedule, briefings, audit, tasks, and on-disk JSON unchanged.

    Ensures failed transactions do not consume proposal IDs.
    """
    initial_schedule = copy.deepcopy(isolated_store.all_schedule_items())
    initial_briefings = copy.deepcopy(isolated_store.all_briefings())
    initial_audits = copy.deepcopy(isolated_store.all_audit_events())
    initial_tasks = copy.deepcopy(isolated_store.all_tasks())

    with open(isolated_store.storage_path, "r", encoding="utf-8") as f:
        initial_disk_content = f.read()

    proposal = {
        "proposal_id": "prop-disk-fail-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # Simulate filesystem I/O error during atomic save
    with patch.object(isolated_store, "save", side_effect=IOError("Simulated disk full")):
        with pytest.raises(IOError) as exc_info:
            execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)
        assert "Simulated disk full" in str(exc_info.value)

    # 1. In-memory state must be completely rolled back
    assert isolated_store.all_schedule_items() == initial_schedule
    assert isolated_store.all_briefings() == initial_briefings
    assert isolated_store.all_audit_events() == initial_audits
    assert isolated_store.all_tasks() == initial_tasks

    # 2. On-disk content must be byte-for-byte identical
    with open(isolated_store.storage_path, "r", encoding="utf-8") as f:
        current_disk_content = f.read()
    assert current_disk_content == initial_disk_content

    # 3. Proposal ID must NOT be consumed in audit trail
    assert isolated_store.find_audit_by_proposal("prop-disk-fail-001") is None

    # 4. Retrying the proposal when I/O is restored must now succeed
    res = execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)
    assert res["success"] is True
    assert isolated_store.find_schedule_item("sch-003")["start_time"] == "09:15"


# ===========================================================================
# 11. Briefing Invalidation & Sent Version Preservation
# ===========================================================================
def test_briefing_invalidation_and_sent_version_preservation(isolated_store, lead_organizer_context):
    """Draft/ready briefings become stale; sent briefings are preserved immutable and reported."""
    # Ensure brf-001 is ready and brf-002 is sent
    isolated_store.update_briefing("brf-001", {"status": "ready", "is_stale": False})
    isolated_store.update_briefing("brf-002", {"status": "sent", "is_stale": False, "session_id": "sch-003"})

    proposal = {
        "proposal_id": "prop-brief-001",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    result = execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)

    # brf-001 (ready) must transition to status="stale"
    b1 = isolated_store.find_briefing("brf-001")
    assert b1["status"] == "stale"
    assert b1["is_stale"] is True

    # brf-002 (sent) must preserve status="sent", marked is_stale=True, and reported in result
    b2 = isolated_store.find_briefing("brf-002")
    assert b2["status"] == "sent"
    assert b2["is_stale"] is True
    assert "brf-002" in result["sent_briefings_needing_revision"]



# ===========================================================================
# 12. Preservation of Task Status and Manual Edits
# ===========================================================================
def test_preservation_of_task_status_and_manual_edits(isolated_store, lead_organizer_context):
    """Existing task completion statuses and manual organizer edits are never overwritten."""
    isolated_store.update_task("tsk-001", {
        "status": "in_progress",
        "notes": "Manual organizer note: microphone checked by Diya at 08:15.",
    })

    proposal = {
        "proposal_id": "prop-task-preserve",
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    execute_approved_schedule_change_transaction(isolated_store, proposal, lead_organizer_context)

    task = isolated_store.find_task("tsk-001")
    assert task["status"] == "in_progress"
    assert "Manual organizer note: microphone checked by Diya at 08:15." in task["notes"]


# ===========================================================================
# 13. No Mutation Through Existing MCP Tools
# ===========================================================================
def test_no_mutation_through_existing_mcp_tools(isolated_store, monkeypatch):
    """Verify that all existing FastMCP tools remain strictly read-only and never mutate records."""
    monkeypatch.setattr(server.BACKEND, "store", isolated_store)

    initial_audits = len(isolated_store.all_audit_events())
    initial_schedule = copy.deepcopy(isolated_store.all_schedule_items())

    # Invoke tool functions through their underlying callable
    def call_tool(tool_obj, *args, **kwargs):
        fn = getattr(tool_obj, "fn", tool_obj)
        return fn(*args, **kwargs)

    call_tool(server.event_lookup)
    call_tool(server.speaker_lookup, "")
    call_tool(server.vendor_lookup, "")
    call_tool(server.sponsor_lookup, "")
    call_tool(server.task_list)
    call_tool(server.logistics_run_of_show)
    call_tool(server.logistics_generate_tasks)
    call_tool(server.logistics_task_board)
    call_tool(server.logistics_preview_briefing, "speaker", "spk-003")
    call_tool(server.logistics_list_briefings)
    call_tool(server.logistics_check_stale_briefings)
    call_tool(server.logistics_detect_conflicts)
    call_tool(server.logistics_analyze_impact, "sch-003", "09:15", "10:15")
    call_tool(server.logistics_propose_resolutions, "cfl-nonexistent")

    # Audit trail must not have grown
    assert len(isolated_store.all_audit_events()) == initial_audits
    # Schedule must not have changed
    assert isolated_store.all_schedule_items() == initial_schedule

    # Mutation entrypoints must NOT be exposed as MCP tools
    assert "apply_approved_schedule_change" not in server.mcp._tool_manager._tools
    assert "apply_approved_schedule_change" not in server.__dict__
    assert "execute_approved_schedule_change_transaction" not in server.mcp._tool_manager._tools
    assert "execute_approved_schedule_change_transaction" not in server.__dict__
    assert "apply_approved_proposal_by_id" not in server.mcp._tool_manager._tools
    assert "apply_approved_proposal_by_id" not in server.__dict__


# ===========================================================================
# 14. Phase 5B.2: Trusted Proposal Creation & Retrieval
# ===========================================================================
def test_create_and_retrieve_trusted_proposal_from_l3(isolated_store):
    """L3 conflict resolution proposal is validated, fingerprinted, and registered server-side."""
    isolated_store.add_schedule_item(
        {
            "id": "sch-compete-001",
            "title": "Competing Workshop",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Tentative workshop creating room overlap.",
        }
    )
    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP)
    proposals_res = propose_conflict_resolutions(isolated_store, room_cfl["id"])
    candidate = next(p for p in proposals_res["proposals"] if p["strategy"] == "RESCHEDULE_SESSION")

    # Create trusted proposal
    res = create_trusted_proposal(isolated_store, candidate, ttl_seconds=1800)
    assert res["success"] is True
    prop_id = res["proposal_id"]
    assert prop_id.startswith("prop-")
    assert res["status"] == ProposalStatus.PENDING.value
    assert res["baseline_fingerprint"]
    preview = res["preview"]
    assert preview["target_schedule_id"] in ("sch-003", "sch-compete-001")
    assert len(preview["changes"]) > 0

    # Retrieve proposal
    saved = get_proposal(isolated_store, prop_id)
    assert saved is not None
    assert saved["id"] == prop_id
    assert saved["status"] == "pending"
    assert saved["target_schedule_id"] == preview["target_schedule_id"]
    assert saved["baseline_fingerprint"] == res["baseline_fingerprint"]

    # List pending
    pending = list_pending_proposals(isolated_store)
    assert any(p["id"] == prop_id for p in pending)
    target_p = next(p for p in pending if p["id"] == prop_id)
    assert target_p["is_stale"] is False

    # Audit trail verification
    audits = isolated_store.all_audit_events()
    create_audit = next((a for a in audits if a.get("proposal_id") == prop_id), None)
    assert create_audit is not None
    assert create_audit["action_type"] == "proposal_created"
    assert create_audit["outcome"] == "success"


# ===========================================================================
# 15. Phase 5B.2: Proposal Persistence Across Store Instances
# ===========================================================================
def test_proposal_persistence_across_event_store_instances(isolated_store):
    """Proposal registry records persist to disk and reload across independent store instances."""
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Move AI Workshop to 09:15",
        "description": "Move session to verified morning slot.",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    # Re-instantiate a fresh EventStore pointing to the same storage path
    second_store = EventStore(storage_path=isolated_store.storage_path)
    loaded = get_proposal(second_store, prop_id)
    assert loaded is not None
    assert loaded["id"] == prop_id
    assert loaded["title"] == "Move AI Workshop to 09:15"
    assert loaded["status"] == "pending"
    assert loaded["baseline_fingerprint"] == created["baseline_fingerprint"]
    assert second_store.find_proposal(prop_id) is not None


# ===========================================================================
# 16. Phase 5B.2: Proposal Expiration Lifecycle
# ===========================================================================
def test_proposal_expiration_lifecycle(isolated_store, lead_organizer_context):
    """Expired proposals cannot be approved or rejected, and do not mutate schedule."""
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Test Expiration",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    initial_schedule = copy.deepcopy(isolated_store.all_schedule_items())

    # Manually backdate expires_at to simulate TTL expiration
    isolated_store.update_proposal(prop_id, {"expires_at": "2026-01-01T00:00:00Z"})

    # get_proposal auto-expires
    p_fetched = get_proposal(isolated_store, prop_id)
    assert p_fetched["status"] == "expired"
    assert "Expired by TTL" in p_fetched["rejection_reason"]

    # list_pending_proposals excludes expired proposals
    pending = list_pending_proposals(isolated_store)
    assert not any(p["id"] == prop_id for p in pending)

    # Attempting to execute raises ProposalExpiredError
    with pytest.raises(ProposalExpiredError) as exc_exec:
        execute_approved_proposal_by_id(isolated_store, prop_id, lead_organizer_context)
    assert "expired" in str(exc_exec.value).lower()

    # Attempting to reject raises ProposalExpiredError
    with pytest.raises(ProposalExpiredError) as exc_rej:
        reject_proposal(isolated_store, prop_id, lead_organizer_context)
    assert "expired" in str(exc_rej.value).lower()

    # Verify schedule was NOT mutated
    assert isolated_store.all_schedule_items() == initial_schedule


# ===========================================================================
# 17. Phase 5B.2: Explicit Proposal Rejection Lifecycle
# ===========================================================================
def test_proposal_explicit_rejection_lifecycle(isolated_store, lead_organizer_context):
    """Explicitly rejected proposals transition to rejected without mutating schedule and cannot be executed."""
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Move to 09:15",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    initial_schedule = copy.deepcopy(isolated_store.all_schedule_items())

    # Reject proposal
    rej_res = reject_proposal(
        isolated_store, prop_id, lead_organizer_context, reason="Speaker is in transit at 09:15"
    )
    assert rej_res["success"] is True
    assert rej_res["status"] == "rejected"
    assert rej_res["rejection_reason"] == "Speaker is in transit at 09:15"

    # Verify store record
    stored_p = isolated_store.find_proposal(prop_id)
    assert stored_p["status"] == "rejected"
    assert stored_p["resolved_by"] == lead_organizer_context.actor_id

    # Verify schedule and briefings were NOT mutated
    assert isolated_store.all_schedule_items() == initial_schedule

    # Attempting to execute rejected proposal raises ProposalRejectedError
    with pytest.raises(ProposalRejectedError) as exc_exec:
        execute_approved_proposal_by_id(isolated_store, prop_id, lead_organizer_context)
    assert "rejected" in str(exc_exec.value).lower()

    # Attempting to reject again raises InvalidProposalStateError
    with pytest.raises(InvalidProposalStateError):
        reject_proposal(isolated_store, prop_id, lead_organizer_context)

    # Verify audit event for rejection
    audit = isolated_store.find_audit_by_proposal(prop_id)
    assert audit is not None
    assert audit["action_type"] == "proposal_rejection"
    assert audit["outcome"] == "rejected"


# ===========================================================================
# 18. Phase 5B.2: Duplicate Proposal Approval Prevention
# ===========================================================================
def test_proposal_duplicate_approval_prevention(isolated_store, lead_organizer_context):
    """An approved proposal cannot be approved again (double-click / replay attack protection)."""
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Move to 09:15",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    adapter = InternalTestApprovalAdapter(lead_organizer_context)

    # First approval succeeds
    res1 = apply_approved_proposal_by_id(isolated_store, prop_id, adapter=adapter)
    assert res1["success"] is True
    assert res1["status"] == "approved"

    # Verified stored proposal status is approved
    p_stored = isolated_store.find_proposal(prop_id)
    assert p_stored["status"] == "approved"
    assert p_stored["resolved_by"] == lead_organizer_context.actor_id

    # Second approval attempt with same proposal_id fails with DuplicateProposalError
    with pytest.raises(DuplicateProposalError) as exc_dup1:
        apply_approved_proposal_by_id(isolated_store, prop_id, adapter=adapter)
    assert "already approved" in str(exc_dup1.value).lower()

    # Direct execution attempt also fails with DuplicateProposalError
    with pytest.raises(DuplicateProposalError):
        execute_approved_proposal_by_id(isolated_store, prop_id, lead_organizer_context)

    # Attempting to reject an approved proposal raises InvalidProposalStateError
    with pytest.raises(InvalidProposalStateError):
        reject_proposal(isolated_store, prop_id, lead_organizer_context)


# ===========================================================================
# 19. Phase 5B.2: Tampered Proposal and Payload Rejection
# ===========================================================================
def test_tampered_proposal_and_payload_rejection(isolated_store, lead_organizer_context):
    """Server rejects unknown proposal IDs, malformed schemas, no-ops, and conflict-inducing payloads."""
    # 1. Nonexistent proposal ID
    with pytest.raises(ProposalNotFoundError):
        execute_approved_proposal_by_id(isolated_store, "prop-nonexistent-12345", lead_organizer_context)

    # 2. Invalid mutation fields (e.g. attempting to tamper with speaker or budget)
    bad_field_candidate = {
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "speaker_honorarium", "before": "0", "after": "5000"},
        ],
    }
    with pytest.raises(InvalidProposalError) as exc_field:
        create_trusted_proposal(isolated_store, bad_field_candidate)
    assert "unsupported mutation field" in str(exc_field.value).lower()

    # 3. Invalid time format
    bad_time_candidate = {
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "25:99"},
        ],
    }
    with pytest.raises(InvalidProposalError):
        create_trusted_proposal(isolated_store, bad_time_candidate)

    # 4. Inverted time order (start >= end)
    inverted_time_candidate = {
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "15:00"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "14:00"},
        ],
    }
    with pytest.raises(InvalidProposalError):
        create_trusted_proposal(isolated_store, inverted_time_candidate)

    # 5. Non-existent schedule item
    nonexistent_item_candidate = {
        "target_schedule_id": "sch-999-fake",
        "proposed_changes": [
            {"record_id": "sch-999-fake", "field": "start_time", "before": "09:00", "after": "10:00"},
        ],
    }
    with pytest.raises(ScheduleItemNotFoundError):
        create_trusted_proposal(isolated_store, nonexistent_item_candidate)

    # 6. No-op candidate (no actual changes)
    noop_candidate = {
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:30"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:30"},
        ],
    }
    with pytest.raises(InvalidProposalError):
        create_trusted_proposal(isolated_store, noop_candidate)

    # 7. Candidate that introduces a new room overlap conflict
    # sch-005 is Morning Workshop 11:00-12:30 in Gates Hall 106. Moving sch-003 to 11:30-12:30 creates conflict!
    conflict_candidate = {
        "target_schedule_id": "sch-003",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "11:30"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "12:30"},
            {"record_id": "sch-003", "field": "room", "before": "Gates Hall 106", "after": "Gates Hall 106"},
        ],
    }
    with pytest.raises(ConflictingProposalError):
        create_trusted_proposal(isolated_store, conflict_candidate)


# ===========================================================================
# 20. Phase 5B.2: Stale Baseline Detection
# ===========================================================================
def test_stale_baseline_detection_invalidates_proposal(isolated_store, lead_organizer_context):
    """Modifying underlying schedule state invalidates earlier proposals with StaleProposalError."""
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Move to 09:15",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    # Before modification, proposal is not stale
    pending = list_pending_proposals(isolated_store)
    p_info = next(p for p in pending if p["id"] == prop_id)
    assert p_info["is_stale"] is False

    # External modification: move sch-003 to 09:20-10:20
    isolated_store.update_schedule_item("sch-003", {"start_time": "09:20", "end_time": "10:20"})

    # Now proposal is detected as stale in pending list
    pending_after = list_pending_proposals(isolated_store)
    p_info_after = next(p for p in pending_after if p["id"] == prop_id)
    assert p_info_after["is_stale"] is True

    # Attempting to execute the stale proposal fails with StaleProposalError
    adapter = InternalTestApprovalAdapter(lead_organizer_context)
    with pytest.raises(StaleProposalError) as exc_stale:
        apply_approved_proposal_by_id(isolated_store, prop_id, adapter=adapter)
    assert "stale" in str(exc_stale.value).lower()

    # Verify schedule item was NOT mutated by the stale proposal
    sch = isolated_store.find_schedule_item("sch-003")
    assert sch["start_time"] == "09:20"
    assert sch["end_time"] == "10:20"


# ===========================================================================
# 21. Phase 5B.2: Concurrent Proposal Approval Across OS Processes
# ===========================================================================
def test_concurrent_proposal_approval_across_processes(tmp_path):
    """Two independent OS processes contending to approve the same proposal_id yield 1 success and 1 duplicate rejection."""
    store_file = tmp_path / "concurrent_event_data.json"
    init_store = EventStore(storage_path=str(store_file))

    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Concurrent Proposal",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(init_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    context_dict = {
        "actor_id": "usr-lead-diya",
        "actor_name": "Diya",
        "actor_role": "lead_organizer",
        "session_id": "sess-concurrent",
        "timestamp": "2026-10-17T19:00:00Z",
        "override_confirmed_commitments": True,
        "external_confirmations_verified": True,
    }

    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    result_queue = ctx.Queue()

    p1 = ctx.Process(
        target=_concurrent_proposal_by_id_worker,
        args=(str(store_file), prop_id, context_dict, barrier, result_queue),
    )
    p2 = ctx.Process(
        target=_concurrent_proposal_by_id_worker,
        args=(str(store_file), prop_id, context_dict, barrier, result_queue),
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

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}: {results}"
    assert failures[0]["error_type"] == "DuplicateProposalError"

    # Verify final persistent state on disk
    final_store = EventStore(storage_path=str(store_file))
    final_prop = final_store.find_proposal(prop_id)
    assert final_prop["status"] == "approved"
    item = final_store.find_schedule_item("sch-003")
    assert item["start_time"] == "09:15"
    assert item["end_time"] == "10:15"

    # Exactly one schedule_mutation audit event for this proposal
    mutation_audits = [
        a for a in final_store.all_audit_events()
        if a.get("proposal_id") == prop_id and a.get("action_type") == "schedule_mutation"
    ]
    assert len(mutation_audits) == 1


# ===========================================================================
# 22. Phase 5B.2: Atomic Approval and Schedule Mutation
# ===========================================================================
def test_atomic_approval_and_schedule_mutation(isolated_store, lead_organizer_context, organizer_context):
    """Approval status, schedule mutation, briefing invalidation, and audit trail commit atomically or roll back completely."""
    # Mark sch-003 as confirmed to test confirmation authorization boundaries
    isolated_store.update_schedule_item("sch-003", {"confirmation_state": ConfirmationState.CONFIRMED.value})

    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Move Confirmed Keynote",
        "strategy": "RESCHEDULE_SESSION",
        "affects_confirmed_commitments": True,
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    initial_audits_count = len(isolated_store.all_audit_events())

    # Case 1: Non-lead organizer attempts approval on confirmed commitment -> raises ConfirmedCommitmentError
    with pytest.raises(ConfirmedCommitmentError):
        execute_approved_proposal_by_id(isolated_store, prop_id, organizer_context)

    # Verify atomic rollback: proposal is still pending, schedule unchanged, no audit added
    prop_check = isolated_store.find_proposal(prop_id)
    assert prop_check["status"] == "pending"
    sch_check = isolated_store.find_schedule_item("sch-003")
    assert sch_check["start_time"] == "09:30"
    assert len(isolated_store.all_audit_events()) == initial_audits_count

    # Case 2: Lead organizer approves with override_confirmed_commitments=True -> succeeds atomically
    res = execute_approved_proposal_by_id(isolated_store, prop_id, lead_organizer_context)
    assert res["success"] is True
    assert res["status"] == "approved"

    # Verify live store state updated
    prop_final = isolated_store.find_proposal(prop_id)
    assert prop_final["status"] == "approved"
    assert prop_final["resolved_by"] == lead_organizer_context.actor_id

    sch_final = isolated_store.find_schedule_item("sch-003")
    assert sch_final["start_time"] == "09:15"
    assert sch_final["end_time"] == "10:15"

    # Verify briefing invalidated
    briefing = isolated_store.find_briefing("brf-001")
    assert briefing["is_stale"] is True
    assert briefing["status"] == "stale"

    # Verify audit event added
    assert len(isolated_store.all_audit_events()) == initial_audits_count + 1


# ===========================================================================
# 23. Phase 5B.2: Public Authentication Boundary for Proposals
# ===========================================================================
def test_public_authentication_boundary_for_proposals(isolated_store, lead_organizer_context):
    """Public proposal entrypoints fail closed without an authenticated adapter, and enforce role authorization."""
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Auth Boundary Test",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    # 1. apply_approved_proposal_by_id with adapter=None fails closed
    with pytest.raises(UntrustedApprovalContextError) as exc_no_adapter:
        apply_approved_proposal_by_id(isolated_store, prop_id)
    assert "fails closed" in str(exc_no_adapter.value)

    # 2. apply_rejected_proposal_by_id with adapter=None fails closed
    with pytest.raises(UntrustedApprovalContextError) as exc_no_adapter_rej:
        apply_rejected_proposal_by_id(isolated_store, prop_id)
    assert "fails closed" in str(exc_no_adapter_rej.value)

    # 3. Passing non-adapter object fails closed
    with pytest.raises(UntrustedApprovalContextError):
        apply_approved_proposal_by_id(isolated_store, prop_id, adapter="not-an-adapter")

    # 4. Unauthorized role rejected
    unauthorized_context = ApprovalContext(
        actor_id="usr-guest-001",
        actor_name="Guest User",
        actor_role="attendee",
    )
    with pytest.raises(UnauthorizedApprovalError):
        execute_approved_proposal_by_id(isolated_store, prop_id, unauthorized_context)


# ===========================================================================
# 24. Phase 5B.2: Audit Integrity Across Full Proposal Lifecycle
# ===========================================================================
def test_audit_integrity_across_full_proposal_lifecycle(isolated_store, lead_organizer_context):
    """Every proposal lifecycle transition records a durable, complete audit event."""
    initial_audits = len(isolated_store.all_audit_events())

    # 1. Proposal Created
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Audit Test",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    p1 = create_trusted_proposal(isolated_store, candidate)["proposal_id"]
    aud1 = isolated_store.find_audit_by_proposal(p1)
    assert aud1 is not None
    assert aud1["action_type"] == "proposal_created"
    assert aud1["actor_id"] == "system_l3_resolver"
    assert aud1["target_id"] == "sch-003"
    assert aud1["outcome"] == "success"

    # 2. Proposal Rejected
    p2 = create_trusted_proposal(isolated_store, candidate)["proposal_id"]
    reject_proposal(isolated_store, p2, lead_organizer_context, reason="Rejected in review")
    all_audits = isolated_store.all_audit_events()
    aud2 = next(a for a in all_audits if a.get("proposal_id") == p2 and a.get("action_type") == "proposal_rejection")
    assert aud2["actor_id"] == lead_organizer_context.actor_id
    assert aud2["actor_role"] == lead_organizer_context.actor_role
    assert aud2["outcome"] == "rejected"
    assert "Rejected in review" in aud2["notes"]

    # 3. Proposal Expired
    p3 = create_trusted_proposal(isolated_store, candidate)["proposal_id"]
    expire_proposal(isolated_store, p3, reason="Test forced expiration")
    all_audits = isolated_store.all_audit_events()
    aud3 = next(a for a in all_audits if a.get("proposal_id") == p3 and a.get("action_type") == "proposal_expiration")
    assert aud3["outcome"] == "expired"
    assert "Test forced expiration" in aud3["notes"]

    # 4. Proposal Approved & Schedule Mutated
    p4 = create_trusted_proposal(isolated_store, candidate)["proposal_id"]
    execute_approved_proposal_by_id(isolated_store, p4, lead_organizer_context)
    all_audits = isolated_store.all_audit_events()
    aud4 = next(a for a in all_audits if a.get("proposal_id") == p4 and a.get("action_type") == "schedule_mutation")
    assert aud4["actor_id"] == lead_organizer_context.actor_id
    assert aud4["before_state"]["start_time"] == "09:30"
    assert aud4["after_state"]["start_time"] == "09:15"
    assert aud4["outcome"] == "success"

    # Total audit count increased by exactly 7
    assert len(isolated_store.all_audit_events()) == initial_audits + 7


# ===========================================================================
# 25. Timezone-Aware Proposal Expiration & Exact Boundary Verification
# ===========================================================================
def test_timezone_aware_proposal_expiration(isolated_store):
    """Proposal expiration correctly handles timezone offsets and exact boundary conditions."""
    from datetime import datetime, timezone, timedelta

    # 1. Exact boundary check
    ref_time = datetime(2026, 10, 17, 18, 0, 0, tzinfo=timezone.utc)
    exact_utc_str = "2026-10-17T18:00:00Z"
    assert is_proposal_expired(exact_utc_str, now=ref_time) is True

    # 1 second before boundary -> not expired
    one_sec_before = ref_time - timedelta(seconds=1)
    assert is_proposal_expired(exact_utc_str, now=one_sec_before) is False

    # 1 second after boundary -> expired
    one_sec_after = ref_time + timedelta(seconds=1)
    assert is_proposal_expired(exact_utc_str, now=one_sec_after) is True

    # 2. Timezone offset checks (Pacific Daylight Time UTC-7)
    # 11:00:00-07:00 is exactly 18:00:00 UTC
    pdt_str = "2026-10-17T11:00:00-07:00"
    assert is_proposal_expired(pdt_str, now=ref_time) is True
    assert is_proposal_expired(pdt_str, now=one_sec_before) is False
    assert is_proposal_expired(pdt_str, now=one_sec_after) is True

    # Central European Time (UTC+2): 20:00:00+02:00 is exactly 18:00:00 UTC
    cest_str = "2026-10-17T20:00:00+02:00"
    assert is_proposal_expired(cest_str, now=ref_time) is True
    assert is_proposal_expired(cest_str, now=one_sec_before) is False
    assert is_proposal_expired(cest_str, now=one_sec_after) is True

    # 3. Expiration in registry with offset timestamp
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Timezone Expiry Test",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }
    created = create_trusted_proposal(isolated_store, candidate, ttl_seconds=3600)
    prop_id = created["proposal_id"]

    # Inject an offset timestamp in the past into the proposal
    with isolated_store.transaction() as staged:
        p = next(x for x in staged["proposals"] if x["id"] == prop_id)
        p["expires_at"] = "2020-01-01T08:00:00-08:00"

    retrieved = get_proposal(isolated_store, prop_id, auto_expire=True)
    assert retrieved["status"] == "expired"


# ===========================================================================
# 26. Event ID Mismatch Rejection
# ===========================================================================
def test_event_id_mismatch_rejection(isolated_store, lead_organizer_context):
    """Proposal creation and execution fail when event_id does not match the store's event."""
    actual_event_id = isolated_store.get_event()["id"]
    candidate = {
        "target_schedule_id": "sch-003",
        "title": "Event ID Test",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
    }

    # 1. Parameter event_id mismatch
    with pytest.raises(InvalidProposalError) as exc_p:
        create_trusted_proposal(isolated_store, candidate, event_id="evt-other-hackathon")
    assert "does not match store event ID" in str(exc_p.value)

    # 2. Candidate dictionary event_id mismatch
    bad_cand = copy.deepcopy(candidate)
    bad_cand["event_id"] = "evt-foreign-event"
    with pytest.raises(InvalidProposalError) as exc_c:
        create_trusted_proposal(isolated_store, bad_cand)
    assert "does not match store event ID" in str(exc_c.value)

    # 3. Execution rejection on tampered proposal event_id
    created = create_trusted_proposal(isolated_store, candidate)
    prop_id = created["proposal_id"]
    with isolated_store.transaction() as staged:
        p = next(x for x in staged["proposals"] if x["id"] == prop_id)
        p["event_id"] = "evt-spoofed-event"

    with pytest.raises(InvalidProposalError) as exc_exec:
        execute_approved_proposal_by_id(isolated_store, prop_id, lead_organizer_context)
    assert "does not match live event ID" in str(exc_exec.value)


# ===========================================================================
# 27. Tampered L3 Proposal Detection and Rejection
# ===========================================================================
def test_tampered_l3_proposal_rejection(isolated_store):
    """Candidate proposals with conflict_id that tamper with proposed times/rooms are rejected."""
    isolated_store.add_schedule_item(
        {
            "id": "sch-tamper-001",
            "title": "Conflicting Demo Session",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Creates conflict with sch-003.",
        }
    )
    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP)
    cfl_id = room_cfl["id"]

    proposals_res = propose_conflict_resolutions(isolated_store, cfl_id)
    genuine_p = next(p for p in proposals_res["proposals"] if p["strategy"] == "RESCHEDULE_SESSION")

    # Caller tampers with the 'after' time of the genuine proposal
    tampered_cand = copy.deepcopy(genuine_p)
    # Genuine was 09:00 or similar; tamper it to an arbitrary unapproved valid time 09:15
    tampered_cand["proposed_changes"][0]["after"] = "09:15"

    with pytest.raises(TamperedProposalError) as exc_tamper:
        create_trusted_proposal(isolated_store, tampered_cand)
    assert "do not match deterministic L3 resolution options" in str(exc_tamper.value)


# ===========================================================================
# 28. Server-Side Proposal Creation Directly from Conflict
# ===========================================================================
def test_server_side_create_trusted_proposal_from_conflict(isolated_store):
    """create_trusted_proposal_from_conflict creates executable proposals directly from conflict_id."""
    isolated_store.add_schedule_item(
        {
            "id": "sch-server-gen-001",
            "title": "Server Gen Conflict Session",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Creates conflict with sch-003.",
        }
    )
    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP)
    cfl_id = room_cfl["id"]

    # Generate trusted proposal on server without passing any change dictionary
    res = create_trusted_proposal_from_conflict(isolated_store, cfl_id, strategy="RESCHEDULE_SESSION", ttl_seconds=1800)
    assert res["success"] is True
    prop_id = res["proposal_id"]
    assert prop_id.startswith("prop-")

    stored = get_proposal(isolated_store, prop_id)
    assert stored is not None
    assert stored["conflict_id"] == cfl_id
    assert stored["status"] == "pending"
    assert len(stored["proposed_changes"]) > 0


# ===========================================================================
# 29. Confirmed Commitments & External Confirmations Cannot Be Stripped
# ===========================================================================
def test_confirmed_commitment_and_external_confirmations_cannot_be_stripped(isolated_store):
    """Proposal creation enforces confirmed commitment flags and confirmations derived from store."""
    # Target item sch-003 has a confirmed speaker (spk-003 Prof. Sara Kim)
    target_item = isolated_store.find_schedule_item("sch-003")
    assert target_item is not None
    assert target_item.get("speaker_id")

    spk = isolated_store.find_speaker(target_item["speaker_id"])
    assert spk is not None
    assert spk["status"] == "confirmed"

    # Caller attempts to create candidate claiming no confirmed commitments and empty confirmations
    malicious_cand = {
        "target_schedule_id": "sch-003",
        "title": "Move Keynote Session",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-003", "field": "start_time", "before": "09:30", "after": "09:15"},
            {"record_id": "sch-003", "field": "end_time", "before": "10:30", "after": "10:15"},
        ],
        "affects_confirmed_commitments": False,  # Untrusted attempt to bypass
        "required_confirmations": [],            # Untrusted attempt to strip confirmations
    }

    created = create_trusted_proposal(isolated_store, malicious_cand)
    # Server must override caller's False and enforce True because speaker is confirmed
    assert created["preview"]["affects_confirmed_commitments"] is True
    # Server must enforce speaker confirmation in required_confirmations
    assert any("Speaker agreement" in r for r in created["preview"]["required_confirmations"])


# ===========================================================================
# 30. Active Conflict Protection: Omitted conflict_id Cannot Evade L3
# ===========================================================================
def test_omitted_conflict_id_cannot_bypass_l3_verification(isolated_store):
    """Callers targeting items in active conflicts cannot bypass L3 checks by omitting conflict_id."""
    # Keynote sch-003 is 09:30-10:30 in Gates Hall 106. Add an overlapping session:
    isolated_store.add_schedule_item(
        {
            "id": "sch-tamper-001",
            "title": "Competing Workshop",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Double booked workshop.",
        }
    )

    cfls = detect_schedule_conflicts(isolated_store).get("conflicts", [])
    active_overlap = [c for c in cfls if "sch-tamper-001" in c.get("affected_schedule_ids", [])]
    assert len(active_overlap) > 0

    # Caller attempts to create a proposal with fabricated/tampered times without passing conflict_id
    tampered_cand_no_conflict_id = {
        "target_schedule_id": "sch-tamper-001",
        "title": "Evading L3 Verification",
        "strategy": "RESCHEDULE_SESSION",
        "proposed_changes": [
            {"record_id": "sch-tamper-001", "field": "start_time", "before": "10:00", "after": "09:15"},
            {"record_id": "sch-tamper-001", "field": "end_time", "before": "11:00", "after": "10:15"},
        ],
    }

    with pytest.raises(TamperedProposalError) as exc_info:
        create_trusted_proposal(isolated_store, tampered_cand_no_conflict_id)
    assert "do not match deterministic L3 resolution options" in str(exc_info.value)
