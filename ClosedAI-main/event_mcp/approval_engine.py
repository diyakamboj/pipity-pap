"""approval_engine: Internal approval transaction executor and audit trail manager.

Part of Phase 5A: Human-in-the-Loop (HITL) Approval Integration.

This module provides internal-only schedule mutation execution gated by a verified
ApprovalContext. It executes real, atomic database updates in EventStore, records durable
audit events, invalidates affected participant briefings, and strictly guards against:
- Untrusted callers, unverified headers, or self-declared client contexts.
- Stale proposals whose expected baseline does not match live EventStore records.
- Proposed mutations that introduce new schedule or resource conflicts.
- Unauthorized modifications to confirmed commitments without lead organizer authorization.
- Duplicate approval attempts (replay attacks / double clicks).
- Concurrency race conditions between validation and commit.

TRUST BOUNDARY & ARCHITECTURAL INVARIANTS:
1. Internal Execution Only: This module is NOT exposed as an agent-callable MCP tool.
   MCP tools remain 100% read-only.
2. Separation of Adapter and Transaction Executor:
   - ApprovalContext is an INTERNAL DATA CARRIER ONLY, NOT proof of authentication.
     Instantiating ApprovalContext from client or untrusted code does NOT confer authorization.
   - AuthenticatedApprovalAdapter defines the server-side contract for authenticating callers.
   - In Phase 5B, the Next.js API layer (/api/logistics/approve) will authenticate the user's
     session token/cookie, extract the server-verified principal and role from the database,
     and pass an authorized ApprovalContext through the adapter.
   - In Phase 5A, because no authenticated production API adapter is registered, the production
     entrypoint (apply_approved_schedule_change) FAILS CLOSED for any unadapted invocation.
3. Single-Lock Atomicity: All state-dependent checks (duplicate detection, baseline freshness,
   target lookup, conflict impact analysis, confirmed commitments) and mutations execute
   under the SAME EventStore.transaction() lock.
4. Concurrency: Synchronized by EventStore's RLock and atomic POSIX disk replacement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
import sys
import time
from typing import Any, Optional
import uuid

# Ensure sibling imports work across working directories
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conflict_engine import (
    analyze_schedule_impact,
    detect_schedule_conflicts,
    propose_conflict_resolutions,
)
from event_store import (
    AuditEvent,
    ConfirmationState,
    EventStore,
    ProposalRecord,
    ProposalStatus,
)


# ---------------------------------------------------------------------------
# Role Definitions & Allowed Mutations
# ---------------------------------------------------------------------------
AUTHORIZED_ROLES = {"lead_organizer", "organizer"}
LEAD_ROLES = {"lead_organizer"}
ALLOWED_MUTATION_FIELDS = {"start_time", "end_time", "room", "notes"}


class ApprovalEngineError(Exception):
    """Base exception for all approval engine errors."""
    pass


class UntrustedApprovalContextError(ApprovalEngineError):
    """Raised when an approval context is missing, unverified, self-declared, or from an untrusted source."""
    pass


class UnauthorizedApprovalError(ApprovalEngineError):
    """Raised when an authenticated actor lacks sufficient role authority."""
    pass


class StaleProposalError(ApprovalEngineError):
    """Raised when the schedule item's baseline state has changed since proposal generation."""
    pass


class DuplicateProposalError(ApprovalEngineError):
    """Raised when a proposal has already been executed (replay / double approval attempt)."""
    pass


class ConflictingProposalError(ApprovalEngineError):
    """Raised when the proposed change introduces newly detected schedule or resource conflicts."""
    pass


class ConfirmedCommitmentError(ApprovalEngineError):
    """Raised when modifying confirmed commitments without lead organizer authorization or external verification."""
    pass


class ScheduleItemNotFoundError(ApprovalEngineError):
    """Raised when the target schedule item does not exist in the store."""
    pass


class InvalidProposalError(ApprovalEngineError):
    """Raised when proposal schema or requested mutation fields are invalid or unsupported."""
    pass


class ProposalNotFoundError(ApprovalEngineError):
    """Raised when a requested proposal ID is not found in the persistent proposal registry."""
    pass


class ProposalExpiredError(ApprovalEngineError):
    """Raised when attempting to execute or modify an expired proposal."""
    pass


class ProposalRejectedError(ApprovalEngineError):
    """Raised when attempting to execute a proposal that was explicitly rejected."""
    pass


class InvalidProposalStateError(ApprovalEngineError):
    """Raised when a proposal is not in the required state for a requested lifecycle transition."""
    pass


class TamperedProposalError(ApprovalEngineError):
    """Raised when a proposal record fails integrity or authenticity checks."""
    pass


# ---------------------------------------------------------------------------
# 1. Approval Context (Internal Data Carrier)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ApprovalContext:
    """Internal data carrier for a server-verified principal and approval options.

    TRUST BOUNDARY SPECIFICATION:
        This class is an INTERNAL DATA CARRIER ONLY, NOT proof of authentication.
        Instantiating this class does not establish authenticity or authorization.

        In Phase 5B, only the server-side API layer (e.g. Next.js route handlers)
        will instantiate this class after cryptographically verifying session tokens,
        verifying user identities against the persistent auth store, and checking
        RBAC permissions.

        In Phase 5A, because no authenticated production API adapter is registered,
        any caller attempting to invoke production entrypoints directly with self-declared
        data fails closed.
    """
    actor_id: str
    actor_name: str
    actor_role: str
    session_id: str = ""
    timestamp: str = ""
    override_confirmed_commitments: bool = False
    external_confirmations_verified: bool = False


# ---------------------------------------------------------------------------
# 2. Authentication Adapter Contract
# ---------------------------------------------------------------------------
class AuthenticatedApprovalAdapter(ABC):
    """Abstract interface for server-side authenticated approval adapters.

    Phase 5B Integration Contract:
        In Phase 5B, this adapter will be implemented by the Next.js API route layer.
        The route handler will:
        1. Validate the caller's HTTP session cookie / Bearer token via NextAuth / iron-session.
        2. Query the user record from the database to obtain their verified role.
        3. Check RBAC permissions for logistics mutations.
        4. Return a server-authenticated ApprovalContext.
    """

    @abstractmethod
    def authenticate_and_authorize(self, request_data: Any) -> ApprovalContext:
        """Validate caller credentials and produce an authorized ApprovalContext."""
        pass


class InternalTestApprovalAdapter(AuthenticatedApprovalAdapter):
    """Internal test adapter used strictly by test harnesses.

    DOCUMENTED LIMITATION:
        This adapter is internal-only for testing transaction semantics without
        simulating or faking production authentication. It must NEVER be exposed
        to external callers or production API routes.
    """

    def __init__(self, context: ApprovalContext):
        self._context = context

    def authenticate_and_authorize(self, request_data: Any = None) -> ApprovalContext:
        return self._context


# ---------------------------------------------------------------------------
# 2.5 Time & Expiration Helpers (Timezone-Aware)
# ---------------------------------------------------------------------------
def _time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' string to minutes since midnight."""
    parts = str(time_str).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format '{time_str}', expected 'HH:MM'")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Time '{time_str}' out of range (00:00 - 23:59)")
    return h * 60 + m


