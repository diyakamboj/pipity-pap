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
import os
import sys
import time
from typing import Any, Optional
import uuid

# Ensure sibling imports work across working directories
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from briefing_engine import compute_source_fingerprint
from conflict_engine import analyze_schedule_impact
from event_store import AuditEvent, ConfirmationState, EventStore


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
