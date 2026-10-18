"""tests/test_logistics_router.py: Dedicated FastAPI test suite for Phase 5B.4 Logistics Approval Service.

Tests cover:
- GET list and details endpoints (read-only, no EventStore mutations).
- Invalid filters (400) and unknown proposal IDs (404).
- Read-only GET behavior preserving expired proposals (persisted pending, effective expired).
- Missing authentication returns 401 for both mutations (fail-closed default).
- Forged identity/role headers cannot bypass authentication.
- Verified test identities can approve and reject according to authoritative EventStore membership.
- Inactive and cross-event actors are rejected (403).
- Confirmed commitments require authoritative lead-organizer permission (403).
- Duplicate (409), stale (409), and expired (410) proposals fail safely.
- Approved changes persist to disk and are visible to separate EventStore instances.
- Audit trail and briefing invalidation remain intact.
- Existing FastAPI routes remain registered.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Optional

import pytest
from starlette.testclient import TestClient

# Ensure HRAgent_Main root is on sys.path
AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

# Ensure event_mcp is on sys.path
REPO_ROOT = AGENT_ROOT.parent
EVENT_MCP_DIR = REPO_ROOT / "event_mcp"
if str(EVENT_MCP_DIR) not in sys.path and EVENT_MCP_DIR.exists():
    sys.path.insert(0, str(EVENT_MCP_DIR))

from approval_engine import (
    ApprovalEngineError,
    ConfirmedCommitmentError,
    DuplicateProposalError,
    EventMembershipApprovalAdapter,
    ProposalExpiredError,
    ProposalNotFoundError,
    StaleProposalError,
    TrustedIdentityVerifier,
    UnauthorizedApprovalError,
    UntrustedApprovalContextError,
    VerifiedIdentity,
    compute_schedule_baseline_fingerprint,
    create_trusted_proposal,
)
from event_store import EventStore, ProposalRecord, ProposalStatus
from runtime.server.api import create_app
from runtime.server.logistics_router import (
    get_event_store,
    get_trusted_identity_verifier,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Mocks
# ---------------------------------------------------------------------------
class MockTestVerifier(TrustedIdentityVerifier):
    """Mock identity verifier for testing authorized/unauthorized scenarios."""

    def __init__(
        self,
        user_id: str,
        auth_source: str = "mock_verifier",
        override_confirmed_commitments: bool = False,
        external_confirmations_verified: bool = False,
        fail_with: Optional[Exception] = None,
    ):
        self.user_id = user_id
        self.auth_source = auth_source
        self.override_confirmed_commitments = override_confirmed_commitments
        self.external_confirmations_verified = external_confirmations_verified
        self.fail_with = fail_with

    def verify_identity(self, request_credentials: Any) -> VerifiedIdentity:
        if self.fail_with is not None:
            raise self.fail_with

        if not self.user_id:
            raise UntrustedApprovalContextError("User unauthenticated.")

        now_iso = datetime.now(timezone.utc).isoformat()
        return VerifiedIdentity(
            user_id=self.user_id,
            auth_source=self.auth_source,
            verified_at=now_iso,
            session_id="mock-session-xyz",
            override_confirmed_commitments=self.override_confirmed_commitments,
            external_confirmations_verified=self.external_confirmations_verified,
        )


@pytest.fixture
def isolated_storage_dir(tmp_path: Path) -> Path:
    """Fixture providing an isolated directory with fresh seed data for EventStore."""
    seed_file = EVENT_MCP_DIR / "event_data.json"
    dest_file = tmp_path / "event_data.json"
    if seed_file.exists():
        shutil.copyfile(seed_file, dest_file)
    return dest_file


@pytest.fixture
def isolated_store(isolated_storage_dir: Path) -> EventStore:
    """Fixture providing an EventStore pointing to the isolated test data file."""
    return EventStore(storage_path=str(isolated_storage_dir))


@pytest.fixture
def client(isolated_store: EventStore):
    """FastAPI TestClient with isolated EventStore and unconfigured verifier (fails closed)."""
    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: None
    return TestClient(app)


def _create_sample_proposal(
    store: EventStore,
    target_id: str = "sch-002",
    ttl_seconds: int = 3600,
) -> dict[str, Any]:
    """Helper to generate a valid, conflict-free proposal in the isolated store."""
    target_item = store.find_schedule_item(target_id)
    assert target_item is not None

    candidate = {
        "title": f"Reschedule {target_item['title']}",
        "description": "Shift timing to resolve room conflict",
        "target_schedule_id": target_id,
        "proposed_changes": [
            {
                "record_id": target_id,
                "record_type": "schedule_item",
                "field": "start_time",
                "before": target_item["start_time"],
                "after": "09:05",
            },
            {
                "record_id": target_id,
                "record_type": "schedule_item",
                "field": "end_time",
                "before": target_item["end_time"],
                "after": "09:35",
            },
        ],
    }
    return create_trusted_proposal(store, candidate, ttl_seconds=ttl_seconds)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
def test_get_proposals_list_empty(client: TestClient, isolated_store: EventStore):
    """GET /api/logistics/proposals returns empty list when no proposals exist."""
    res = client.get("/api/logistics/proposals")
    assert res.status_code == 200
    data = res.json()
    assert data["event_id"] == "evt-001"
    assert data["total"] == 0
    assert data["proposals"] == []


def test_get_proposals_list_and_details(client: TestClient, isolated_store: EventStore):
    """GET /api/logistics/proposals and /proposals/{id} return correct details."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    # Test list endpoint
    list_res = client.get("/api/logistics/proposals")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    item = list_data["proposals"][0]
    assert item["id"] == prop_id
    assert item["target_schedule_id"] == "sch-002"
    assert item["status"] == "pending"
    assert item["persisted_status"] == "pending"
    assert item["effective_status"] == "pending"
    assert item["is_expired"] is False
    assert item["is_stale"] is False
    assert len(item["proposed_changes"]) == 2

    # Test detail endpoint
    detail_res = client.get(f"/api/logistics/proposals/{prop_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == prop_id
    assert detail_data["title"] == item["title"]
    assert detail_data["baseline_fingerprint"] == item["baseline_fingerprint"]


def test_get_proposals_invalid_filter_400(client: TestClient):
    """GET /api/logistics/proposals?status=invalid returns 400 Bad Request."""
    res = client.get("/api/logistics/proposals?status=bogus_status")
    assert res.status_code == 400
    assert "Invalid status filter" in res.json()["detail"]


def test_get_proposal_unknown_404(client: TestClient):
    """GET /api/logistics/proposals/{proposal_id} returns 404 for nonexistent proposal."""
    res = client.get("/api/logistics/proposals/prop-nonexistent-123")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_proposals_cross_event_restricted(client: TestClient, isolated_store: EventStore):
    """Queries for non-hosted events return empty list or 404."""
    _create_sample_proposal(isolated_store, target_id="sch-002")

    # Filter for non-hosted event returns 0 results
    res = client.get("/api/logistics/proposals?event_id=evt-999")
    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert res.json()["proposals"] == []


def test_read_only_get_preserves_expired_state(client: TestClient, isolated_store: EventStore):
    """GET does NOT mutate EventStore when an expired proposal is encountered."""
    # Create proposal with expiration in the past
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    isolated_store.update_proposal(prop_id, {"expires_at": past_time})

    # Call GET list endpoint
    list_res = client.get("/api/logistics/proposals")
    assert list_res.status_code == 200
    item = list_res.json()["proposals"][0]
    assert item["is_expired"] is True
    assert item["persisted_status"] == "pending"  # In DB it remains pending
    assert item["effective_status"] == "expired"  # Calculated in real time

    # Call GET details endpoint
    detail_res = client.get(f"/api/logistics/proposals/{prop_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["is_expired"] is True
    assert detail_res.json()["persisted_status"] == "pending"

    # CRITICAL: Verify EventStore was NOT mutated by the GET operations
    stored_raw = isolated_store.find_proposal(prop_id)
    assert stored_raw["status"] == "pending"


def test_mutations_fail_closed_without_auth_401(client: TestClient, isolated_store: EventStore):
    """Without a configured verifier, POST approve and reject return 401 Unauthorized."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    # Test approve fails closed
    app_res = client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert app_res.status_code == 401
    assert "No trusted identity verifier is configured" in app_res.json()["detail"]

    # Test reject fails closed
    rej_res = client.post(f"/api/logistics/proposals/{prop_id}/reject", json={"reason": "Testing"})
    assert rej_res.status_code == 401
    assert "No trusted identity verifier is configured" in rej_res.json()["detail"]

    # Verify proposal remains pending and untouched in store
    assert isolated_store.find_proposal(prop_id)["status"] == "pending"


def test_forged_headers_cannot_bypass_auth_401(client: TestClient, isolated_store: EventStore):
    """Forged headers (X-Actor-Id, X-Role, X-Session-API-Key) cannot bypass unconfigured auth."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    headers = {
        "X-Actor-Id": "usr-diya-001",
        "X-Role": "lead_organizer",
        "X-Session-API-Key": "fake-admin-key",
        "Authorization": "Bearer fake-token",
    }

    res = client.post(f"/api/logistics/proposals/{prop_id}/approve", headers=headers)
    assert res.status_code == 401
    assert "No trusted identity verifier is configured" in res.json()["detail"]


def test_verified_organizer_approval_flow(isolated_store: EventStore):
    """Verified lead organizer can successfully approve a proposal."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
        override_confirmed_commitments=True,
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "approved"
    assert data["target_schedule_id"] == "sch-002"
    assert data["mutation"]["after"]["start_time"] == "09:05"
    assert data["mutation"]["after"]["end_time"] == "09:35"

    # Verify store record updated
    stored_prop = isolated_store.find_proposal(prop_id)
    assert stored_prop["status"] == "approved"
    assert stored_prop["resolved_by"] == "usr-diya-001"

    sch_item = isolated_store.find_schedule_item("sch-002")
    assert sch_item["start_time"] == "09:05"
    assert sch_item["end_time"] == "09:35"


def test_changes_persist_and_visible_to_separate_store_instance(isolated_store: EventStore, isolated_storage_dir: Path):
    """Approved mutations persist to disk and are visible to a separate EventStore instance."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 200

    # Instantiate a completely separate EventStore pointing to the same file
    second_store = EventStore(storage_path=str(isolated_storage_dir))
    second_prop = second_store.find_proposal(prop_id)
    assert second_prop["status"] == "approved"
    second_sch = second_store.find_schedule_item("sch-002")
    assert second_sch["start_time"] == "09:05"


def test_verified_organizer_rejection_flow(isolated_store: EventStore):
    """Verified organizer can reject a proposal with an explanatory reason."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-org-002",
    )
    test_client = TestClient(app)

    res = test_client.post(
        f"/api/logistics/proposals/{prop_id}/reject",
        json={"reason": "Speaker prefers earlier morning slot"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Speaker prefers earlier morning slot"

    # Verify store state
    stored_prop = isolated_store.find_proposal(prop_id)
    assert stored_prop["status"] == "rejected"
    assert stored_prop["rejection_reason"] == "Speaker prefers earlier morning slot"
    assert stored_prop["resolved_by"] == "usr-org-002"

    # Schedule item remains unchanged
    sch_item = isolated_store.find_schedule_item("sch-002")
    assert sch_item["start_time"] == "09:00"


def test_inactive_organizer_rejected_403(isolated_store: EventStore):
    """Inactive organizer identity is rejected with 403 Forbidden."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-inactive-003",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 403
    detail = res.json()["detail"].lower()
    assert "inactive" in detail


def test_cross_event_actor_rejected_403(isolated_store: EventStore):
    """Unregistered or cross-event user is rejected with 403 Forbidden."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-foreign-999",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 403
    assert "no organizer membership" in res.json()["detail"].lower()


def test_confirmed_commitment_requires_lead_organizer_403(isolated_store: EventStore):
    """Modifying confirmed commitment without lead organizer authorization returns 403."""
    # Target item sch-003 has a confirmed speaker (Prof. Sara Kim)
    target_id = "sch-003"
    isolated_store.update_schedule_item(target_id, {"confirmation_state": "confirmed"})
    target_item = isolated_store.find_schedule_item(target_id)
    assert target_item is not None

    candidate = {
        "title": "Shift Keynote",
        "description": "Shift keynote timing",
        "target_schedule_id": target_id,
        "strategy": "RESCHEDULE_SESSION",
        "affects_confirmed_commitments": True,
        "proposed_changes": [
            {
                "record_id": target_id,
                "record_type": "schedule_item",
                "field": "start_time",
                "before": "09:30",
                "after": "09:15",
            },
            {
                "record_id": target_id,
                "record_type": "schedule_item",
                "field": "end_time",
                "before": "10:30",
                "after": "10:15",
            },
        ],
    }
    prop = create_trusted_proposal(isolated_store, candidate)
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    # Regular organizer (not lead) without confirmed override
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-org-002",
        override_confirmed_commitments=False,
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 403
    assert "confirmed commitment" in res.json()["detail"].lower()


def test_duplicate_approval_rejected_409(isolated_store: EventStore):
    """Approving an already approved proposal returns 409 Conflict."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
    )
    test_client = TestClient(app)

    # First approval succeeds
    res1 = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res1.status_code == 200

    # Second approval fails with 409 Conflict
    res2 = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res2.status_code == 409
    assert "already approved" in res2.json()["detail"].lower() or "unexpected state" in res2.json()["detail"].lower()


