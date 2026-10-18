"""Unit tests for L2 Briefing Engine and FastMCP briefing tools.

Tests:
1. Speaker briefing generation (timing, arrival, stage AV, emergency contact, unconfirmed slots).
2. Vendor briefing generation (delivery window, loading dock access, food policies, headcount, unconfirmed booking).
3. Vendor pricing exclusion regression test (strictly no quotes, pricing, dollar amounts, budgets, or competitor comparisons).
4. Volunteer briefing generation (role shifts, reporting stations, operational checklist, escalation contact).
5. Permission-scoped information allowlists and privacy leakage prevention:
   - Speaker receives NO vendor quotes or sponsor funding amounts.
   - Vendor receives NO pricing, budgets, competitor quotes, or speaker personal emails.
   - Volunteer receives NO confidential pricing, sponsor contracts, or private speaker contacts.
6. Positive field projection (allowlisted positive key extraction before formatting).
7. Deterministic generation (identical source data yields identical fingerprints).
8. Stable IDs, versioning, and persistent revision history snapshots.
9. Dynamic staleness detection after source schedule, speaker, or venue updates.
10. Unrelated changes (vendor pricing, competitor quotes, sponsor amounts) do NOT mark speaker briefings stale.
11. Sent-version preservation & immutability (cannot silently overwrite previously sent briefings).
12. Strict readiness & sending guards (readiness bypass boolean removed; ready/sent strictly blocked on unverified drafts).
13. FastMCP tool scoping: draft-saving and sent-status operations are internal-only and NOT exposed through FastMCP.
14. Read-only FastMCP tools behavior (MCP preview, list, and audit tools never mutate persistent store).
15. Inline confirmation labeling across all participant roles.
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock
import pytest

# Mock fastmcp if not present in test environment
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

from briefing_engine import (
    assert_no_sensitive_leakage,
    check_stale_briefings,
    compute_source_fingerprint,
    evaluate_briefing_readiness,
    generate_speaker_briefing,
    generate_vendor_briefing,
    generate_volunteer_briefing,
    list_briefings,
    mark_briefing_sent,
    preview_briefing,
    project_speaker_allowed_fields,
    project_vendor_allowed_fields,
    project_volunteer_allowed_fields,
    save_briefing_draft,
)
from event_store import Briefing, ConfirmationState, EventStore
from server import (
    MockBackend,
    logistics_check_stale_briefings,
    logistics_list_briefings,
    logistics_preview_briefing,
)


@pytest.fixture
def temp_store_path():
    """Create a temporary filepath for an isolated event store test."""
    fd, path = tempfile.mkstemp(prefix="test_briefings_", suffix=".json")
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
# 1. Speaker Briefing Generation Tests
# ---------------------------------------------------------------------------
def test_speaker_briefing_generation(isolated_store):
    """Generates grounded, permission-scoped briefing for confirmed speaker (Prof. Sara Kim)."""
    briefing = generate_speaker_briefing(isolated_store, "spk-003")

    assert briefing["role"] == "speaker"
    assert briefing["recipient_name"] == "Prof. Sara Kim"
    assert briefing["recipient_email"] == "skim@cs.uw.edu"
    assert "Fairness in Machine Learning" in briefing["session_title"]
    assert briefing["session_time"] == "09:30 - 10:30"
    assert briefing["arrival_time"] == "09:00"  # 30 min before session
    assert "Gates Hall 106" in briefing["room"]

    # Technical provisions
    assert "Podium microphone" in briefing["av_provisions"]
    assert "HDMI" in briefing["av_provisions"]

    # Grounded emergency contact (never invent personal phone numbers)
    assert "Diya" in briefing["emergency_contact"]
    assert "pending organizer confirmation" in briefing["emergency_contact"].lower()
    assert "206-555-0199" not in briefing["emergency_contact"]

    # Grounded confirmation status: attendance confirmed, exact slot tentative
    assert briefing["confirmation_state"] == "tentative"
    assert any("tentative" in item.lower() for item in briefing["missing_details"])

    # Rendered markdown format with explicit inline tags
    body = briefing["rendered_body"]
    assert "# Speaker Briefing: Prof. Sara Kim" in body
    assert "09:00" in body
    assert "09:10" in body  # AV sound check
    assert "206-555-0199" not in body
    assert "[NEEDS ORGANIZER CONFIRMATION]" in body
    assert "[PROPOSED TIMING - TENTATIVE]" in body
    assert "[ASSUMED VENUE PROVISIONS" in body
    assert "Display adapters (USB-C/DisplayPort to HDMI) are NOT guaranteed" in body


def test_speaker_briefing_unconfirmed_speaker(isolated_store):
    """Generates briefing draft for prospecting speaker, explicitly labeling unconfirmed status."""
    briefing = generate_speaker_briefing(isolated_store, "spk-001")

    assert briefing["recipient_name"] == "Dr. Alicia Chen"
    # Should flag prospecting status in missing details
    assert any("prospecting" in item.lower() for item in briefing["missing_details"])


# ---------------------------------------------------------------------------
# 2. Vendor Briefing Generation Tests & Pricing Exclusion Regression
# ---------------------------------------------------------------------------
def test_vendor_briefing_generation(isolated_store):
    """Generates grounded, permission-scoped briefing for catering vendor (Taste of Seoul)."""
    briefing = generate_vendor_briefing(isolated_store, "vnd-003")

    assert briefing["role"] == "vendor"
    assert briefing["recipient_name"] == "Taste of Seoul"
    assert briefing["recipient_email"] == "hello@tasteofseoul.com"
    assert briefing["arrival_time"] == "11:45"
    assert briefing["session_time"] == "12:30 - 13:30"

    content = briefing["content"]
    assert content["service_specifications"]["expected_headcount"] == 80
    assert "Vegan" in content["service_specifications"]["dietary_specifications"]
    assert "Halal" in content["service_specifications"]["dietary_specifications"]

    # Loading dock rules
    assert "Stevens Way service bay" in content["delivery_and_loading_dock"]["loading_access"]
    assert "30-minute" in content["delivery_and_loading_dock"]["dock_rule"]

    # Venue food policy
    assert "chafing dishes allowed" in content["venue_facility_policies"]["food_policy"]
    assert "open flames prohibited" in content["venue_facility_policies"]["food_policy"]

    # Missing booking confirmation (no quote/pricing terms)
    assert any("vendor selection" in item.lower() for item in briefing["missing_details"])

    body = briefing["rendered_body"]
    assert "# Vendor Briefing: Taste of Seoul" in body
    assert "Stevens Way service bay" in body
    assert "11:45" in body
    assert "[UNCONFIRMED BOOKING" in body
    assert "[PROPOSED DELIVERY WINDOW - TENTATIVE" in body
    assert "[ASSUMED VENUE" in body
    assert "206-555-0199" not in body

    # Strictly no pricing, quotes, or budgets in external-facing draft
    assert "$" not in body
    assert "quote" not in body.lower()
    assert "per head" not in body.lower()
    assert "960" not in body
    assert "1200" not in body
    assert "Campus Catering" not in body
    assert "budget" not in body.lower()


def test_vendor_pricing_leak_prevention_regression(isolated_store):
    """Regression test: vendor briefing strictly excludes quotes, pricing, budgets, and comparisons."""
    vnd_briefing = generate_vendor_briefing(isolated_store, "vnd-003")
    rendered = vnd_briefing["rendered_body"]

    # 1. No dollar sign anywhere in rendered markdown
    assert "$" not in rendered, f"Dollar sign found in vendor briefing: {rendered}"

    # 2. No quote or pricing terms
    forbidden_terms = [
        "quote", "$960", "960", "$1200", "1200", "$240", "240",
        "$12", "$15", "$3", "per head", "per_head", "budget", "$5000", "5000",
        "campus catering", "printfast", "acme ai labs", "northwest tech fund",
    ]
    for term in forbidden_terms:
        assert term.lower() not in rendered.lower(), f"Forbidden pricing/quote term '{term}' leaked in vendor briefing!"

    # 3. Allowlist leakage assertion succeeds on clean output
    assert_no_sensitive_leakage("vendor", rendered)

    # 4. Injected pricing leaks MUST trigger assert_no_sensitive_leakage ValueError
    with pytest.raises(ValueError, match="Forbidden pricing"):
        assert_no_sensitive_leakage("vendor", "Target price: $12/head.")

    with pytest.raises(ValueError, match="Forbidden pricing"):
        assert_no_sensitive_leakage("vendor", "Taste of Seoul quote is $960.")

    with pytest.raises(ValueError, match="Forbidden pricing"):
        assert_no_sensitive_leakage("vendor", "Event budget is $5000.")

    with pytest.raises(ValueError, match="Forbidden pricing"):
        assert_no_sensitive_leakage("vendor", "Campus Catering was rejected.")


# ---------------------------------------------------------------------------
# 3. Volunteer Briefing Generation Tests
# ---------------------------------------------------------------------------
def test_volunteer_briefing_generation(isolated_store):
    """Generates grounded operational briefing for volunteers with explicit inline labels."""
    # 1. Check-in Desk Volunteer
    checkin_briefing = generate_volunteer_briefing(isolated_store, "vol-001")
    assert checkin_briefing["role"] == "volunteer"
    assert "Check-in Desk" in checkin_briefing["recipient_name"]
    assert checkin_briefing["session_time"] == "08:30 - 11:30"
    assert "Gates Hall 106 Lobby" in checkin_briefing["room"]
    assert any("scanner" in task.lower() for task in checkin_briefing["content"]["operational_checklist"])
    assert any("lanyards" in task.lower() for task in checkin_briefing["content"]["operational_checklist"])

    body1 = checkin_briefing["rendered_body"]
    assert "[UNASSIGNED ROLE - NEEDS ORGANIZER CONFIRMATION]" in body1
    assert "[PROPOSED SHIFT - PLANNING ESTIMATE" in body1
    assert "206-555-0199" not in body1

    # 2. Teardown Volunteer
    teardown_briefing = generate_volunteer_briefing(isolated_store, "vol-003")
    assert "Teardown" in teardown_briefing["recipient_name"]
    assert teardown_briefing["session_time"] == "16:30 - 18:00"
    assert "18:00 strict lock-out" in teardown_briefing["content"]["venue_rules_and_curfew"]["curfew"]
    assert any("lock-out checklist" in item.lower() for item in teardown_briefing["missing_details"])

    body2 = teardown_briefing["rendered_body"]
    assert "[ASSUMED VENUE CONSTRAINT" in body2
    assert "18:00 strict lock-out" in body2


# ---------------------------------------------------------------------------
# 4. Permission-Scoped Information & Privacy Leakage Prevention Tests
# ---------------------------------------------------------------------------
def test_privacy_allowlist_speaker_no_vendor_or_sponsor_data(isolated_store):
    """Speaker briefing must NEVER leak vendor pricing or sponsor agreements."""
    speaker_b = generate_speaker_briefing(isolated_store, "spk-003")
    rendered = speaker_b["rendered_body"]

    forbidden = ["$1200", "$960", "$240", "per head", "Campus Catering", "Acme AI Labs", "Northwest Tech Fund", "$2000", "$1000"]
    for item in forbidden:
        assert item.lower() not in rendered.lower(), f"Leakage detected: Speaker briefing contains '{item}'"

    assert_no_sensitive_leakage("speaker", rendered)


def test_privacy_allowlist_vendor_no_speaker_personal_contacts(isolated_store):
    """Vendor briefing must NEVER leak speaker personal contact info or competitor quotes."""
    vendor_b = generate_vendor_briefing(isolated_store, "vnd-003")
    rendered = vendor_b["rendered_body"]

    forbidden = ["skim@cs.uw.edu", "achen@example.com", "mrivera@example.com", "Campus Catering", "$1200", "Acme AI Labs", "$2000"]
    for item in forbidden:
        assert item.lower() not in rendered.lower(), f"Leakage detected: Vendor briefing contains '{item}'"

    assert_no_sensitive_leakage("vendor", rendered)


def test_privacy_allowlist_volunteer_no_financial_or_speaker_contacts(isolated_store):
    """Volunteer briefing must NEVER leak confidential quotes, sponsor amounts, or speaker contacts."""
    volunteer_b = generate_volunteer_briefing(isolated_store, "vol-001")
    rendered = volunteer_b["rendered_body"]

    forbidden = ["$1200", "$960", "$2000", "$1000", "skim@cs.uw.edu", "achen@example.com", "Campus Catering", "Acme AI Labs"]
    for item in forbidden:
        assert item.lower() not in rendered.lower(), f"Leakage detected: Volunteer briefing contains '{item}'"

    assert_no_sensitive_leakage("volunteer", rendered)


def test_sensitive_leakage_assertion_raises():
    """assert_no_sensitive_leakage raises ValueError when privacy violation occurs."""
    with pytest.raises(ValueError, match="Privacy Leakage Violation"):
        assert_no_sensitive_leakage("speaker", "The catering cost is $1200 from Campus Catering Co.")

    with pytest.raises(ValueError, match="Privacy Leakage Violation"):
        assert_no_sensitive_leakage("vendor", "Contact the speaker directly at skim@cs.uw.edu.")


# ---------------------------------------------------------------------------
# 5. Positive Field Projection Tests
# ---------------------------------------------------------------------------
def test_positive_field_projection_speaker():
    """Speaker projection contains strictly allowlisted keys and no financial or vendor data."""
    event = {"id": "evt-001", "name": "DubHacks", "date": "2026-11-15", "budget": 5000}
    venue = {"venue_name": "Gates 106", "av_provisions": ["Mic"], "loading_dock_instructions": "Stevens Way"}
    speaker = {"id": "spk-003", "name": "Sara Kim", "topic": "Fairness", "status": "confirmed"}
    session = {"id": "sch-003", "title": "Fairness", "start_time": "09:30", "end_time": "10:30", "room": "Gates 106"}

    proj = project_speaker_allowed_fields(event, venue, speaker, session, "09:00", "09:10", [])

    # Excludes budget, loading dock, vendor quotes
    assert "budget" not in proj["event_overview"]
    assert "loading_dock_instructions" not in proj["av_and_technical_provisions"]
    assert "vendor" not in proj
    assert "sponsor" not in proj


def test_positive_field_projection_vendor():
    """Vendor projection contains strictly allowlisted keys and no speaker emails or competitor pricing."""
    event = {"id": "evt-001", "name": "DubHacks", "date": "2026-11-15", "attendees": 80, "budget": 5000}
    venue = {"venue_name": "Gates 106", "loading_dock_instructions": "Bay 1", "food_policy": "Buffet ok"}
    vendor = {"id": "vnd-003", "name": "Taste of Seoul", "dietary": "Halal", "confirmed": False, "quote": 960}
    session = {"id": "sch-006", "title": "Lunch", "start_time": "12:30", "end_time": "13:30", "room": "Patio"}

    proj = project_vendor_allowed_fields(event, venue, vendor, session, "11:45", [])

    # Excludes overall budget, quote, speaker data
    assert "budget" not in proj["event_overview"]
    assert "speaker" not in proj
    assert "quote" not in proj["service_specifications"]


# ---------------------------------------------------------------------------
# 6. Deterministic Generation & Fingerprinting Tests
# ---------------------------------------------------------------------------
def test_deterministic_generation(isolated_store):
    """Briefings generated from the same data produce identical content and fingerprints."""
    b1 = generate_speaker_briefing(isolated_store, "spk-003")
    b2 = generate_speaker_briefing(isolated_store, "spk-003")

    assert b1["source_fingerprint"] == b2["source_fingerprint"]
    assert b1["rendered_body"] == b2["rendered_body"]
    assert b1["source_records"] == b2["source_records"]


# ---------------------------------------------------------------------------
# 7. Staleness Detection & Unrelated Change Isolation Tests
# ---------------------------------------------------------------------------
def test_staleness_detection_on_schedule_change(isolated_store):
    """Modifying linked schedule slot immediately marks briefing draft as stale."""
    draft = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=draft)

    saved_b = isolated_store.find_briefing(draft["id"])
    assert saved_b is not None
    assert saved_b["is_stale"] is False

    # Modify keynote start time from 09:30 to 10:00
    isolated_store.update_schedule_item("sch-003", {"start_time": "10:00", "end_time": "11:00"})

    # Check staleness report
    audit = check_stale_briefings(isolated_store)
    stale_ids = {b["briefing_id"] for b in audit["stale_briefings"]}
    assert draft["id"] in stale_ids

    # Preview also flags staleness
    preview = preview_briefing(isolated_store, "speaker", "spk-003")
    assert preview["briefing"]["is_stale"] is True


def test_staleness_detection_on_venue_change(isolated_store):
    """Modifying relevant venue constraints marks affected briefings stale."""
    draft = preview_briefing(isolated_store, "vendor", "vnd-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=draft)

    # Change venue loading instructions (relevant to vendor)
    isolated_store.update_venue_constraints({"loading_dock_instructions": "Access via East Gate only."})

    audit = check_stale_briefings(isolated_store)
    stale_ids = {b["briefing_id"] for b in audit["stale_briefings"]}
    assert draft["id"] in stale_ids


def test_unrelated_changes_do_not_trigger_staleness(isolated_store):
    """Unrelated changes must NOT falsely mark unaffected briefings stale."""
    # Save a speaker briefing draft
    spk_draft = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=spk_draft)

    # 1. Unrelated update: change vendor quote & dietary
    isolated_store.update_vendor("vnd-003", {"quote": 1500, "dietary": "Vegan only"})

    # Speaker briefing MUST NOT be marked stale
    spk_preview = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    assert spk_preview.get("is_stale") is False, "Speaker briefing falsely marked stale after vendor change!"

    # 2. Unrelated update: change venue loading dock instructions
    isolated_store.update_venue_constraints({"loading_dock_instructions": "Delivery via North loading zone."})

    # Speaker briefing does not use loading dock, so it MUST NOT be marked stale
    spk_preview2 = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    assert spk_preview2.get("is_stale") is False, "Speaker briefing falsely marked stale after loading dock change!"

    # 3. Unrelated update: change sponsor funding
    isolated_store.update_sponsor("spo-001", {"amount": 5000})

    # Neither speaker nor vendor should be marked stale
    audit = check_stale_briefings(isolated_store)
    stale_ids = {b["briefing_id"] for b in audit["stale_briefings"]}
    assert spk_draft["id"] not in stale_ids, "Speaker briefing falsely marked stale after sponsor update!"


# ---------------------------------------------------------------------------
# 8. Versioning, History Snapshots, and Sent-Version Preservation
# ---------------------------------------------------------------------------
def test_version_increment_and_history(isolated_store):
    """Updating a briefing draft increments version and preserves previous revision history."""
    draft1 = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=draft1)

    b_v1 = isolated_store.find_briefing(draft1["id"])
    assert b_v1["version"] == 1
    assert len(b_v1.get("history", [])) == 0

    # Modify source to trigger version bump
    isolated_store.update_schedule_item("sch-003", {"start_time": "10:00"})

    # Save Version 2
    draft2 = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=draft2)

    b_v2 = isolated_store.find_briefing(draft1["id"])
    assert b_v2["version"] == 2
    assert len(b_v2["history"]) == 1
    assert b_v2["history"][0]["version"] == 1


def test_unchanged_source_data_does_not_increment_version(isolated_store):
    """Saving when underlying source data has not changed preserves the existing version."""
    draft = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=draft)

    # Save again without any source changes
    save_briefing_draft(isolated_store, briefing_data=draft)

    b = isolated_store.find_briefing(draft["id"])
    assert b["version"] == 1


def test_sent_version_preservation_and_immutability(isolated_store):
    """Sent briefings cannot be mutated in-place; revisions create new drafts with archived history."""
    # 1. Set up a fully verified briefing (all commitments locked)
    confirmed_briefing = {
        "id": "brf-spk-confirmed",
        "role": "speaker",
        "recipient_id": "spk-003",
        "recipient_name": "Prof. Sara Kim",
        "recipient_email": "skim@cs.uw.edu",
        "session_id": "sch-003",
        "session_title": "Fairness in Machine Learning",
        "session_time": "09:30 - 10:30",
        "arrival_time": "09:00",
        "room": "Gates Hall 106",
        "av_provisions": "Podium microphone, Dual HDMI displays",
        "notes": "All requirements verified and locked.",
        "emergency_contact": "Diya (Lead Organizer) - verified direct phone via Slack",
        "confirmation_state": "confirmed",
        "status": "draft",
        "is_stale": False,
        "version": 1,
        "source_fingerprint": "fp-confirmed-v1",
        "source_records": ["evt-001", "venue", "spk-003", "sch-003"],
        "missing_details": [],
        "content": {
            "session_details": {"timing_state": "confirmed"},
            "event_overview": {"event_name": "DubHacks Workshop 2026"},
        },
        "rendered_body": "# Speaker Briefing: Prof. Sara Kim\n\nAll details confirmed.",
    }
    isolated_store.add_briefing(confirmed_briefing)

    # 2. Mark briefing as sent (succeeds because commitments are confirmed)
    sent_res = mark_briefing_sent(isolated_store, "brf-spk-confirmed")
    assert sent_res["status"] == "sent"

    sent_b = isolated_store.find_briefing("brf-spk-confirmed")
    assert sent_b["status"] == "sent"
    assert sent_b["version"] == 1

    # 3. Attempting direct in-place mutation of sent briefing content MUST raise ValueError
    with pytest.raises(ValueError, match="immutable"):
        isolated_store.update_briefing(
            "brf-spk-confirmed",
            {"rendered_body": "Tampered body", "session_time": "11:00 - 12:00"},
        )

    # 4. Subsequent source change
    isolated_store.update_schedule_item("sch-003", {"start_time": "10:00"})

    # 5. Saving updated draft through upsert_briefing_version safely archives sent version
    revised_draft = copy.deepcopy(confirmed_briefing)
    revised_draft["source_fingerprint"] = "fp-confirmed-v2"
    revised_draft["status"] = "draft"
    save_briefing_draft(isolated_store, briefing_data=revised_draft)

    updated = isolated_store.find_briefing("brf-spk-confirmed")
    assert updated["version"] == 2
    assert updated["status"] == "draft"

    sent_snapshots = [h for h in updated["history"] if h["status"] == "sent"]
    assert len(sent_snapshots) == 1
    assert sent_snapshots[0]["version"] == 1


# ---------------------------------------------------------------------------
# 9. Strict Readiness and Sending Guards (No Boolean Override)
# ---------------------------------------------------------------------------
def test_attempted_readiness_bypass_is_strictly_blocked(isolated_store):
    """Cannot mark briefing as ready or sent while required external commitments remain unverified.

    No boolean bypass (allow_unverified_override) is permitted; ready/sent transitions are strictly blocked.
    """
    draft = preview_briefing(isolated_store, "speaker", "spk-003")["briefing"]
    save_briefing_draft(isolated_store, briefing_data=draft)

    # Evaluate readiness
    is_ready, reasons = evaluate_briefing_readiness(draft)
    assert is_ready is False
    assert len(reasons) > 0

    # 1. mark_briefing_sent MUST fail
    with pytest.raises(ValueError, match="required external commitments remain unverified"):
        mark_briefing_sent(isolated_store, draft["id"])

    # 2. save_briefing_draft with status='ready' MUST fail
    draft["status"] = "ready"
    with pytest.raises(ValueError, match="required external commitments remain unverified"):
        save_briefing_draft(isolated_store, briefing_data=draft)

    # 3. save_briefing_draft with status='sent' MUST fail
    draft["status"] = "sent"
    with pytest.raises(ValueError, match="required external commitments remain unverified"):
        save_briefing_draft(isolated_store, briefing_data=draft)

    # 4. Attempting to pass allow_unverified_override MUST raise TypeError (parameter removed)
    with pytest.raises(TypeError):
        mark_briefing_sent(isolated_store, draft["id"], allow_unverified_override=True)  # type: ignore

    with pytest.raises(TypeError):
        save_briefing_draft(isolated_store, briefing_data=draft, allow_unverified_override=True)  # type: ignore


# ---------------------------------------------------------------------------
# 10. FastMCP Server Tool Scoping & Read-Only Tests
# ---------------------------------------------------------------------------
def test_draft_saving_and_sent_operations_are_not_exposed_in_fastmcp():
    """Verify that save_briefing_draft and mark_briefing_sent are NOT exposed on FastMCP server."""
    import server

    # Neither save_briefing_draft nor mark_briefing_sent should be imported or exposed in server
    assert "save_briefing_draft" not in server.__dict__
    assert "mark_briefing_sent" not in server.__dict__

    # All logistics briefing tools in server are strictly read-only tools
    logistics_briefing_tools = [
        name for name, val in server.__dict__.items()
        if name.startswith("logistics_") and "briefing" in name.lower() and callable(val)
    ]
    assert set(logistics_briefing_tools) == {
        "logistics_preview_briefing",
        "logistics_list_briefings",
        "logistics_check_stale_briefings",
    }


def test_mcp_briefing_tools_are_strictly_read_only(isolated_store, monkeypatch):
    """Calling MCP briefing tools cannot mutate the persistent store."""
    backend = MockBackend(store=isolated_store)
    import server
    monkeypatch.setattr(server, "BACKEND", backend)

    initial_briefings_count = len(isolated_store.all_briefings())
    initial_dump = json.dumps(isolated_store._data, sort_keys=True)

    # 1. logistics_preview_briefing
    prev_resp = logistics_preview_briefing(role="speaker", recipient_id="spk-003")
    assert prev_resp["is_preview"] is True
    assert prev_resp["_canvas"]["module"] == "briefing_view"
    assert "Prof. Sara Kim" in prev_resp["briefing"]["recipient_name"]

    # 2. logistics_list_briefings
    list_resp = logistics_list_briefings(role="speaker")
    assert list_resp["found"] is True
    assert list_resp["_canvas"]["module"] == "briefing_list"

    # 3. logistics_check_stale_briefings
    audit_resp = logistics_check_stale_briefings()
    assert "stale_count" in audit_resp
    assert audit_resp["_canvas"]["module"] == "briefing_audit"

    # Store was NOT mutated at all
    assert len(isolated_store.all_briefings()) == initial_briefings_count
    final_dump = json.dumps(isolated_store._data, sort_keys=True)
    assert initial_dump == final_dump, "MCP preview/audit tools modified store data!"


def test_mcp_preview_vendor_and_volunteer(isolated_store, monkeypatch):
    """FastMCP preview works for vendor and volunteer roles."""
    backend = MockBackend(store=isolated_store)
    import server
    monkeypatch.setattr(server, "BACKEND", backend)

    # Vendor preview
    vnd_resp = logistics_preview_briefing(role="vendor", recipient_id="vnd-003")
    assert vnd_resp["is_preview"] is True
    assert "Taste of Seoul" in vnd_resp["briefing"]["recipient_name"]
    assert "Stevens Way service bay" in vnd_resp["briefing"]["rendered_body"]

    # Volunteer preview
    vol_resp = logistics_preview_briefing(role="volunteer", recipient_id="vol-001")
    assert vol_resp["is_preview"] is True
    assert "Check-in Desk" in vol_resp["briefing"]["recipient_name"]
    assert "Gates Hall 106 Lobby" in vol_resp["briefing"]["rendered_body"]
