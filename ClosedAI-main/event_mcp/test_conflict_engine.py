"""Tests for Logistics L3: Conflict Detection, Impact Analysis, and Resolution Proposals."""

import copy
import hashlib
import json
import os
import shutil
import tempfile
import pytest

from conflict_engine import (
    ConflictSeverity,
    ConflictType,
    analyze_schedule_impact,
    calculate_duration_minutes,
    detect_schedule_conflicts,
    intervals_overlap,
    is_shared_or_nonexclusive_space,
    minutes_to_time,
    propose_conflict_resolutions,
    time_to_minutes,
)
from event_store import ConfirmationState, EventStore
import server


@pytest.fixture
def isolated_store(tmp_path):
    """Provide a fresh, isolated EventStore in a temporary directory for each test."""
    store_file = tmp_path / "test_event_data.json"
    store = EventStore(storage_path=str(store_file))
    return store


# ===========================================================================
# 1. Interval & Exclusivity Logic Tests
# ===========================================================================
def test_half_open_intervals_no_false_overlap():
    """Verify that half-open interval [start, end) avoids false-positive boundary overlaps."""
    # [09:30, 10:30) and [10:30, 11:00) should NOT overlap
    assert not intervals_overlap("09:30", "10:30", "10:30", "11:00")
    assert not intervals_overlap("10:30", "11:00", "09:30", "10:30")

    # [08:00, 09:00) and [09:00, 09:30) should NOT overlap
    assert not intervals_overlap("08:00", "09:00", "09:00", "09:30")


def test_intervals_actual_overlap():
    """Verify that genuinely overlapping intervals return True."""
    # [09:30, 10:30) and [10:00, 11:00) overlap between 10:00 and 10:30
    assert intervals_overlap("09:30", "10:30", "10:00", "11:00")
    # Subsumed interval: [09:00, 12:00) and [10:00, 11:00)
    assert intervals_overlap("09:00", "12:00", "10:00", "11:00")


def test_shared_or_nonexclusive_spaces():
    """Verify identification of shared/nonexclusive areas vs. exclusive halls."""
    assert is_shared_or_nonexclusive_space("Gates Hall 106 Lobby")
    assert is_shared_or_nonexclusive_space("Patio/Lounge")
    assert is_shared_or_nonexclusive_space("Main Foyer")
    assert is_shared_or_nonexclusive_space("Registration Atrium")

    # Exclusive auditorium
    assert not is_shared_or_nonexclusive_space("Gates Hall 106")
    assert not is_shared_or_nonexclusive_space("Room 204")
    assert not is_shared_or_nonexclusive_space("Auditorium B")


# ===========================================================================
# 2. Baseline Conflict Scan & Boundary Verification
# ===========================================================================
def test_baseline_schedule_has_no_room_overlaps(isolated_store):
    """The default seed schedule has contiguous half-open slots with no direct room overlaps."""
    report = detect_schedule_conflicts(isolated_store)
    room_conflicts = [c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP]
    assert len(room_conflicts) == 0