def test_stale_baseline_approval_rejected_409(isolated_store: EventStore):
    """If target item baseline state changed after proposal creation, approval returns 409."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    # Mutate a baseline-fingerprinted field (e.g. room) directly before approval
    isolated_store.update_schedule_item("sch-002", {"room": "Gates Hall 200"})

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 409
    assert "stale" in res.json()["detail"].lower() or "baseline" in res.json()["detail"].lower()


def test_expired_proposal_approval_rejected_410(isolated_store: EventStore):
    """Attempting to approve an expired proposal returns 410 Gone."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    isolated_store.update_proposal(prop_id, {"expires_at": past_time})

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 410
    assert "expired" in res.json()["detail"].lower()


def test_audit_trail_and_briefing_invalidation(isolated_store: EventStore):
    """Approval invalidates draft briefings and records durable audit events."""
    # Ensure a draft briefing exists with session_id matching the target schedule item
    briefing = {
        "id": "brf-test-001",
        "recipient_id": "spk-002",
        "session_id": "sch-002",
        "participant_type": "speaker",
        "status": "draft",
        "content": "Original briefing draft",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    isolated_store.add_briefing(briefing)

    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 200

    # Briefing should be invalidated to 'stale'
    updated_brf = isolated_store.find_briefing("brf-test-001")
    assert updated_brf["status"] == "stale"
    assert updated_brf["is_stale"] is True

    # Audit trail should contain the approval record
    audits = isolated_store.all_audit_events()
    approval_audit = next(
        (a for a in reversed(audits) if a.get("proposal_id") == prop_id and a.get("action_type") == "schedule_mutation"),
        None,
    )
    assert approval_audit is not None
    assert approval_audit["action_type"] == "schedule_mutation"
    assert approval_audit["actor_id"] == "usr-diya-001"
    assert approval_audit["actor_role"] == "lead_organizer"
    assert approval_audit["outcome"] == "success"


def test_existing_fastapi_routes_remain_registered():
    """Verify that existing FastAPI endpoints are preserved after registering logistics_router."""
    app = create_app()
    paths = {r.path for r in app.routes}

    # Verify standard HRAgent endpoints are registered
    assert "/alive" in paths
    assert "/server_info" in paths
    assert "/api/settings" in paths
    assert "/api/plugins" in paths

    # Verify new logistics endpoints are registered
    assert "/api/logistics/proposals" in paths
    assert "/api/logistics/proposals/{proposal_id}" in paths
    assert "/api/logistics/proposals/{proposal_id}/approve" in paths
    assert "/api/logistics/proposals/{proposal_id}/reject" in paths


def test_get_proposals_does_not_modify_file_bytes_or_mtime(client: TestClient, isolated_store: EventStore, isolated_storage_dir: Path):
    """GET endpoints never modify file bytes or disk contents, even for expired proposals."""
    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    # Expire proposal by timestamp
    past_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    isolated_store.update_proposal(prop_id, {"expires_at": past_time})

    # Read disk bytes before GET operations
    before_bytes = isolated_storage_dir.read_bytes()
    before_mtime = os.path.getmtime(isolated_storage_dir)

    # Perform multiple read operations
    res_list = client.get("/api/logistics/proposals")
    assert res_list.status_code == 200
    res_detail = client.get(f"/api/logistics/proposals/{prop_id}")
    assert res_detail.status_code == 200

    # Read disk bytes after GET operations
    after_bytes = isolated_storage_dir.read_bytes()
    after_mtime = os.path.getmtime(isolated_storage_dir)

    assert before_bytes == after_bytes
    assert before_mtime == after_mtime


def test_server_session_api_key_enforced_when_configured(isolated_store: EventStore):
    """When session_api_keys is configured on the server, X-Session-API-Key is enforced, but does not grant organizer identity."""
    from runtime.server.config import Config

    conf = Config(session_api_keys=["super-secret-cluster-key"])
    app = create_app(config=conf)
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: None
    test_client = TestClient(app)

    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    # 1. Without X-Session-API-Key, GET is rejected by server gate with 401
    res_unauth = test_client.get("/api/logistics/proposals")
    assert res_unauth.status_code == 401

    # 2. With valid X-Session-API-Key, GET succeeds
    res_auth = test_client.get(
        "/api/logistics/proposals",
        headers={"X-Session-API-Key": "super-secret-cluster-key"},
    )
    assert res_auth.status_code == 200

    # 3. With valid X-Session-API-Key, POST approve is STILL rejected with 401 because
    #    server API keys do NOT establish human organizer identity (fails closed)
    res_approve = test_client.post(
        f"/api/logistics/proposals/{prop_id}/approve",
        headers={"X-Session-API-Key": "super-secret-cluster-key"},
    )
    assert res_approve.status_code == 401
    assert "No trusted identity verifier is configured" in res_approve.json()["detail"]


def test_sent_briefings_needing_revision_in_approval_response(isolated_store: EventStore):
    """Approval preserves sent briefings as immutable and lists them in sent_briefings_needing_revision."""
    # Create a briefing that was already sent
    sent_briefing = {
        "id": "brf-sent-001",
        "recipient_id": "spk-002",
        "session_id": "sch-002",
        "participant_type": "speaker",
        "status": "sent",
        "content": "Sent briefing text",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    isolated_store.add_briefing(sent_briefing)

    prop = _create_sample_proposal(isolated_store, target_id="sch-002")
    prop_id = prop["proposal_id"]

    app = create_app()
    app.dependency_overrides[get_event_store] = lambda: isolated_store
    app.dependency_overrides[get_trusted_identity_verifier] = lambda: MockTestVerifier(
        user_id="usr-diya-001",
    )
    test_client = TestClient(app)

    res = test_client.post(f"/api/logistics/proposals/{prop_id}/approve")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    # The sent briefing ID is listed for human revision tracking
    assert "brf-sent-001" in data["sent_briefings_needing_revision"]

    # Verify that the sent briefing was NOT overwritten to stale in storage (stays sent)
    brf_check = isolated_store.find_briefing("brf-sent-001")
    assert brf_check["status"] == "sent"


def test_unexpected_exception_sanitized_500():
    """Unexpected internal exceptions in map_approval_engine_error do not leak paths or stack traces."""
    from runtime.server.logistics_router import map_approval_engine_error

    sensitive_exc = OSError("/Users/private/internal/path/event_data.json: Disk I/O failure")
    http_exc = map_approval_engine_error(sensitive_exc)
    assert http_exc.status_code == 500
    assert http_exc.detail == "Internal server error occurred during proposal processing."
    assert "Users" not in http_exc.detail
    assert "event_data.json" not in http_exc.detail