def parse_iso_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware UTC datetime.

    Handles UTC 'Z', explicit offsets ('+00:00', '-07:00'), and naive strings (treated as UTC).
    """
    s = str(ts or "").strip()
    if not s:
        raise ValueError("Empty timestamp string.")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_proposal_expired(expires_at_str: str, now: datetime | None = None) -> bool:
    """Check if a proposal has expired (now >= expires_at), timezone-aware.

    Returns True if now is at or after expires_at (exact boundary inclusive).
    Fails closed (returns True) on unparseable or corrupted expiration timestamps.
    """
    s = str(expires_at_str or "").strip()
    if not s:
        return False
    try:
        expiry_dt = parse_iso_timestamp(s)
        current_dt = now if now is not None else datetime.now(timezone.utc)
        return current_dt >= expiry_dt
    except Exception:
        return True


# ---------------------------------------------------------------------------
# 3. Internal Schedule-Change Transaction Executor
# ---------------------------------------------------------------------------
def execute_approved_schedule_change_transaction(
    store: EventStore,
    proposal: dict[str, Any],
    context: ApprovalContext,
) -> dict[str, Any]:
    """Execute an approved schedule mutation within an atomic EventStore transaction.

    INTERNAL-ONLY BACKEND OPERATION.
    Requires an authorized ApprovalContext supplied by an authenticated adapter.
    NEVER exposed directly as an MCP tool.

    Validation & Execution are protected by the same single transaction lock:
    1. Pre-lock structural checks (context type, proposal format).
    2. Lock acquisition & staging (store.transaction()).
    3. Under-the-lock idempotency check: Rejects duplicate executions of previously committed proposals.
    4. Under-the-lock target item validation: Ensures target schedule ID exists in current store.
    5. Under-the-lock baseline freshness check: Compares proposal 'before' fields against current live record.
    6. Under-the-lock confirmed commitment & external confirmation check.
    7. Under-the-lock full impact recomputation: Invokes conflict engine against live store state.
    8. Under-the-lock staged schedule mutation.
    9. Under-the-lock staged briefing invalidation (draft/ready -> stale, sent -> preserved immutable).
    10. Under-the-lock staged audit trail append.
    11. Atomic commit via tempfile + fsync + os.replace.
    """
    # -----------------------------------------------------------------------
    # Step 1: Pre-Transaction Structural Validations
    # -----------------------------------------------------------------------
    if not isinstance(context, ApprovalContext):
        raise UntrustedApprovalContextError(
            "Untrusted approval context: caller did not provide a validated ApprovalContext instance."
        )

    if not context.actor_id or not context.actor_role:
        raise UntrustedApprovalContextError(
            "Untrusted approval context: missing required actor_id or actor_role."
        )

    if context.actor_role not in AUTHORIZED_ROLES:
        raise UnauthorizedApprovalError(
            f"Actor '{context.actor_id}' with role '{context.actor_role}' is not authorized to approve "
            f"schedule mutations. Requires role in {AUTHORIZED_ROLES}."
        )

    if not isinstance(proposal, dict):
        raise InvalidProposalError("Proposal must be a valid dictionary.")

    proposal_id = str(proposal.get("proposal_id", "")).strip()
    if not proposal_id:
        raise InvalidProposalError("Proposal must provide a non-empty 'proposal_id'.")

    changes = proposal.get("proposed_changes", [])
    target_id = proposal.get("target_schedule_id")
    if not target_id and changes:
        target_id = changes[0].get("record_id")

    if not target_id:
        raise InvalidProposalError("Proposal does not specify a target schedule item ID.")

    if not changes:
        raise InvalidProposalError(f"Proposal '{proposal_id}' does not contain any 'proposed_changes'.")

    for change in changes:
        field_name = change.get("field")
        if field_name not in ALLOWED_MUTATION_FIELDS:
            raise InvalidProposalError(
                f"Unsupported mutation field '{field_name}' on schedule item '{target_id}'. "
                f"Only {ALLOWED_MUTATION_FIELDS} can be modified."
            )

    # -----------------------------------------------------------------------
    # Step 2: Atomic Transaction Execution (ALL checks under SAME lock)
    # -----------------------------------------------------------------------
    with store.transaction() as staged:
        # A. Idempotency & Duplicate Rejection under lock
        existing_audit = next(
            (a for a in staged.get("audit_trail", []) if a.get("proposal_id") == proposal_id),
            None,
        )
        if existing_audit and existing_audit.get("outcome") == "success":
            raise DuplicateProposalError(
                f"Proposal '{proposal_id}' was already approved and executed at {existing_audit.get('timestamp')} "
                f"by actor '{existing_audit.get('actor_id')}'. Duplicate approval attempts are rejected."
            )

        # Check proposal registry if proposal exists there
        for reg_p in staged.get("proposals", []):
            if reg_p.get("id") == proposal_id:
                reg_status = reg_p.get("status")
                if reg_status == ProposalStatus.APPROVED.value:
                    raise DuplicateProposalError(
                        f"Proposal '{proposal_id}' was already approved and executed at {reg_p.get('resolved_at')} "
                        f"by actor '{reg_p.get('resolved_by')}'. Duplicate approval attempts are rejected."
                    )
                if reg_status == ProposalStatus.REJECTED.value:
                    raise ProposalRejectedError(
                        f"Proposal '{proposal_id}' was rejected: {reg_p.get('rejection_reason')}."
                    )
                if reg_status == ProposalStatus.EXPIRED.value or is_proposal_expired(reg_p.get("expires_at", "")):
                    raise ProposalExpiredError(
                        f"Proposal '{proposal_id}' has expired and cannot be executed."
                    )

        # B. Target Schedule Item Resolution under lock
        target_item = next(
            (item for item in staged.get("schedule", []) if item.get("id") == target_id),
            None,
        )
        if not target_item:
            raise ScheduleItemNotFoundError(f"Target schedule item '{target_id}' not found in event store.")

        # C. Baseline Freshness Comparison under lock
        for change in changes:
            field_name = change.get("field")
            expected_before = change.get("before")
            current_value = target_item.get(field_name)

            if expected_before is not None and current_value != expected_before:
                raise StaleProposalError(
                    f"Proposal baseline is stale for schedule item '{target_id}' field '{field_name}': "
                    f"current live value is '{current_value}', but proposal expected baseline '{expected_before}'. "
                    "The schedule was modified after this proposal was generated."
                )

        # Extract proposed target values
        new_start = next((c.get("after") for c in changes if c.get("field") == "start_time"), target_item.get("start_time"))
        new_end = next((c.get("after") for c in changes if c.get("field") == "end_time"), target_item.get("end_time"))
        new_room = next((c.get("after") for c in changes if c.get("field") == "room"), target_item.get("room"))
        new_notes = next((c.get("after") for c in changes if c.get("field") == "notes"), None)

        # D. Confirmed Commitment & External Confirmation Protection under lock
        is_target_confirmed = (target_item.get("confirmation_state") == ConfirmationState.CONFIRMED.value)
        affects_confirmed = is_target_confirmed or bool(proposal.get("affects_confirmed_commitments", False))

        if affects_confirmed:
            if context.actor_role not in LEAD_ROLES:
                raise ConfirmedCommitmentError(
                    f"Actor '{context.actor_id}' with role '{context.actor_role}' cannot modify confirmed "
                    f"commitment '{target_id}'. Modifying confirmed commitments requires 'lead_organizer' authority."
                )
            if not context.override_confirmed_commitments:
                raise ConfirmedCommitmentError(
                    f"Modifying confirmed commitment '{target_id}' requires explicit organizer confirmation override "
                    "(override_confirmed_commitments=True)."
                )

        req_confirmations = proposal.get("required_confirmations", [])
        if req_confirmations and not context.external_confirmations_verified:
            confirmations_str = ", ".join(req_confirmations)
            raise ConfirmedCommitmentError(
                f"Cannot apply proposal with unverified external confirmations ({confirmations_str}). "
                "Organizer must verify external confirmations before approval (external_confirmations_verified=True)."
            )

        # E. Recompute Full Live Impact & Conflict Scan under lock
        impact = analyze_schedule_impact(
            store,
            schedule_item_id=target_id,
            proposed_start=new_start,
            proposed_end=new_end,
            proposed_room=new_room,
        )

        introduced_conflicts = (
            impact.get("conflict_summary", {}).get("introduced_conflicts", [])
            or impact.get("introduced_conflicts", [])
        )
        if introduced_conflicts:

            conflict_titles = [c.get("title", c.get("id")) for c in introduced_conflicts]
            raise ConflictingProposalError(
                f"Proposal introduces {len(introduced_conflicts)} new conflict(s): {'; '.join(conflict_titles)}. "
                "Schedule changes that introduce new conflicts are rejected."
            )

        # F. Staged Schedule Mutation
        before_state = {
            "start_time": target_item.get("start_time"),
            "end_time": target_item.get("end_time"),
            "room": target_item.get("room"),
            "notes": target_item.get("notes"),
        }
        after_state = {
            "start_time": new_start,
            "end_time": new_end,
            "room": new_room,
            "notes": new_notes if new_notes is not None else target_item.get("notes"),
        }

        target_item["start_time"] = new_start
        target_item["end_time"] = new_end
        target_item["room"] = new_room
        if new_notes is not None:
            target_item["notes"] = new_notes

        # G. Staged Briefing Invalidation & History Preservation
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        stale_briefing_ids = {sb["briefing_id"] for sb in impact.get("stale_briefings", [])}
        for b in staged.get("briefings", []):
            if b.get("session_id") == target_id:
                stale_briefing_ids.add(b["id"])
            if target_item.get("speaker_id") and b.get("recipient_id") == target_item.get("speaker_id"):
                stale_briefing_ids.add(b["id"])
            if target_item.get("vendor_id") and b.get("recipient_id") == target_item.get("vendor_id"):
                stale_briefing_ids.add(b["id"])

        invalidated_briefings = []
        sent_briefings_needing_revision = []
        for b in staged.get("briefings", []):
            if b["id"] in stale_briefing_ids:
                b_status = b.get("status", "draft")
                b["is_stale"] = True
                b["updated_at"] = now_iso
                b["stale_reason"] = (
                    f"Schedule item '{target_id}' ({target_item.get('title')}) was moved to "
                    f"{new_start}-{new_end} in {new_room}."
                )
                if b_status in ("draft", "ready"):
                    b["status"] = "stale"
                elif b_status == "sent":
                    sent_briefings_needing_revision.append(b["id"])

                invalidated_briefings.append({
                    "id": b["id"],
                    "role": b.get("role"),
                    "recipient_name": b.get("recipient_name"),
                    "status": b.get("status"),
                    "is_stale": True,
                })

        # H. Preserved Operational Tasks (Verification)
        preserved_task_ids = [t["id"] for t in staged.get("tasks", [])]

        # I. Staged Audit Trail Append
        event_id = f"aud-{uuid.uuid4().hex[:12]}"
        audit_event = AuditEvent(
            event_id=event_id,
            proposal_id=proposal_id,
            action_type="schedule_mutation",
            actor_id=context.actor_id,
            actor_role=context.actor_role,
            auth_source="internal_transaction_executor",
            timestamp=now_iso,
            target_id=target_id,
            before_state=before_state,
            after_state=after_state,
            affected_records={
                "schedule_item_id": target_id,
                "invalidated_briefing_ids": [b["id"] for b in invalidated_briefings],
                "sent_briefings_needing_revision": sent_briefings_needing_revision,
                "preserved_task_ids": preserved_task_ids,
            },
            outcome="success",
            notes=(
                f"Approved schedule mutation: {target_item.get('title')} moved to "
                f"{new_start}-{new_end} in {new_room} by {context.actor_role} '{context.actor_name or context.actor_id}'."
            ),
        )
        if "audit_trail" not in staged:
            staged["audit_trail"] = []
        staged["audit_trail"].append(audit_event.to_dict())

    # Outside transaction context: commit succeeded atomically
    return {
        "success": True,
        "proposal_id": proposal_id,
        "audit_event_id": event_id,
        "target_schedule_id": target_id,
        "mutation": {
            "before": before_state,
            "after": after_state,
        },
        "invalidated_briefings": invalidated_briefings,
        "sent_briefings_needing_revision": sent_briefings_needing_revision,
        "preserved_tasks_count": len(preserved_task_ids),
        "audit_event": audit_event.to_dict(),
    }


# ---------------------------------------------------------------------------
# 4. Public / Future API Entrypoint (Fails Closed in Phase 5A)
# ---------------------------------------------------------------------------
def apply_approved_schedule_change(
    store: EventStore,
    proposal: dict[str, Any],
    approval_context: Any = None,
    *,
    adapter: AuthenticatedApprovalAdapter | None = None,
) -> dict[str, Any]:
    """Public entrypoint for applying an approved schedule change.

    PHASE 5A TRUST BOUNDARY:
    In Phase 5A, no production authenticated API adapter is registered.
    Any attempt to call this function directly with a self-declared ApprovalContext,
    arbitrary dictionary (e.g. {"approved": True}), spoofed headers, or unauthenticated
    input FAILS CLOSED with UntrustedApprovalContextError.

    To execute a change in Phase 5A test suites, the caller must supply an explicit
    InternalTestApprovalAdapter. In Phase 5B, this entrypoint will be wired to the
    production AuthenticatedApprovalAdapter that validates Next.js HTTP session tokens.
    """
    if adapter is None:
        raise UntrustedApprovalContextError(
            "Production mutation entrypoint fails closed in Phase 5A: No authenticated server API adapter "
            "is registered. Callers cannot self-declare authorization by passing an ApprovalContext, "
            "arbitrary headers, or boolean flags. Production schedule mutations require server-side session "
            "authentication scheduled for Phase 5B."
        )

    if not isinstance(adapter, AuthenticatedApprovalAdapter):
        raise UntrustedApprovalContextError(
            "Invalid approval adapter: adapter must implement AuthenticatedApprovalAdapter."
        )

    verified_context = adapter.authenticate_and_authorize(approval_context)
    return execute_approved_schedule_change_transaction(store, proposal, verified_context)


# ---------------------------------------------------------------------------
# 5. Baseline Fingerprinting
# ---------------------------------------------------------------------------
def compute_schedule_baseline_fingerprint(item: dict[str, Any]) -> str:
    """Generate a deterministic SHA256 digest representing the baseline schedule state.

    Includes identity, timing, room, speaker/vendor bindings, and confirmation state.
    Any external change to these fields invalidates stale proposals.
    """
    parts = [
        str(item.get("id", "")),
        str(item.get("start_time", "")),
        str(item.get("end_time", "")),
        str(item.get("room", "")),
        str(item.get("speaker_id") or ""),
        str(item.get("vendor_id") or ""),
        str(item.get("confirmation_state", "")),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 6. Trusted Proposal Creation (Server-Owned L3 Registry)
# ---------------------------------------------------------------------------
def create_trusted_proposal(
    store: EventStore,
    candidate_proposal: dict[str, Any],
    *,
    event_id: str | None = None,
    ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Accept and validate a deterministic L3 resolution proposal, persisting it server-side.

    INVARIANTS:
    1. Structure and event association are validated against live store records.
    2. Proposed changes must be internally consistent, valid, and conflict-free.
    3. An opaque proposal ID is generated and stored with baseline schedule fingerprints.
    4. Client/LLM payloads are never trusted as executable changes; only the server-stored
       record identified by proposal_id can ever be executed.
    5. Returns a proposal ID and safe preview.
    """
    if not isinstance(candidate_proposal, dict):
        raise InvalidProposalError("Candidate proposal must be a valid dictionary.")

    changes = candidate_proposal.get("proposed_changes")
    if not isinstance(changes, list) or not changes:
        raise InvalidProposalError("Candidate proposal must contain a non-empty list of 'proposed_changes'.")

    target_id = candidate_proposal.get("target_schedule_id") or changes[0].get("record_id")
    if not target_id:
        raise InvalidProposalError("Candidate proposal must specify a target schedule item ID.")

    for change in changes:
        if change.get("record_id") != target_id:
            raise InvalidProposalError(
                f"Inconsistent proposed changes: change targets record '{change.get('record_id')}', "
                f"expected target '{target_id}'."
            )
        field_name = change.get("field")
        if field_name not in ALLOWED_MUTATION_FIELDS:
            raise InvalidProposalError(
                f"Unsupported mutation field '{field_name}'. Only {ALLOWED_MUTATION_FIELDS} are allowed."
            )
        if field_name in ("start_time", "end_time"):
            val = str(change.get("after", "")).strip()
            try:
                _time_to_minutes(val)
            except Exception as e:
                raise InvalidProposalError(f"Invalid time format '{val}' for field '{field_name}': {e}") from e

    with store.transaction() as staged:
        target_item = next(
            (item for item in staged.get("schedule", []) if item.get("id") == target_id),
            None,
        )
        if not target_item:
            raise ScheduleItemNotFoundError(
                f"Target schedule item '{target_id}' not found in event store."
            )

        # Baseline check: verify before values match live item
        for change in changes:
            field_name = change.get("field")
            expected_before = change.get("before")
            current_val = target_item.get(field_name)
            if expected_before is not None and current_val != expected_before:
                raise StaleProposalError(
                    f"Candidate proposal baseline is stale for schedule item '{target_id}' field '{field_name}': "
                    f"current live value is '{current_val}', but proposal expected baseline '{expected_before}'."
                )

        new_start = next((c.get("after") for c in changes if c.get("field") == "start_time"), target_item.get("start_time"))
        new_end = next((c.get("after") for c in changes if c.get("field") == "end_time"), target_item.get("end_time"))
        new_room = next((c.get("after") for c in changes if c.get("field") == "room"), target_item.get("room"))
        new_notes = next((c.get("after") for c in changes if c.get("field") == "notes"), None)

        if _time_to_minutes(new_start) >= _time_to_minutes(new_end):
            raise InvalidProposalError(
                f"Proposed start time '{new_start}' must be strictly before end time '{new_end}'."
            )

        # Ensure not a no-op
        if (
            new_start == target_item.get("start_time")
            and new_end == target_item.get("end_time")
            and new_room == target_item.get("room")
            and (new_notes is None or new_notes == target_item.get("notes"))
        ):
            raise InvalidProposalError(
                f"Candidate proposal proposes no net changes to schedule item '{target_id}'."
            )

        actual_event_id = staged.get("event", {}).get("id")
        if actual_event_id:
            if event_id and event_id != actual_event_id:
                raise InvalidProposalError(
                    f"Proposal event_id '{event_id}' does not match store event ID '{actual_event_id}'."
                )
            cand_event_id = candidate_proposal.get("event_id")
            if cand_event_id and cand_event_id != actual_event_id:
                raise InvalidProposalError(
                    f"Candidate proposal event_id '{cand_event_id}' does not match store event ID '{actual_event_id}'."
                )
        evt_id = actual_event_id or event_id or "evt-001"

        # If conflict_id is provided or target item is involved in an active conflict, verify against L3
        conflict_id = candidate_proposal.get("conflict_id")
        if not conflict_id:
            try:
                active_conflicts = detect_schedule_conflicts(store).get("conflicts", [])
                for cfl in active_conflicts:
                    if target_id in cfl.get("affected_schedule_ids", []):
                        conflict_id = cfl.get("id")
                        break
            except Exception:
                pass

        if conflict_id:
            resolutions = propose_conflict_resolutions(store, conflict_id)
            if not resolutions.get("proposals"):
                raise TamperedProposalError(
                    f"Conflict '{conflict_id}' is not an active detectable conflict in the event store."
                )
            matched = False
            for det_p in resolutions["proposals"]:
                det_changes = det_p.get("proposed_changes") or []
                det_target = det_p.get("target_schedule_id") or (
                    det_changes[0].get("record_id") if det_changes else None
                )
                if (
                    det_target == target_id
                    and det_p.get("strategy") == candidate_proposal.get("strategy", det_p.get("strategy"))
                ):
                    if len(det_changes) == len(changes):
                        changes_match = True
                        for dc, cc in zip(det_changes, changes):
                            if (
                                dc.get("record_id") != cc.get("record_id")
                                or dc.get("field") != cc.get("field")
                                or dc.get("after") != cc.get("after")
                            ):
                                changes_match = False
                                break
                        if changes_match:
                            matched = True
                            break
            if not matched:
                raise TamperedProposalError(
                    f"Candidate proposal changes for conflict '{conflict_id}' do not match deterministic "
                    f"L3 resolution options. Tampered proposal payloads are rejected."
                )

        # Verify no introduced conflicts
        impact = analyze_schedule_impact(
            store,
            schedule_item_id=target_id,
            proposed_start=new_start,
            proposed_end=new_end,
            proposed_room=new_room,
        )
        introduced_conflicts = (
            impact.get("conflict_summary", {}).get("introduced_conflicts", [])
            or impact.get("introduced_conflicts", [])
        )
        if introduced_conflicts:
            conflict_titles = [c.get("title", c.get("id")) for c in introduced_conflicts]
            raise ConflictingProposalError(
                f"Candidate proposal introduces {len(introduced_conflicts)} new conflict(s): {'; '.join(conflict_titles)}."
            )

        baseline_fingerprint = compute_schedule_baseline_fingerprint(target_item)
        proposal_id = f"prop-{uuid.uuid4().hex[:12]}"

        now_t = time.time()
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_t))
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_t + ttl_seconds))

        # Reliably derive confirmed commitment impact and required confirmations from live records
        is_target_confirmed = (target_item.get("confirmation_state") == ConfirmationState.CONFIRMED.value)
        spk_confirmed = False
        spk_name = ""
        if target_item.get("speaker_id"):
            spk = next((s for s in staged.get("speakers", []) if s.get("id") == target_item.get("speaker_id")), None)
            if spk and spk.get("status") == "confirmed":
                spk_confirmed = True
                spk_name = spk.get("name", "")

        vnd_confirmed = False
        vnd_name = ""
        if target_item.get("vendor_id"):
            vnd = next((v for v in staged.get("vendors", []) if v.get("id") == target_item.get("vendor_id")), None)
            if vnd and vnd.get("confirmed") is True:
                vnd_confirmed = True
                vnd_name = vnd.get("name", "")

        affects_confirmed = (
            is_target_confirmed
            or spk_confirmed
            or vnd_confirmed
            or bool(candidate_proposal.get("affects_confirmed_commitments", False))
        )

        req_confirmations = list(candidate_proposal.get("required_confirmations", []))
        if spk_confirmed and spk_name:
            spk_req = f"Speaker agreement from {spk_name}"
            if not any(spk_req.lower() in r.lower() for r in req_confirmations):
                req_confirmations.append(spk_req)
        if vnd_confirmed and vnd_name:
            vnd_req = f"Written confirmation from {vnd_name}"
            if not any(vnd_req.lower() in r.lower() for r in req_confirmations):
                req_confirmations.append(vnd_req)

        proposal_record = ProposalRecord(
            id=proposal_id,
            event_id=evt_id,
            target_schedule_id=target_id,
            proposed_changes=changes,
            title=candidate_proposal.get("title") or f"Move '{target_item.get('title')}' to {new_start}-{new_end}",
            description=candidate_proposal.get("description", ""),
            strategy=candidate_proposal.get("strategy", "RESCHEDULE_SESSION"),
            conflict_id=conflict_id,
            baseline_fingerprint=baseline_fingerprint,
            created_at=created_at,
            expires_at=expires_at,
            status=ProposalStatus.PENDING.value,
            resolves_conflicts=list(candidate_proposal.get("resolves_conflicts", [])),
            potential_new_conflicts=[],
            downstream_task_impacts=[
                t["title"] for t in impact.get("affected_operational_tasks", {}).get("directly_linked_tasks", [])
            ] if "affected_operational_tasks" in impact else list(candidate_proposal.get("downstream_task_impacts", [])),
            downstream_briefing_impacts=[
                f"{b.get('role')} briefing ({b.get('recipient_name')})" for b in impact.get("stale_briefings", [])
            ] if "stale_briefings" in impact else list(candidate_proposal.get("downstream_briefing_impacts", [])),
            required_confirmations=req_confirmations,
            affects_confirmed_commitments=affects_confirmed,
            requires_human_approval=True,
            metadata=copy.deepcopy(candidate_proposal.get("metadata", {})),
        )

        if "proposals" not in staged:
            staged["proposals"] = []
        staged["proposals"].append(proposal_record.to_dict())

        # Audit record
        aud_id = f"aud-{uuid.uuid4().hex[:12]}"
        audit_event = AuditEvent(
            event_id=aud_id,
            proposal_id=proposal_id,
            action_type="proposal_created",
            actor_id="system_l3_resolver",
            actor_role="system",
            auth_source="trusted_proposal_registry",
            timestamp=created_at,
            target_id=target_id,
            before_state={"baseline_fingerprint": baseline_fingerprint},
            after_state={"status": ProposalStatus.PENDING.value, "expires_at": expires_at},
            affected_records={"proposal_id": proposal_id, "target_schedule_id": target_id},
            outcome="success",
            notes=f"Created trusted proposal '{proposal_id}' for '{target_item.get('title')}' with TTL {ttl_seconds}s.",
        )
        if "audit_trail" not in staged:
            staged["audit_trail"] = []
        staged["audit_trail"].append(audit_event.to_dict())

    return {
        "success": True,
        "proposal_id": proposal_id,
        "event_id": evt_id,
        "status": ProposalStatus.PENDING.value,
        "created_at": created_at,
        "expires_at": expires_at,
        "baseline_fingerprint": baseline_fingerprint,
        "preview": {
            "title": proposal_record.title,
            "description": proposal_record.description,
            "strategy": proposal_record.strategy,
            "target_schedule_id": target_id,
            "target_title": target_item.get("title", ""),
            "changes": [
                {
                    "field": c.get("field"),
                    "before": c.get("before"),
                    "after": c.get("after"),
                }
                for c in proposal_record.proposed_changes
            ],
            "resolves_conflicts": proposal_record.resolves_conflicts,
            "downstream_impacts": {
                "tasks": proposal_record.downstream_task_impacts,
                "briefings": proposal_record.downstream_briefing_impacts,
            },
            "required_confirmations": proposal_record.required_confirmations,
            "affects_confirmed_commitments": proposal_record.affects_confirmed_commitments,
        },
    }


