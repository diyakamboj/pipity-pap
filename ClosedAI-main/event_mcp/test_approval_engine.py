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

from approval_engine import (
    ApprovalContext,
    ConfirmedCommitmentError,
    ConflictingProposalError,
    DuplicateProposalError,
    InternalTestApprovalAdapter,
    InvalidProposalError,
    ScheduleItemNotFoundError,
    StaleProposalError,
    UnauthorizedApprovalError,
    UntrustedApprovalContextError,
    apply_approved_schedule_change,
    execute_approved_schedule_change_transaction,
)
from event_store import ConfirmationState, EventStore
import server


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