def test_shared_space_simultaneous_activities_no_conflict(isolated_store):
    """Two activities in a shared space (e.g. Lobby or Patio) do not produce a ROOM_OVERLAP conflict."""
    # sch-002 is in Gates Hall 106 Lobby (09:00-09:30)
    # Add another activity in Gates Hall 106 Lobby during overlapping time (09:15-09:45)
    isolated_store.add_schedule_item(
        {
            "id": "sch-test-lobby",
            "title": "Sponsor Booth Setup in Lobby",
            "start_time": "09:15",
            "end_time": "09:45",
            "room": "Gates Hall 106 Lobby",
            "item_type": "sponsor",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Table in shared lobby area.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    lobby_room_conflicts = [
        c
        for c in report["conflicts"]
        if c["conflict_type"] == ConflictType.ROOM_OVERLAP
        and "Gates Hall 106 Lobby" in c["affected_resource_ids"]
    ]
    assert len(lobby_room_conflicts) == 0


# ===========================================================================
# 3. Room & Exclusive Resource Overlaps
# ===========================================================================
def test_detect_exclusive_room_overlap(isolated_store):
    """Adding an overlapping session in Gates Hall 106 triggers a ROOM_OVERLAP conflict with stable ID."""
    # Keynote sch-003 is 09:30-10:30 in Gates Hall 106
    # Add competing session in same exclusive room from 10:00 to 11:00
    isolated_store.add_schedule_item(
        {
            "id": "sch-overlap-001",
            "title": "Competing AI Workshop",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "confirmed",
            "dependencies": [],
            "notes": "Double booked workshop.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    room_conflicts = [c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP]
    assert len(room_conflicts) >= 1

    cfl = next(c for c in room_conflicts if "sch-overlap-001" in c["affected_schedule_ids"])
    assert "sch-003" in cfl["affected_schedule_ids"]
    assert cfl["affected_resource_ids"] == ["Gates Hall 106"]
    # Stable ID format check
    assert cfl["id"] == "cfl-room-sch-003-sch-overlap-001"
    assert cfl["severity"] in (ConflictSeverity.HIGH, ConflictSeverity.CRITICAL)


def test_detect_speaker_double_booking(isolated_store):
    """Assigning the same speaker to overlapping sessions triggers RESOURCE_CONTENTION."""
    # Prof. Sara Kim (spk-003) is in sch-003 (09:30-10:30)
    # Add parallel session with same speaker in a different room
    isolated_store.add_schedule_item(
        {
            "id": "sch-speaker-double",
            "title": "VIP Roundtable with Prof. Kim",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Room 204",
            "item_type": "session",
            "speaker_id": "spk-003",
            "confirmation_state": "confirmed",
            "dependencies": [],
            "notes": "Parallel session.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    speaker_conflicts = [
        c
        for c in report["conflicts"]
        if c["conflict_type"] == ConflictType.RESOURCE_CONTENTION
        and "spk-003" in c["affected_resource_ids"]
    ]
    assert len(speaker_conflicts) == 1
    cfl = speaker_conflicts[0]
    assert cfl["verification_status"] == "verified"  # Prof. Kim status is confirmed
    assert cfl["severity"] == ConflictSeverity.CRITICAL
    assert "sch-003" in cfl["affected_schedule_ids"]
    assert "sch-speaker-double" in cfl["affected_schedule_ids"]


# ===========================================================================
# 4. Setup, Teardown, and Buffer Conflicts
# ===========================================================================
def test_vendor_setup_buffer_violation_detected(isolated_store):
    """When vendor source notes specify setup time (e.g. T-60 min) and preceding session leaves insufficient buffer, flag it."""
    # vnd-001 (Campus Catering Co.) notes: "Setup at T-60 min."
    # Add catering lunch in Gates Hall 106 from 12:30-13:30 with vnd-001
    # Preceding workshop sch-005 in Gates Hall 106 ends at 12:00 (or 12:30 in seed data)
    # If sch-005 ends at 12:15, only 15 min buffer exists, violating 60 min requirement
    isolated_store.add_schedule_item(
        {
            "id": "sch-catering-buffer-test",
            "title": "Campus Catering Banquet",
            "start_time": "12:30",
            "end_time": "13:30",
            "room": "Gates Hall 106",
            "item_type": "meal",
            "vendor_id": "vnd-001",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Requires 60 min setup.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    buffer_conflicts = [
        c
        for c in report["conflicts"]
        if c["conflict_type"] == ConflictType.INSUFFICIENT_BUFFER
        and "vnd-001" in c["affected_resource_ids"]
    ]
    assert len(buffer_conflicts) == 1
    cfl = buffer_conflicts[0]
    assert "vnd-001" in cfl["affected_resource_ids"]
    assert cfl["evidence"]["required_buffer_minutes"] == 60


def test_missing_buffer_constraint_reported_rather_than_invented(isolated_store):
    """When turnover buffer between sessions is unrecorded, report missing constraint rather than fabricating conflict."""
    report = detect_schedule_conflicts(isolated_store)
    # Check that missing constraints capture unspecified turnover buffers
    unspecified_buffers = [
        m for m in report["missing_constraints"] if m.get("type") == "unspecified_turnover_buffer"
    ]
    assert len(unspecified_buffers) >= 1
    assert "Zero turnover buffer" in unspecified_buffers[0]["note"]


# ===========================================================================
# 5. Vendor Timing and Confirmation States
# ===========================================================================
def test_vendor_delivery_extending_past_service_start(isolated_store):
    """Detect when vendor delivery window extends past scheduled session start."""
    # Update sch-006 notes to have delivery window 12:15-12:45 for lunch starting at 12:30
    isolated_store.update_schedule_item(
        "sch-006",
        {
            "notes": "Taste of Seoul buffet for 80 attendees; delivery window targeted for 12:15-12:45.",
        },
    )

    report = detect_schedule_conflicts(isolated_store)
    misalignments = [
        c for c in report["conflicts"] if c["conflict_type"] == ConflictType.VENDOR_SERVICE_MISALIGNMENT
    ]
    assert len(misalignments) == 1
    cfl = misalignments[0]
    assert cfl["affected_resource_ids"] == ["vnd-003"]
    # Vendor booking is unconfirmed in seed data, so verification status is provisional
    assert cfl["verification_status"] == "provisional"
    assert cfl["severity"] == ConflictSeverity.HIGH

    # If vendor is confirmed, status becomes verified
    isolated_store.update_vendor("vnd-003", {"confirmed": True})
    report2 = detect_schedule_conflicts(isolated_store)
    cfl2 = next(
        c for c in report2["conflicts"] if c["conflict_type"] == ConflictType.VENDOR_SERVICE_MISALIGNMENT
    )
    assert cfl2["verification_status"] == "verified"
    assert cfl2["severity"] == ConflictSeverity.CRITICAL


# ===========================================================================
# 6. Confirmed vs. Assumed Venue Constraints
# ===========================================================================
def test_venue_constraint_violations_provisional_when_assumed(isolated_store):
    """Violations of assumed venue constraints must be flagged as provisional."""
    # Venue access hours: 08:00 - 18:00 (assumed)
    # Move sch-010 (Teardown) to end at 18:30 (past access_end and 18:00 curfew)
    isolated_store.update_schedule_item("sch-010", {"end_time": "18:30"})

    report = detect_schedule_conflicts(isolated_store)
    venue_conflicts = [
        c for c in report["conflicts"] if c["conflict_type"] == ConflictType.VENUE_CONSTRAINT_VIOLATION
    ]
    assert len(venue_conflicts) >= 1

    # Because venue_constraints confirmation_state is "assumed", it must be flagged provisional
    for vc in venue_conflicts:
        assert vc["verification_status"] == "provisional"

    # Now confirm venue constraints in store
    isolated_store.update_venue_constraints({"confirmation_state": ConfirmationState.CONFIRMED.value})

    report_confirmed = detect_schedule_conflicts(isolated_store)
    venue_conflicts_conf = [
        c
        for c in report_confirmed["conflicts"]
        if c["conflict_type"] == ConflictType.VENUE_CONSTRAINT_VIOLATION
    ]
    assert len(venue_conflicts_conf) >= 1
    for vc in venue_conflicts_conf:
        assert vc["verification_status"] == "verified"


def test_venue_capacity_violation_detection(isolated_store):
    """When event attendee count exceeds venue max_capacity, detect capacity conflict."""
    # Update event attendees to 120 (max_capacity is 100)
    event = isolated_store.get_event()
    event["attendees"] = 120
    isolated_store._data["event"] = event
    isolated_store.save()

    report = detect_schedule_conflicts(isolated_store)
    capacity_conflicts = [
        c
        for c in report["conflicts"]
        if c["id"] == "cfl-venue-capacity-event"
    ]
    assert len(capacity_conflicts) == 1
    assert capacity_conflicts[0]["evidence"]["attendees"] == 120
    assert capacity_conflicts[0]["evidence"]["max_capacity"] == 100


# ===========================================================================
# 7. Downstream Impact Analysis
# ===========================================================================
def test_analyze_schedule_impact_does_not_mutate_store(isolated_store):
    """Verify that analyzing schedule impact leaves the EventStore completely unchanged."""
    before_state = copy.deepcopy(isolated_store._data)

    # Propose moving Keynote sch-003 to 14:00-15:00
    impact = analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-003",
        proposed_start="14:00",
        proposed_end="15:00",
    )

    after_state = copy.deepcopy(isolated_store._data)
    assert before_state == after_state
    assert impact["schedule_item_id"] == "sch-003"
    assert impact["requires_human_approval"] is True


def test_analyze_schedule_impact_detects_introduced_conflicts(isolated_store):
    """Moving a session to overlap with another introduces conflicts in preview."""
    # Propose moving Morning Workshop sch-005 (11:00-12:30) to 09:30-11:00 (overlaps with sch-003 Keynote 09:30-10:30)
    impact = analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-005",
        proposed_start="09:30",
        proposed_end="11:00",
    )

    summary = impact["conflict_summary"]
    assert summary["introduced_conflicts_count"] >= 1
    assert any("sch-003" in c["affected_schedule_ids"] for c in summary["introduced_conflicts"])


def test_analyze_schedule_impact_stale_briefing_detection(isolated_store):
    """Moving Prof. Sara Kim's keynote session causes her speaker briefing (brf-001) to become stale."""
    # Ensure brf-001 has current fingerprint
    b_before = isolated_store.find_briefing("brf-001")
    assert b_before is not None

    # Propose moving Keynote sch-003 from 09:30-10:30 to 11:00-12:00
    impact = analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-003",
        proposed_start="11:00",
        proposed_end="12:00",
    )

    stale_briefings = impact["stale_briefings"]
    stale_ids = [b["briefing_id"] for b in stale_briefings]
    assert "brf-001" in stale_ids
    # Vendor briefing should NOT be marked stale by speaker session move
    assert "brf-002" not in stale_ids


def test_analyze_schedule_impact_task_dependencies(isolated_store):
    """Schedule changes identify linked operational tasks and downstream dependent sessions."""
    # sch-003 is linked to tasks and sch-004 depends on sch-003
    # If we propose shifting sch-003 to end at 11:00 (past sch-004 start at 10:30)
    impact = analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-003",
        proposed_start="10:00",
        proposed_end="11:00",
    )

    downstream = impact["downstream_dependent_sessions"]
    sch_004_dep = next((s for s in downstream if s["session_id"] == "sch-004"), None)
    assert sch_004_dep is not None
    assert sch_004_dep["gap_violation"] is True


# ===========================================================================
# 8. Deterministic Resolution Proposals
# ===========================================================================
def test_propose_conflict_resolutions_room_overlap(isolated_store):
    """Propose deterministic resolutions for room overlap with explicit human approval flag."""
    # Create an overlap: Add a competing workshop from 10:00 to 11:00 in Gates Hall 106
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
            "notes": "Tentative workshop.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP)

    proposals_result = propose_conflict_resolutions(isolated_store, room_cfl["id"])
    assert proposals_result["requires_human_approval"] is True
    assert proposals_result["total_proposals"] >= 1

    proposals = proposals_result["proposals"]
    reschedule_prop = next((p for p in proposals if p["strategy"] == "RESCHEDULE_SESSION"), None)
    if reschedule_prop:
        assert reschedule_prop["requires_human_approval"] is True
        assert len(reschedule_prop["proposed_changes"]) >= 2
        assert reschedule_prop["proposed_changes"][0]["record_type"] == "schedule_item"

    # Verify that secondary room proposal does not invent nonexistent rooms
    room_check_prop = next((p for p in proposals if p["strategy"] == "ROOM_REASSIGNMENT_CHECK"), None)
    assert room_check_prop is not None
    assert "Gates Hall 106 is the only confirmed auditorium room" in room_check_prop["description"]


def test_propose_conflict_resolutions_vendor_window(isolated_store):
    """Propose vendor delivery window adjustment when service misalignment occurs."""
    # Create vendor service misalignment
    isolated_store.update_schedule_item(
        "sch-006",
        {
            "notes": "Taste of Seoul buffet for 80 attendees; delivery window targeted for 12:15-12:45.",
        },
    )

    report = detect_schedule_conflicts(isolated_store)
    misalign_cfl = next(
        c for c in report["conflicts"] if c["conflict_type"] == ConflictType.VENDOR_SERVICE_MISALIGNMENT
    )

    proposals_result = propose_conflict_resolutions(isolated_store, misalign_cfl["id"])
    assert proposals_result["total_proposals"] >= 1
    v_prop = next(p for p in proposals_result["proposals"] if p["strategy"] == "ADJUST_VENDOR_DELIVERY_WINDOW")
    assert v_prop["requires_human_approval"] is True
    assert "Taste of Seoul" in v_prop["title"]
    assert "Written confirmation from Taste of Seoul" in v_prop["required_confirmations"][0]


# ===========================================================================
# 9. MCP Server Integration & Read-Only Invariance
# ===========================================================================
def test_mcp_conflict_tools_read_only_and_functional(isolated_store, monkeypatch):
    """Verify that FastMCP conflict tools in server.py operate read-only and return valid structures."""
    # Point server BACKEND to isolated_store
    monkeypatch.setattr(server.BACKEND, "store", isolated_store)

    # 1. logistics_detect_conflicts
    detect_res = server.logistics_detect_conflicts()
    assert "has_conflicts" in detect_res
    assert "_canvas" in detect_res
    assert detect_res["_canvas"]["module"] == "conflict_report"

    # 2. logistics_analyze_impact
    impact_res = server.logistics_analyze_impact(
        schedule_item_id="sch-003",
        proposed_start="10:00",
        proposed_end="11:00",
    )
    assert impact_res["schedule_item_id"] == "sch-003"
    assert impact_res["requires_human_approval"] is True
    assert "_canvas" in impact_res

    # 3. logistics_propose_resolutions on non-existent conflict
    prop_res = server.logistics_propose_resolutions(conflict_id="cfl-nonexistent")
    assert prop_res["found"] is False
    assert "error" in prop_res


# ===========================================================================
# 10. Audit & Safety Invariance Regression Tests
# ===========================================================================
def test_proposed_slot_occupied_by_third_session_rejected(isolated_store):
    """Specifically verify that 13:30-14:30 in Gates Hall 106 is NOT free (occupied by sch-007) and never proposed."""
    # sch-007 is Afternoon Session: AI for Civic Engagement, 13:30-15:00 in Gates Hall 106
    sch_007 = isolated_store.find_schedule_item("sch-007")
    assert sch_007 is not None
    assert sch_007["start_time"] == "13:30"
    assert sch_007["end_time"] == "15:00"
    assert sch_007["room"] == "Gates Hall 106"

    # Add a competing workshop that overlaps with sch-003 (09:30-10:30)
    isolated_store.add_schedule_item(
        {
            "id": "sch-compete-audit",
            "title": "Competing Morning Workshop",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Tentative workshop.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP)

    proposals_result = propose_conflict_resolutions(isolated_store, room_cfl["id"])
    proposals = proposals_result["proposals"]

    # Verify that NO proposal suggests 13:30-14:30 or any window overlapping sch-007 (13:30-15:00)
    for p in proposals:
        if p.get("strategy") == "RESCHEDULE_SESSION":
            changes = {ch["field"]: ch["after"] for ch in p.get("proposed_changes", [])}
            prop_start = changes.get("start_time")
            prop_end = changes.get("end_time")
            assert prop_start is not None and prop_end is not None
            # Must NOT overlap with sch-007 (13:30-15:00)
            assert not intervals_overlap(prop_start, prop_end, "13:30", "15:00")
            assert prop_start != "13:30"


def test_no_available_slot_within_venue_hours_returns_explicit_failure(isolated_store):
    """When a conflicting session cannot fit into any available room gap, return NO_FEASIBLE_ALTERNATIVE."""
    # Add a 120-minute session that overlaps with sch-003 in Gates Hall 106
    # In Gates Hall 106, the maximum unbooked interval is 60 minutes (12:30-13:30).
    # A 120-minute session cannot fit anywhere without moving other sessions.
    isolated_store.add_schedule_item(
        {
            "id": "sch-huge-workshop",
            "title": "Extended 2-Hour Hands-on Lab",
            "start_time": "10:00",
            "end_time": "12:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "2-hour workshop.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(
        c
        for c in report["conflicts"]
        if c["conflict_type"] == ConflictType.ROOM_OVERLAP
        and "sch-huge-workshop" in c["affected_schedule_ids"]
    )

    proposals_result = propose_conflict_resolutions(isolated_store, room_cfl["id"])
    proposals = proposals_result["proposals"]

    # Must contain NO_FEASIBLE_ALTERNATIVE proposal for sch-huge-workshop
    no_alt_prop = next((p for p in proposals if p["strategy"] == "NO_FEASIBLE_ALTERNATIVE"), None)
    assert no_alt_prop is not None
    assert "No validated alternative slot found" in no_alt_prop["title"]
    assert no_alt_prop["requires_human_approval"] is True
    assert len(no_alt_prop["proposed_changes"]) == 0


def test_resource_conflict_introduced_by_proposed_move_rejected(isolated_store):
    """If an open room slot introduces a speaker double-booking conflict, it is rejected."""
    # In Gates Hall 106, 12:30-13:30 is unbooked by the room.
    # Add a workshop assigned to Prof. Sara Kim (spk-003) overlapping with sch-003 (09:30-10:30)
    # Also add a meeting for Prof. Sara Kim in Room 204 from 12:30 to 13:30.
    isolated_store.add_schedule_item(
        {
            "id": "sch-kim-lunch-mtg",
            "title": "Prof. Kim Faculty Lunch Meeting",
            "start_time": "12:30",
            "end_time": "13:30",
            "room": "Room 204",
            "item_type": "meeting",
            "speaker_id": "spk-003",
            "confirmation_state": "confirmed",
            "dependencies": [],
            "notes": "External meeting.",
        }
    )
    isolated_store.add_schedule_item(
        {
            "id": "sch-kim-competing-talk",
            "title": "Prof. Kim Special Talk",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "session",
            "speaker_id": "spk-003",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Special talk.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(
        c
        for c in report["conflicts"]
        if c["conflict_type"] == ConflictType.ROOM_OVERLAP
        and "sch-kim-competing-talk" in c["affected_schedule_ids"]
    )

    proposals_result = propose_conflict_resolutions(isolated_store, room_cfl["id"])
    proposals = proposals_result["proposals"]

    # Even though Gates Hall 106 is unbooked at 12:30-13:30, Prof. Kim is in Room 204 at 12:30-13:30.
    # Therefore, 12:30-13:30 must NOT be proposed for sch-kim-competing-talk!
    for p in proposals:
        if p.get("strategy") == "RESCHEDULE_SESSION":
            for ch in p.get("proposed_changes", []):
                if ch.get("field") == "start_time":
                    assert ch["after"] != "12:30"


def test_correctly_computed_downstream_task_and_briefing_ids(isolated_store):
    """Verify that all affected task and briefing IDs in impact analysis genuinely exist in the store."""
    impact = analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-003",
        proposed_start="11:00",
        proposed_end="12:00",
    )

    all_stored_task_ids = {t["id"] for t in isolated_store.all_tasks()}
    all_stored_briefing_ids = {b["id"] for b in isolated_store.all_briefings()}

    # All directly linked task IDs must exist
    for t in impact["affected_operational_tasks"]["directly_linked_tasks"]:
        assert t["id"] in all_stored_task_ids

    # All dependent task IDs must exist
    for t in impact["affected_operational_tasks"]["dependent_tasks"]:
        assert t["id"] in all_stored_task_ids

    # All stale briefing IDs must exist
    for b in impact["stale_briefings"]:
        assert b["briefing_id"] in all_stored_briefing_ids


def test_no_fabricated_downstream_impacts(isolated_store):
    """Moving a session without linked speaker or vendor returns None without fabricated entities."""
    # sch-008 is Hackathon Challenge & Mentoring (no speaker, no vendor)
    sch_008 = isolated_store.find_schedule_item("sch-008")
    assert sch_008["speaker_id"] is None
    assert sch_008["vendor_id"] is None

    impact = analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-008",
        proposed_start="15:30",
        proposed_end="17:00",
    )

    participants = impact["affected_participants"]
    assert participants["speaker"] is None
    assert participants["vendor"] is None


def test_stable_deterministic_proposals(isolated_store):
    """propose_conflict_resolutions returns identical, deterministic proposals across multiple executions."""
    isolated_store.add_schedule_item(
        {
            "id": "sch-det-overlap",
            "title": "Deterministic Test Workshop",
            "start_time": "10:00",
            "end_time": "11:00",
            "room": "Gates Hall 106",
            "item_type": "workshop",
            "confirmation_state": "tentative",
            "dependencies": [],
            "notes": "Deterministic test.",
        }
    )

    report = detect_schedule_conflicts(isolated_store)
    room_cfl = next(c for c in report["conflicts"] if c["conflict_type"] == ConflictType.ROOM_OVERLAP)

    res1 = propose_conflict_resolutions(isolated_store, room_cfl["id"])
    res2 = propose_conflict_resolutions(isolated_store, room_cfl["id"])

    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True)


def test_persistent_state_isolation_and_immutability(isolated_store):
    """Verify that scanning conflicts, analyzing impact, and proposing resolutions never mutate disk storage."""
    # Compute SHA-256 of the store file on disk before operations
    with open(isolated_store.storage_path, "rb") as f:
        before_hash = hashlib.sha256(f.read()).hexdigest()
    before_mtime = os.path.getmtime(isolated_store.storage_path)
    before_data = copy.deepcopy(isolated_store._data)

    # 1. Run conflict detection
    detect_schedule_conflicts(isolated_store)

    # 2. Run impact analysis
    analyze_schedule_impact(
        isolated_store,
        schedule_item_id="sch-003",
        proposed_start="14:00",
        proposed_end="15:00",
    )

    # 3. Run resolution proposals
    propose_conflict_resolutions(isolated_store, conflict_id="cfl-nonexistent")

    # Re-read store file on disk
    with open(isolated_store.storage_path, "rb") as f:
        after_hash = hashlib.sha256(f.read()).hexdigest()
    after_mtime = os.path.getmtime(isolated_store.storage_path)
    after_data = copy.deepcopy(isolated_store._data)

    assert before_hash == after_hash
    assert before_mtime == after_mtime
    assert before_data == after_data