def create_trusted_proposal_from_conflict(
    store: EventStore,
    conflict_id: str,
    *,
    proposal_index: int = 0,
    strategy: str | None = None,
    ttl_seconds: int = 3600,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Generate and persist a trusted proposal directly from deterministic L3 conflict resolution.

    SERVER-GENERATED PROPOSAL CREATION:
    The caller supplies ONLY the conflict_id (and optional proposal_index/strategy).
    The server independently invokes propose_conflict_resolutions(), selects the deterministic
    L3 proposal, and commits it into the persistent proposal registry.
    This guarantees that untrusted clients and LLMs can NEVER supply arbitrary times, rooms,
    or changes to create executable proposals.
    """
    conflict_id = str(conflict_id or "").strip()
    if not conflict_id:
        raise InvalidProposalError("Must provide a non-empty conflict_id.")

    resolutions = propose_conflict_resolutions(store, conflict_id)
    if not resolutions.get("proposals"):
        err_msg = resolutions.get("error") or f"No deterministic L3 resolution proposals found for conflict '{conflict_id}'."
        raise InvalidProposalError(err_msg)

    cfl_proposals = resolutions["proposals"]
    if strategy:
        matching = [p for p in cfl_proposals if p.get("strategy") == strategy]
        if not matching:
            raise InvalidProposalError(
                f"No proposal with strategy '{strategy}' found for conflict '{conflict_id}'. "
                f"Available strategies: {[p.get('strategy') for p in cfl_proposals]}"
            )
        candidate = matching[0]
    else:
        if proposal_index < 0 or proposal_index >= len(cfl_proposals):
            raise InvalidProposalError(
                f"Proposal index {proposal_index} out of range for conflict '{conflict_id}' "
                f"(found {len(cfl_proposals)} proposals)."
            )
        candidate = cfl_proposals[proposal_index]

    return create_trusted_proposal(
        store,
        candidate,
        event_id=event_id,
        ttl_seconds=ttl_seconds,
    )


# ---------------------------------------------------------------------------
# 7. Proposal Lifecycle Operations
# ---------------------------------------------------------------------------
def get_proposal(
    store: EventStore,
    proposal_id: str,
    auto_expire: bool = True,
) -> dict[str, Any] | None:
    """Retrieve a proposal from the registry by ID.

    If auto_expire is True and the proposal's expires_at timestamp has passed,
    it is atomically transitioned to 'expired' and the expired record is returned.
    """
    proposal_id = str(proposal_id or "").strip()
    if not proposal_id:
        return None

    proposal = store.find_proposal(proposal_id)
    if not proposal:
        return None

    if auto_expire and proposal.get("status") == ProposalStatus.PENDING.value:
        expires_at = proposal.get("expires_at", "")
        if expires_at and is_proposal_expired(expires_at):
            try:
                expire_proposal(store, proposal_id, reason="Expired by TTL")
                proposal = store.find_proposal(proposal_id)
            except Exception:
                pass

    return copy.deepcopy(proposal)


def list_pending_proposals(
    store: EventStore,
    event_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all currently pending proposals, expiring any whose TTL has passed.

    Annotates each pending proposal with 'is_stale' indicating whether the
    live schedule item still matches the proposal's baseline fingerprint.
    """
    all_props = store.all_proposals()
    pending_list: list[dict[str, Any]] = []

    for p in all_props:
        if p.get("status") != ProposalStatus.PENDING.value:
            continue

        p_id = p.get("id")
        expires_at = p.get("expires_at", "")
        if expires_at and is_proposal_expired(expires_at):
            try:
                expire_proposal(store, p_id, reason="Expired by TTL")
            except Exception:
                pass
            continue

        if event_id and p.get("event_id") != event_id:
            continue

        target_id = p.get("target_schedule_id")
        target_item = store.find_schedule_item(target_id)
        if target_item:
            current_fp = compute_schedule_baseline_fingerprint(target_item)
            expected_fp = p.get("baseline_fingerprint")
            p["is_stale"] = (current_fp != expected_fp)
        else:
            p["is_stale"] = True

        pending_list.append(copy.deepcopy(p))

    return pending_list


def reject_proposal(
    store: EventStore,
    proposal_id: str,
    context: ApprovalContext,
    reason: str = "",
) -> dict[str, Any]:
    """Explicitly reject a proposal in the registry.

    Lifecycle Invariant:
    Rejection transitions proposal status from 'pending' to 'rejected'.
    Does NOT mutate schedule items or briefings.
    """
    if not isinstance(context, ApprovalContext):
        raise UntrustedApprovalContextError(
            "Untrusted approval context: caller did not provide a validated ApprovalContext instance."
        )

    if not context.actor_id or not context.actor_role:
        raise UntrustedApprovalContextError(
            "Untrusted approval context: missing required actor_id or actor_role."
        )

    if context.actor_role not in AUTHORIZED_ROLES:
        raise UnauthorizedApprovalError(
            f"Actor '{context.actor_id}' with role '{context.actor_role}' is not authorized to reject "
            f"proposals. Requires role in {AUTHORIZED_ROLES}."
        )

    proposal_id = str(proposal_id or "").strip()
    if not proposal_id:
        raise InvalidProposalError("Must provide a non-empty proposal_id.")

    with store.transaction() as staged:
        proposal = next(
            (p for p in staged.get("proposals", []) if p.get("id") == proposal_id),
            None,
        )
        if not proposal:
            raise ProposalNotFoundError(
                f"Proposal '{proposal_id}' not found in persistent proposal registry."
            )

        current_status = proposal.get("status", ProposalStatus.PENDING.value)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if current_status == ProposalStatus.APPROVED.value:
            raise InvalidProposalStateError(
                f"Cannot reject proposal '{proposal_id}': proposal has already been approved and executed."
            )
        if current_status == ProposalStatus.REJECTED.value:
            raise InvalidProposalStateError(
                f"Proposal '{proposal_id}' is already rejected."
            )
        if current_status == ProposalStatus.EXPIRED.value:
            raise ProposalExpiredError(
                f"Cannot reject proposal '{proposal_id}': proposal has expired."
            )

        expires_at = proposal.get("expires_at", "")
        if expires_at and is_proposal_expired(expires_at):
            proposal["status"] = ProposalStatus.EXPIRED.value
            proposal["resolved_at"] = now_iso
            proposal["rejection_reason"] = "Proposal expired by TTL before rejection"
            aud_id = f"aud-{uuid.uuid4().hex[:12]}"
            staged["audit_trail"].append(
                AuditEvent(
                    event_id=aud_id,
                    proposal_id=proposal_id,
                    action_type="proposal_expired",
                    actor_id="system",
                    actor_role="system",
                    auth_source="ttl_enforcer",
                    timestamp=now_iso,
                    target_id=proposal.get("target_schedule_id", ""),
                    outcome="expired",
                    notes="Proposal expired by TTL before rejection.",
                ).to_dict()
            )
            raise ProposalExpiredError(
                f"Proposal '{proposal_id}' expired at {expires_at}."
            )

        if current_status != ProposalStatus.PENDING.value:
            raise InvalidProposalStateError(
                f"Proposal '{proposal_id}' is in unexpected state '{current_status}'. Expected 'pending'."
            )

        rejection_reason = reason.strip() or f"Rejected by {context.actor_role} '{context.actor_name or context.actor_id}'"
        proposal["status"] = ProposalStatus.REJECTED.value
        proposal["rejection_reason"] = rejection_reason
        proposal["resolved_at"] = now_iso
        proposal["resolved_by"] = context.actor_id

        event_id = f"aud-{uuid.uuid4().hex[:12]}"
        audit_event = AuditEvent(
            event_id=event_id,
            proposal_id=proposal_id,
            action_type="proposal_rejection",
            actor_id=context.actor_id,
            actor_role=context.actor_role,
            auth_source="internal_proposal_registry",
            timestamp=now_iso,
            target_id=proposal.get("target_schedule_id", ""),
            outcome="rejected",
            notes=rejection_reason,
        )
        if "audit_trail" not in staged:
            staged["audit_trail"] = []
        staged["audit_trail"].append(audit_event.to_dict())

    return {
        "success": True,
        "proposal_id": proposal_id,
        "status": "rejected",
        "rejection_reason": rejection_reason,
        "audit_event_id": event_id,
        "audit_event": audit_event.to_dict(),
    }


def expire_proposal(
    store: EventStore,
    proposal_id: str,
    reason: str = "Expired by TTL",
) -> dict[str, Any]:
    """Expire a proposal in the registry.

    Lifecycle Invariant:
    Transitions proposal from 'pending' to 'expired'.
    Does NOT mutate schedule items or briefings.
    """
    proposal_id = str(proposal_id or "").strip()
    if not proposal_id:
        raise InvalidProposalError("Must provide a non-empty proposal_id.")

    with store.transaction() as staged:
        proposal = next(
            (p for p in staged.get("proposals", []) if p.get("id") == proposal_id),
            None,
        )
        if not proposal:
            raise ProposalNotFoundError(
                f"Proposal '{proposal_id}' not found in persistent proposal registry."
            )

        current_status = proposal.get("status", ProposalStatus.PENDING.value)
        if current_status != ProposalStatus.PENDING.value:
            raise InvalidProposalStateError(
                f"Cannot expire proposal '{proposal_id}' in state '{current_status}'. Expected 'pending'."
            )

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        proposal["status"] = ProposalStatus.EXPIRED.value
        proposal["rejection_reason"] = reason
        proposal["resolved_at"] = now_iso

        event_id = f"aud-{uuid.uuid4().hex[:12]}"
        audit_event = AuditEvent(
            event_id=event_id,
            proposal_id=proposal_id,
            action_type="proposal_expiration",
            actor_id="system",
            actor_role="system",
            auth_source="ttl_enforcer",
            timestamp=now_iso,
            target_id=proposal.get("target_schedule_id", ""),
            outcome="expired",
            notes=f"Proposal '{proposal_id}' marked expired: {reason}",
        )
        if "audit_trail" not in staged:
            staged["audit_trail"] = []
        staged["audit_trail"].append(audit_event.to_dict())

    return {
        "success": True,
        "proposal_id": proposal_id,
        "status": "expired",
        "rejection_reason": reason,
        "audit_event_id": event_id,
        "audit_event": audit_event.to_dict(),
    }


def execute_approved_proposal_by_id(
    store: EventStore,
    proposal_id: str,
    context: ApprovalContext,
) -> dict[str, Any]:
    """Execute an approved proposal by proposal ID within an atomic EventStore transaction.

    SERVER-OWNED PROPOSAL EXECUTION (Phase 5B.2):
    The caller supplies ONLY the proposal_id and a server-verified ApprovalContext.
    All proposed changes, baseline states, and target items are retrieved directly
    from the durable server-side proposal registry. The client CANNOT alter times,
    rooms, baseline values, or approval states.
    """
    if not isinstance(context, ApprovalContext):
        raise UntrustedApprovalContextError(
            "Untrusted approval context: caller did not provide a validated ApprovalContext instance."
        )

    if not context.actor_id or not context.actor_role:
        raise UntrustedApprovalContextError(
            "Untrusted approval context: missing required actor_id or actor_role."
        )

    if context.actor_role not in AUTHORIZED_ROLES:
        raise UnauthorizedApprovalError(
            f"Actor '{context.actor_id}' with role '{context.actor_role}' is not authorized to approve "
            f"schedule mutations. Requires role in {AUTHORIZED_ROLES}."
        )

    proposal_id = str(proposal_id or "").strip()
    if not proposal_id:
        raise InvalidProposalError("Must provide a non-empty proposal_id.")

    with store.transaction() as staged:
        # 1. Lookup in proposal registry
        proposal = next(
            (p for p in staged.get("proposals", []) if p.get("id") == proposal_id),
            None,
        )
        if not proposal:
            raise ProposalNotFoundError(
                f"Proposal '{proposal_id}' not found in persistent proposal registry."
            )

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        current_status = proposal.get("status", ProposalStatus.PENDING.value)

        # 2. Status verification
        if current_status == ProposalStatus.APPROVED.value:
            raise DuplicateProposalError(
                f"Proposal '{proposal_id}' was already approved and executed at {proposal.get('resolved_at')} "
                f"by actor '{proposal.get('resolved_by')}'. Duplicate approval attempts are rejected."
            )

        if current_status == ProposalStatus.REJECTED.value:
            raise ProposalRejectedError(
                f"Proposal '{proposal_id}' has been rejected ({proposal.get('rejection_reason')}) "
                "and cannot be executed."
            )

        if current_status == ProposalStatus.EXPIRED.value:
            raise ProposalExpiredError(
                f"Proposal '{proposal_id}' has expired ({proposal.get('rejection_reason')}) "
                "and cannot be executed."
            )

        # Check TTL expiration
        expires_at = proposal.get("expires_at", "")
        if expires_at and is_proposal_expired(expires_at):
            proposal["status"] = ProposalStatus.EXPIRED.value
            proposal["resolved_at"] = now_iso
            proposal["rejection_reason"] = "Proposal expired by TTL before execution"
            aud_id = f"aud-{uuid.uuid4().hex[:12]}"
            exp_audit = AuditEvent(
                event_id=aud_id,
                proposal_id=proposal_id,
                action_type="proposal_expired",
                actor_id="system",
                actor_role="system",
                auth_source="ttl_enforcer",
                timestamp=now_iso,
                target_id=proposal.get("target_schedule_id", ""),
                outcome="expired",
                notes="Proposal expired by TTL before execution.",
            )
            if "audit_trail" not in staged:
                staged["audit_trail"] = []
            staged["audit_trail"].append(exp_audit.to_dict())
            raise ProposalExpiredError(
                f"Proposal '{proposal_id}' expired at {expires_at} and cannot be executed."
            )

        if current_status != ProposalStatus.PENDING.value:
            raise InvalidProposalStateError(
                f"Proposal '{proposal_id}' is in state '{current_status}', expected 'pending'."
            )

        # Event ID association check
        actual_event_id = staged.get("event", {}).get("id")
        if actual_event_id and proposal.get("event_id") and proposal.get("event_id") != actual_event_id:
            raise InvalidProposalError(
                f"Proposal event_id '{proposal.get('event_id')}' does not match live event ID '{actual_event_id}'."
            )

        # 3. Target schedule item resolution
        target_id = proposal.get("target_schedule_id")
        target_item = next(
            (item for item in staged.get("schedule", []) if item.get("id") == target_id),
            None,
        )
        if not target_item:
            raise ScheduleItemNotFoundError(
                f"Target schedule item '{target_id}' not found in event store."
            )

        # 4. Baseline freshness & fingerprint verification
        current_fp = compute_schedule_baseline_fingerprint(target_item)
        expected_fp = proposal.get("baseline_fingerprint")
        if expected_fp and current_fp != expected_fp:
            raise StaleProposalError(
                f"Proposal baseline is stale for schedule item '{target_id}': schedule state was modified "
                f"after proposal generation (expected baseline fingerprint '{expected_fp}', "
                f"current '{current_fp}')."
            )

        changes = proposal.get("proposed_changes", [])
        if not changes:
            raise InvalidProposalError(f"Proposal '{proposal_id}' does not contain any 'proposed_changes'.")

        for change in changes:
            field_name = change.get("field")
            expected_before = change.get("before")
            current_value = target_item.get(field_name)
            if expected_before is not None and current_value != expected_before:
                raise StaleProposalError(
                    f"Proposal baseline is stale for schedule item '{target_id}' field '{field_name}': "
                    f"current live value is '{current_value}', but proposal expected baseline '{expected_before}'. "
                    "The schedule was modified after this proposal was generated."
                )

        new_start = next((c.get("after") for c in changes if c.get("field") == "start_time"), target_item.get("start_time"))
        new_end = next((c.get("after") for c in changes if c.get("field") == "end_time"), target_item.get("end_time"))
        new_room = next((c.get("after") for c in changes if c.get("field") == "room"), target_item.get("room"))
        new_notes = next((c.get("after") for c in changes if c.get("field") == "notes"), None)

        # 5. Confirmed commitment & external confirmation protection
        is_target_confirmed = (target_item.get("confirmation_state") == ConfirmationState.CONFIRMED.value)
        affects_confirmed = is_target_confirmed or bool(proposal.get("affects_confirmed_commitments", False))

        if affects_confirmed:
            if context.actor_role not in LEAD_ROLES:
                raise ConfirmedCommitmentError(
                    f"Actor '{context.actor_id}' with role '{context.actor_role}' cannot modify confirmed "
                    f"commitment '{target_id}'. Modifying confirmed commitments requires 'lead_organizer' authority."
                )
            if not context.override_confirmed_commitments:
                raise ConfirmedCommitmentError(
                    f"Modifying confirmed commitment '{target_id}' requires explicit organizer confirmation override "
                    "(override_confirmed_commitments=True)."
                )

        req_confirmations = proposal.get("required_confirmations", [])
        if req_confirmations and not context.external_confirmations_verified:
            confirmations_str = ", ".join(req_confirmations)
            raise ConfirmedCommitmentError(
                f"Cannot apply proposal with unverified external confirmations ({confirmations_str}). "
                "Organizer must verify external confirmations before approval (external_confirmations_verified=True)."
            )

        # 6. Recompute live impact and conflicts under lock
        impact = analyze_schedule_impact(
            store,
            schedule_item_id=target_id,
            proposed_start=new_start,
            proposed_end=new_end,
            proposed_room=new_room,
        )
        introduced_conflicts = (
            impact.get("conflict_summary", {}).get("introduced_conflicts", [])
            or impact.get("introduced_conflicts", [])
        )
        if introduced_conflicts:
            conflict_titles = [c.get("title", c.get("id")) for c in introduced_conflicts]
            raise ConflictingProposalError(
                f"Proposal introduces {len(introduced_conflicts)} new conflict(s): {'; '.join(conflict_titles)}. "
                "Schedule changes that introduce new conflicts are rejected."
            )

        # 7. Staged schedule mutation
        before_state = {
            "start_time": target_item.get("start_time"),
            "end_time": target_item.get("end_time"),
            "room": target_item.get("room"),
            "notes": target_item.get("notes"),
        }
        after_state = {
            "start_time": new_start,
            "end_time": new_end,
            "room": new_room,
            "notes": new_notes if new_notes is not None else target_item.get("notes"),
        }
        target_item["start_time"] = new_start
        target_item["end_time"] = new_end
        target_item["room"] = new_room
        if new_notes is not None:
            target_item["notes"] = new_notes

        # 8. Staged briefing invalidations
        stale_briefing_ids = {sb["briefing_id"] for sb in impact.get("stale_briefings", [])}
        for b in staged.get("briefings", []):
            if b.get("session_id") == target_id:
                stale_briefing_ids.add(b["id"])
            if target_item.get("speaker_id") and b.get("recipient_id") == target_item.get("speaker_id"):
                stale_briefing_ids.add(b["id"])
            if target_item.get("vendor_id") and b.get("recipient_id") == target_item.get("vendor_id"):
                stale_briefing_ids.add(b["id"])

        invalidated_briefings = []
        sent_briefings_needing_revision = []
        for b in staged.get("briefings", []):
            if b["id"] in stale_briefing_ids:
                b_status = b.get("status", "draft")
                b["is_stale"] = True
                b["updated_at"] = now_iso
                b["stale_reason"] = (
                    f"Schedule item '{target_id}' ({target_item.get('title')}) was moved to "
                    f"{new_start}-{new_end} in {new_room}."
                )
                if b_status in ("draft", "ready"):
                    b["status"] = "stale"
                elif b_status == "sent":
                    sent_briefings_needing_revision.append(b["id"])

                invalidated_briefings.append({
                    "id": b["id"],
                    "role": b.get("role"),
                    "recipient_name": b.get("recipient_name"),
                    "status": b.get("status"),
                    "is_stale": True,
                })

        preserved_task_ids = [t["id"] for t in staged.get("tasks", [])]

        # 9. Update proposal status in registry atomically
        proposal["status"] = ProposalStatus.APPROVED.value
        proposal["resolved_at"] = now_iso
        proposal["resolved_by"] = context.actor_id

        # 10. Append audit record
        event_id = f"aud-{uuid.uuid4().hex[:12]}"
        audit_event = AuditEvent(
            event_id=event_id,
            proposal_id=proposal_id,
            action_type="schedule_mutation",
            actor_id=context.actor_id,
            actor_role=context.actor_role,
            auth_source="internal_proposal_registry_executor",
            timestamp=now_iso,
            target_id=target_id,
            before_state=before_state,
            after_state=after_state,
            affected_records={
                "schedule_item_id": target_id,
                "proposal_id": proposal_id,
                "invalidated_briefing_ids": [b["id"] for b in invalidated_briefings],
                "sent_briefings_needing_revision": sent_briefings_needing_revision,
                "preserved_task_ids": preserved_task_ids,
            },
            outcome="success",
            notes=(
                f"Approved proposal '{proposal_id}': {target_item.get('title')} moved to "
                f"{new_start}-{new_end} in {new_room} by {context.actor_role} '{context.actor_name or context.actor_id}'."
            ),
        )
        if "audit_trail" not in staged:
            staged["audit_trail"] = []
        staged["audit_trail"].append(audit_event.to_dict())

    return {
        "success": True,
        "proposal_id": proposal_id,
        "status": "approved",
        "audit_event_id": event_id,
        "target_schedule_id": target_id,
        "mutation": {
            "before": before_state,
            "after": after_state,
        },
        "invalidated_briefings": invalidated_briefings,
        "sent_briefings_needing_revision": sent_briefings_needing_revision,
        "preserved_tasks_count": len(preserved_task_ids),
        "audit_event": audit_event.to_dict(),
    }


# ---------------------------------------------------------------------------
# 8. Public / API Adapter Entrypoints for Proposal Lifecycle
# ---------------------------------------------------------------------------
def apply_approved_proposal_by_id(
    store: EventStore,
    proposal_id: str,
    approval_context: Any = None,
    *,
    adapter: AuthenticatedApprovalAdapter | None = None,
) -> dict[str, Any]:
    """Public entrypoint for executing an approved proposal by its server-owned proposal ID.

    PHASE 5B TRUST BOUNDARY:
    Requires an authenticated AuthenticatedApprovalAdapter. If adapter is None,
    fails closed with UntrustedApprovalContextError.
    """
    if adapter is None:
        raise UntrustedApprovalContextError(
            "Production proposal approval entrypoint fails closed in Phase 5B: No authenticated server API adapter "
            "is registered. Callers cannot self-declare authorization by passing an ApprovalContext, "
            "arbitrary headers, or boolean flags. Production proposal approvals require server-side session "
            "authentication."
        )

    if not isinstance(adapter, AuthenticatedApprovalAdapter):
        raise UntrustedApprovalContextError(
            "Invalid approval adapter: adapter must implement AuthenticatedApprovalAdapter."
        )

    verified_context = adapter.authenticate_and_authorize(approval_context)
    return execute_approved_proposal_by_id(store, proposal_id, verified_context)


def apply_rejected_proposal_by_id(
    store: EventStore,
    proposal_id: str,
    approval_context: Any = None,
    *,
    reason: str = "",
    adapter: AuthenticatedApprovalAdapter | None = None,
) -> dict[str, Any]:
    """Public entrypoint for rejecting a proposal by its server-owned proposal ID.

    PHASE 5B TRUST BOUNDARY:
    Requires an authenticated AuthenticatedApprovalAdapter. If adapter is None,
    fails closed with UntrustedApprovalContextError.
    """
    if adapter is None:
        raise UntrustedApprovalContextError(
            "Production proposal rejection entrypoint fails closed in Phase 5B: No authenticated server API adapter "
            "is registered. Callers cannot self-declare authorization by passing an ApprovalContext, "
            "arbitrary headers, or boolean flags. Production proposal rejections require server-side session "
            "authentication."
        )

    if not isinstance(adapter, AuthenticatedApprovalAdapter):
        raise UntrustedApprovalContextError(
            "Invalid approval adapter: adapter must implement AuthenticatedApprovalAdapter."
        )

    verified_context = adapter.authenticate_and_authorize(approval_context)
    return reject_proposal(store, proposal_id, verified_context, reason=reason)
