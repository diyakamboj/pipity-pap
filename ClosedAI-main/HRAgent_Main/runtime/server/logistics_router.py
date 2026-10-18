"""logistics_router: Dedicated FastAPI router for HITL Schedule Change Proposals.

Part of Phase 5B.4: Python Approval Service.

Exposes REST endpoints for:
- GET  /api/logistics/proposals
- GET  /api/logistics/proposals/{proposal_id}
- POST /api/logistics/proposals/{proposal_id}/approve
- POST /api/logistics/proposals/{proposal_id}/reject

TRUST BOUNDARY & ARCHITECTURAL INVARIANTS:
1. Strict Separation of Read vs. Mutation:
   - GET endpoints inspect stored proposals and compute effective expiration and staleness
     WITHOUT mutating the EventStore.
   - Mutation endpoints (approve / reject) execute atomic schedule changes and lifecycle
     transitions under EventStore's single transaction lock.
2. Fail-Closed Authentication:
   - Approval and rejection require a configured TrustedIdentityVerifier.
   - In production (and by default), no verifier is configured, causing mutations to fail
     closed with HTTP 401 Unauthorized.
   - Never infers identity from X-Session-API-Key, conversation IDs, arbitrary headers,
     caller-provided role strings, or demo organizer fixtures.
3. Authoritative Authorization:
   - Uses EventMembershipApprovalAdapter to authenticate external credentials via the verifier
     and derive the actor's role authoritatively from EventStore membership records.
   - Role and active status are re-verified inside the atomic transaction lock.
4. Input Integrity:
   - Rejects arbitrary proposed_changes from HTTP clients; mutations execute strictly from
     the server-owned ProposalRecord in EventStore.
5. Cross-Process Consistency:
   - Resolves EventStore storage paths robustly and preserves POSIX file locking (fcntl.flock).
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Robust Sibling & Sibling-Package Path Resolution
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # ClosedAI-main
EVENT_MCP_DIR = os.environ.get("EVENT_MCP_DIR")
if EVENT_MCP_DIR:
    event_mcp_path = Path(EVENT_MCP_DIR).resolve()
else:
    event_mcp_path = (REPO_ROOT / "event_mcp").resolve()

if str(event_mcp_path) not in sys.path and event_mcp_path.exists():
    sys.path.insert(0, str(event_mcp_path))

from approval_engine import (
    ApprovalEngineError,
    ConflictingProposalError,
    ConfirmedCommitmentError,
    DuplicateProposalError,
    EventMembershipApprovalAdapter,
    InvalidProposalError,
    InvalidProposalStateError,
    ProposalExpiredError,
    ProposalNotFoundError,
    ProposalRejectedError,
    ScheduleItemNotFoundError,
    StaleProposalError,
    TamperedProposalError,
    TrustedIdentityVerifier,
    UnauthorizedApprovalError,
    UntrustedApprovalContextError,
    VerifiedIdentity,
    apply_approved_proposal_by_id,
    apply_rejected_proposal_by_id,
    compute_schedule_baseline_fingerprint,
    is_proposal_expired,
)
from event_store import (
    EventStore,
    ProposalRecord,
    ProposalStatus,
)


# ---------------------------------------------------------------------------
# Router & Dependency Seams
# ---------------------------------------------------------------------------
logistics_router = APIRouter(prefix="/logistics", tags=["Logistics"])

_shared_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """Return an EventStore instance connected to the authoritative persistent store.

    Uses EVENT_STORE_PATH if set, otherwise defaults to event_mcp/event_data.json.
    Can be overridden via FastAPI dependency_overrides in tests.
    """
    global _shared_store
    storage_path = os.environ.get("EVENT_STORE_PATH")
    if storage_path is None:
        storage_path = str(event_mcp_path / "event_data.json")

    storage_path_abs = os.path.abspath(storage_path)
    if _shared_store is None or _shared_store.storage_path != storage_path_abs:
        _shared_store = EventStore(storage_path=storage_path_abs)
    return _shared_store


def get_trusted_identity_verifier() -> Optional[TrustedIdentityVerifier]:
    """Dependency seam returning the registered TrustedIdentityVerifier.

    By default in Phase 5B.4, returns None because Gurt has no real login or
    session authentication configured yet.
    Future phases (or production config) can register a real verifier (e.g., NextAuthSessionVerifier).
    Tests can override this dependency using FastAPI's dependency_overrides.
    """
    return None


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class ProposalSummaryResponse(BaseModel):
    """Normalized response schema for a schedule change proposal."""
    id: str
    event_id: str
    target_schedule_id: str
    title: str
    description: str
    status: str
    persisted_status: str
    effective_status: str
    is_expired: bool
    is_stale: bool
    proposed_changes: list[dict[str, Any]]
    impact: dict[str, Any]
    required_confirmations: list[str]
    created_at: str
    expires_at: str
    baseline_version: int
    baseline_fingerprint: str
    rejection_reason: Optional[str] = None
    executed_at: Optional[str] = None
    audit_event_id: Optional[str] = None
    proposal_hash: Optional[str] = None
    created_by: Optional[str] = None


class ProposalListResponse(BaseModel):
    """Response schema for listing stored proposals."""
    event_id: str
    total: int
    proposals: list[ProposalSummaryResponse]


class ApproveProposalResponse(BaseModel):
    """Response schema for a successfully approved proposal."""
    success: bool
    proposal_id: str
    status: str
    audit_event_id: str
    target_schedule_id: str
    mutation: dict[str, Any]
    invalidated_briefings: list[dict[str, Any]] = []
    sent_briefings_needing_revision: list[str] = []
    preserved_tasks_count: int = 0
    audit_event: dict[str, Any]


class RejectProposalRequest(BaseModel):
    """Request schema for rejecting a proposal."""
    reason: str = Field(default="", max_length=500, description="Optional explanation for rejecting the proposal.")


class RejectProposalResponse(BaseModel):
    """Response schema for a successfully rejected proposal."""
    success: bool
    proposal_id: str
    status: str
    rejection_reason: str
    audit_event_id: str
    audit_event: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Domain Exception Mapping
# ---------------------------------------------------------------------------
def map_approval_engine_error(exc: Exception) -> HTTPException:
    """Map approval engine domain exceptions to semantically appropriate HTTP status codes."""
    if isinstance(exc, UntrustedApprovalContextError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    elif isinstance(exc, (UnauthorizedApprovalError, ConfirmedCommitmentError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    elif isinstance(exc, (ProposalNotFoundError, ScheduleItemNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    elif isinstance(exc, ProposalExpiredError):
        return HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))
    elif isinstance(
        exc,
        (
            DuplicateProposalError,
            StaleProposalError,
            ProposalRejectedError,
            InvalidProposalStateError,
            ConflictingProposalError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    elif isinstance(exc, (InvalidProposalError, TamperedProposalError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    elif isinstance(exc, ApprovalEngineError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error occurred during proposal processing.",
    )


# ---------------------------------------------------------------------------
# Proposal Annotation Helper (Read-Only)
# ---------------------------------------------------------------------------
def _annotate_proposal_summary(p: dict[str, Any], store: EventStore, hosted_event_id: str) -> ProposalSummaryResponse:
    """Compute real-time expiration and staleness annotations without mutating EventStore."""
    persisted_status = p.get("status", ProposalStatus.PENDING.value)
    expires_at = p.get("expires_at", "")
    is_expired = is_proposal_expired(expires_at) if expires_at else False

    target_id = p.get("target_schedule_id")
    if not target_id and p.get("proposed_changes"):
        target_id = p["proposed_changes"][0].get("record_id")

    target_item = store.find_schedule_item(target_id) if target_id else None
    if target_item:
        current_fp = compute_schedule_baseline_fingerprint(target_item)
        is_stale = (current_fp != p.get("baseline_fingerprint"))
    else:
        is_stale = True

    if persisted_status == ProposalStatus.PENDING.value and is_expired:
        effective_status = ProposalStatus.EXPIRED.value
    else:
        effective_status = persisted_status

    return ProposalSummaryResponse(
        id=p.get("id", ""),
        event_id=p.get("event_id", hosted_event_id),
        target_schedule_id=target_id or "",
        title=p.get("title", ""),
        description=p.get("description", ""),
        status=persisted_status,
        persisted_status=persisted_status,
        effective_status=effective_status,
        is_expired=is_expired,
        is_stale=is_stale,
        proposed_changes=p.get("proposed_changes", []),
        impact=p.get("impact", {}),
        required_confirmations=p.get("required_confirmations", []),
        created_at=p.get("created_at", ""),
        expires_at=expires_at,
        baseline_version=int(p.get("baseline_version", 0)),
        baseline_fingerprint=p.get("baseline_fingerprint", ""),
        rejection_reason=p.get("rejection_reason"),
        executed_at=p.get("executed_at") or p.get("resolved_at"),
        audit_event_id=p.get("audit_event_id"),
        proposal_hash=p.get("proposal_hash"),
        created_by=p.get("created_by"),
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@logistics_router.get(
    "/proposals",
    response_model=ProposalListResponse,
    summary="List stored schedule change proposals",
)
def list_proposals_endpoint(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter proposals by status (pending, approved, rejected, expired)",
    ),
    event_id: Optional[str] = Query(
        None,
        description="Optional event ID filter. Restricts queries to the hosted event.",
    ),
    store: EventStore = Depends(get_event_store),
):
    """List stored proposals for the hosted event.

    Strictly read-only: does NOT mutate EventStore.
    Reports real-time expiration and staleness separately from persisted database status.
    """
    valid_statuses = {s.value for s in ProposalStatus}
    validated_status: Optional[str] = None
    if status_filter is not None:
        status_clean = status_filter.strip().lower()
        if status_clean not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter '{status_filter}'. Allowed statuses: {sorted(list(valid_statuses))}",
            )
        validated_status = status_clean

    hosted_event = store.get_event()
    hosted_event_id = hosted_event.get("id") or "evt-001"

    if event_id and event_id.strip() != hosted_event_id:
        return ProposalListResponse(
            event_id=hosted_event_id,
            total=0,
            proposals=[],
        )

    proposals_raw = store.all_proposals()
    annotated: list[ProposalSummaryResponse] = []

    for p in proposals_raw:
        if p.get("event_id") != hosted_event_id:
            continue

        summary = _annotate_proposal_summary(p, store, hosted_event_id)

        if validated_status is not None:
            # Match persisted status or effective status
            if summary.persisted_status != validated_status and summary.effective_status != validated_status:
                continue

        annotated.append(summary)

    return ProposalListResponse(
        event_id=hosted_event_id,
        total=len(annotated),
        proposals=annotated,
    )


@logistics_router.get(
    "/proposals/{proposal_id}",
    response_model=ProposalSummaryResponse,
    summary="Get proposal details by ID",
)
def get_proposal_endpoint(
    proposal_id: str,
    store: EventStore = Depends(get_event_store),
):
    """Retrieve full proposal details by ID.

    Strictly read-only: does NOT mutate EventStore.
    Returns 404 for unknown proposals or proposals for other events.
    """
    p = store.find_proposal(proposal_id)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{proposal_id}' not found.",
        )

    hosted_event = store.get_event()
    hosted_event_id = hosted_event.get("id") or "evt-001"
    if p.get("event_id") != hosted_event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal '{proposal_id}' not found.",
        )

    return _annotate_proposal_summary(p, store, hosted_event_id)


@logistics_router.post(
    "/proposals/{proposal_id}/approve",
    response_model=ApproveProposalResponse,
    summary="Approve a schedule change proposal",
)
def approve_proposal_endpoint(
    proposal_id: str,
    request: Request,
    store: EventStore = Depends(get_event_store),
    verifier: Optional[TrustedIdentityVerifier] = Depends(get_trusted_identity_verifier),
):
    """Execute an approved schedule change proposal.

    Requires an authenticated, server-verified identity supplied by a configured
    TrustedIdentityVerifier. Fails closed with 401 if verifier is unconfigured.
    Never accepts arbitrary proposed_changes from the request body.
    """
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication unavailable: No trusted identity verifier is configured. "
                "The approval service fails closed because Gurt currently has no real login or "
                "session authentication provider configured to verify organizer credentials."
            ),
        )

    hosted_event = store.get_event()
    hosted_event_id = hosted_event.get("id") or "evt-001"
    adapter = EventMembershipApprovalAdapter(
        store=store,
        event_id=hosted_event_id,
        verifier=verifier,
    )

    try:
        result = apply_approved_proposal_by_id(
            store=store,
            proposal_id=proposal_id,
            approval_context=request,
            adapter=adapter,
        )
        return ApproveProposalResponse(
            success=result["success"],
            proposal_id=result["proposal_id"],
            status=result["status"],
            audit_event_id=result["audit_event_id"],
            target_schedule_id=result["target_schedule_id"],
            mutation=result["mutation"],
            invalidated_briefings=result.get("invalidated_briefings", []),
            sent_briefings_needing_revision=result.get("sent_briefings_needing_revision", []),
            preserved_tasks_count=result.get("preserved_tasks_count", 0),
            audit_event=result["audit_event"],
        )
    except Exception as exc:
        raise map_approval_engine_error(exc)


@logistics_router.post(
    "/proposals/{proposal_id}/reject",
    response_model=RejectProposalResponse,
    summary="Reject a schedule change proposal",
)
def reject_proposal_endpoint(
    proposal_id: str,
    request: Request,
    body: Optional[RejectProposalRequest] = None,
    store: EventStore = Depends(get_event_store),
    verifier: Optional[TrustedIdentityVerifier] = Depends(get_trusted_identity_verifier),
):
    """Explicitly reject a schedule change proposal.

    Requires an authenticated, server-verified identity supplied by a configured
    TrustedIdentityVerifier. Fails closed with 401 if verifier is unconfigured.
    """
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication unavailable: No trusted identity verifier is configured. "
                "The rejection service fails closed because Gurt currently has no real login or "
                "session authentication provider configured to verify organizer credentials."
            ),
        )

    hosted_event = store.get_event()
    hosted_event_id = hosted_event.get("id") or "evt-001"
    adapter = EventMembershipApprovalAdapter(
        store=store,
        event_id=hosted_event_id,
        verifier=verifier,
    )

    reason = (body.reason if body else "") or ""
    try:
        result = apply_rejected_proposal_by_id(
            store=store,
            proposal_id=proposal_id,
            approval_context=request,
            reason=reason,
            adapter=adapter,
        )
        return RejectProposalResponse(
            success=result["success"],
            proposal_id=result["proposal_id"],
            status=result["status"],
            rejection_reason=result["rejection_reason"],
            audit_event_id=result["audit_event_id"],
            audit_event=result.get("audit_event"),
        )
    except Exception as exc:
        raise map_approval_engine_error(exc)
