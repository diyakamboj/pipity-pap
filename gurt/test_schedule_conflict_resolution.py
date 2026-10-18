"""Focused Automated Tests for Gurt Schedule Conflict Resolution Workflow.

Covers:
1. Read-only conflict detection and resolution previewing (zero database side-effects).
2. Successful resolution application and automatic conflict recalculation.
3. Persistence of approved schedule changes across database connections.
4. Stale proposal protection (SHA-256 state fingerprint mismatch rejection).
5. Input validation (invalid event ID, session ID, time format, inverted time, empty room).
6. Schedule dependency precedence enforcement (cannot start before predecessor finishes).
7. Event boundary isolation (changes in one event cannot modify or resolve conflicts in another).
8. FastAPI REST endpoints (/api/logistics/conflicts/proposals, /api/logistics/conflicts/apply).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any

# Add gurt root to sys.path
GURT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GURT_ROOT))

from gurt.db import (
    get_connection,
    init_db,
    get_schedule_items,
    get_schedule_item_by_id,
    save_schedule_item,
    clear_schedule_items,
    update_schedule_item,
    get_audit_logs
)
from gurt.logistics.conflict_engine import (
    detect_schedule_conflicts,
    propose_conflict_resolutions,
    apply_conflict_resolution,
    compute_session_fingerprint,
    is_valid_time_str,
    validate_schedule_dependencies
)
from gurt.tools.logistics_tools import (
    tool_detect_schedule_conflicts,
    tool_propose_conflict_resolutions,
    tool_apply_conflict_resolution
)
from gurt.api.server import app
from fastapi.testclient import TestClient


class TestScheduleConflictResolution(unittest.TestCase):
    """Test suite for the persistent backend schedule conflict resolution workflow."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        """Set up an isolated test event with controlled schedule conflicts."""
        self.test_event_id = "evt-test-logistics-99"
        clear_schedule_items(self.test_event_id)

        # Seed 3 sessions in the same exclusive room to produce both overlap and buffer conflicts
        # Session 1: 09:00 - 10:00 in "Room 214"
        self.item_1 = save_schedule_item(
            event_id=self.test_event_id,
            time_slot="09:00 - 10:00",
            activity="Opening Keynote",
            location="Room 214",
            owner="Alice",
            activity_type="presentation",
            dependencies="None",
            notes="Opening session"
        )
        # Update start_time, end_time, room
        update_schedule_item(self.item_1["id"], {"start_time": "09:00", "end_time": "10:00", "room": "Room 214"}, event_id=self.test_event_id)

        # Session 2: 10:00 - 11:00 in "Room 214" -> Exactly 0m gap after Session 1 (requires 10m buffer!)
        self.item_2 = save_schedule_item(
            event_id=self.test_event_id,
            time_slot="10:00 - 11:00",
            activity="Hands-on Workshop",
            location="Room 214",
            owner="Bob",
            activity_type="workshop",
            dependencies=self.item_1["id"],
            notes="Requires 10m buffer after Session 1"
        )
        update_schedule_item(self.item_2["id"], {"start_time": "10:00", "end_time": "11:00", "room": "Room 214", "dependencies": self.item_1["id"]}, event_id=self.test_event_id)

        # Session 3: 10:30 - 11:30 in "Room 214" -> Direct double-booking overlap with Session 2
        self.item_3 = save_schedule_item(
            event_id=self.test_event_id,
            time_slot="10:30 - 11:30",
            activity="Lightning Demos",
            location="Room 214",
            owner="Charlie",
            activity_type="demos",
            dependencies="None",
            notes="Collides with Session 2"
        )
        update_schedule_item(self.item_3["id"], {"start_time": "10:30", "end_time": "11:30", "room": "Room 214"}, event_id=self.test_event_id)

    def tearDown(self):
        clear_schedule_items(self.test_event_id)

    def test_01_detect_and_preview_is_strictly_read_only(self):
        """Conflict detection and resolution proposal must never mutate the database."""
        # 1. Snapshot database state before detection
        items_before = get_schedule_items(self.test_event_id)

        # 2. Run conflict detection
        conflicts_result = detect_schedule_conflicts(self.test_event_id)
        self.assertGreaterEqual(conflicts_result["total_conflicts"], 2)

        # 3. Request resolution proposals
        proposals_result = propose_conflict_resolutions(event_id=self.test_event_id)
        self.assertIn("proposals", proposals_result)
        self.assertGreater(len(proposals_result["proposals"]), 0)

        # 4. Verify database state is 100% identical
        items_after = get_schedule_items(self.test_event_id)
        self.assertEqual(len(items_before), len(items_after))
        for b, a in zip(items_before, items_after):
            self.assertEqual(b["time_slot"], a["time_slot"])
            self.assertEqual(b["start_time"], a["start_time"])
            self.assertEqual(b["end_time"], a["end_time"])

    def test_02_successful_resolution_application_and_recalculation(self):
        """Applying an approved resolution updates the DB and recalculates conflicts."""
        # Detect conflicts
        conflicts_data = detect_schedule_conflicts(self.test_event_id)
        # Find turnover buffer conflict between Session 1 and Session 2
        buffer_conflict = next(
            (c for c in conflicts_data["conflicts"] if c["conflict_type"] == "insufficient_turnover_buffer" and c["session_a_id"] == self.item_1["id"]),
            None
        )
        self.assertIsNotNone(buffer_conflict, "Expected buffer conflict between Session 1 and 2")

        # Get proposal
        proposal_data = propose_conflict_resolutions(conflict_id=buffer_conflict["id"], event_id=self.test_event_id)
        self.assertTrue(len(proposal_data.get("resolutions", [])) > 0)
        resolution = proposal_data["resolutions"][0]

        # Verify resolution structure
        self.assertEqual(resolution["target_session_id"], self.item_2["id"])
        self.assertIn("expected_fingerprint", resolution)
        self.assertIn("proposed_changes", resolution)

        # Apply resolution
        apply_res = apply_conflict_resolution(
            event_id=self.test_event_id,
            session_id=resolution["target_session_id"],
            proposed_changes=resolution["proposed_changes"],
            expected_fingerprint=resolution["expected_fingerprint"],
            conflict_id=buffer_conflict["id"]
        )

        self.assertEqual(apply_res["status"], "applied")
        self.assertTrue(apply_res["is_conflict_resolved"])
        self.assertEqual(apply_res["session_id"], self.item_2["id"])

        # Verify updated session in database
        updated_db_item = get_schedule_item_by_id(self.item_2["id"], event_id=self.test_event_id)
        self.assertIsNotNone(updated_db_item)
        self.assertEqual(updated_db_item["start_time"], resolution["proposed_changes"]["start_time"])
        self.assertEqual(updated_db_item["end_time"], resolution["proposed_changes"]["end_time"])

        # Verify that the buffer conflict is no longer in recalculated conflicts
        recalculated_ids = [c["id"] for c in apply_res["recalculated_conflicts"]["conflicts"]]
        self.assertNotIn(buffer_conflict["id"], recalculated_ids)

        # Verify audit trail record was created
        audit_logs = get_audit_logs(self.test_event_id)
        self.assertTrue(any(a["action"] == "schedule_conflict_resolved" and a["target_id"] == self.item_2["id"] for a in audit_logs))

    def test_03_persistence_across_connection_reload(self):
        """Changes must persist to disk and survive database reload."""
        # Update session 3 to 12:00 - 13:00 to clear the double-booking
        apply_res = apply_conflict_resolution(
            event_id=self.test_event_id,
            session_id=self.item_3["id"],
            proposed_changes={"start_time": "12:00", "end_time": "13:00"}
        )
        self.assertEqual(apply_res["status"], "applied")

        # Open completely fresh SQLite connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT start_time, end_time, room, time_slot FROM schedules WHERE id = ? AND event_id = ?", (self.item_3["id"], self.test_event_id))
        row = c.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["start_time"], "12:00")
        self.assertEqual(row["end_time"], "13:00")
        self.assertEqual(row["time_slot"], "12:00 - 13:00")

    def test_04_stale_proposal_rejection(self):
        """If a session is modified after proposal generation, apply must fail closed."""
        # 1. Generate proposal and capture fingerprint
        proposal_data = propose_conflict_resolutions(event_id=self.test_event_id)
        self.assertTrue(len(proposal_data["proposals"]) > 0)
        resolution = proposal_data["proposals"][0]
        target_id = resolution["target_session_id"]
        original_fp = resolution["expected_fingerprint"]

        # 2. Simulate concurrent edit to target session
        update_schedule_item(target_id, {"room": "Ballroom B"}, event_id=self.test_event_id)

        # 3. Attempt to apply proposal with the old fingerprint
        apply_res = apply_conflict_resolution(
            event_id=self.test_event_id,
            session_id=target_id,
            proposed_changes=resolution["proposed_changes"],
            expected_fingerprint=original_fp
        )

        # 4. Assert rejection with stale_proposal
        self.assertEqual(apply_res["status"], "error")
        self.assertEqual(apply_res["error"], "stale_proposal")
        self.assertIn("modified since resolution was generated", apply_res["message"])

    def test_05_input_validations(self):
        """Strict validation of event_id, session_id, time formats, and rooms."""
        # Nonexistent event
        res = apply_conflict_resolution("evt-nonexistent", self.item_1["id"], {"start_time": "14:00", "end_time": "15:00"})
        self.assertEqual(res["error"], "not_found")

        # Nonexistent session
        res = apply_conflict_resolution(self.test_event_id, "sch-nonexistent", {"start_time": "14:00", "end_time": "15:00"})
        self.assertEqual(res["error"], "not_found")

        # Invalid time string format
        res = apply_conflict_resolution(self.test_event_id, self.item_1["id"], {"start_time": "25:00", "end_time": "15:00"})
        self.assertEqual(res["error"], "invalid_time")

        res = apply_conflict_resolution(self.test_event_id, self.item_1["id"], {"start_time": "09:00", "end_time": "99:99"})
        self.assertEqual(res["error"], "invalid_time")

        # Inverted time (start >= end)
        res = apply_conflict_resolution(self.test_event_id, self.item_1["id"], {"start_time": "15:00", "end_time": "14:00"})
        self.assertEqual(res["error"], "invalid_time")

        res = apply_conflict_resolution(self.test_event_id, self.item_1["id"], {"start_time": "14:00", "end_time": "14:00"})
        self.assertEqual(res["error"], "invalid_time")

        # Empty room
        res = apply_conflict_resolution(self.test_event_id, self.item_1["id"], {"start_time": "14:00", "end_time": "15:00", "room": ""})
        self.assertEqual(res["error"], "invalid_room")

    def test_06_dependency_precedence_enforcement(self):
        """A session cannot be scheduled before its predecessor finishes."""
        # item_2 depends on item_1 (which finishes at 10:00).
        # Attempting to move item_2 to 08:30 - 09:30 should fail.
        res = apply_conflict_resolution(
            event_id=self.test_event_id,
            session_id=self.item_2["id"],
            proposed_changes={"start_time": "08:30", "end_time": "09:30"}
        )
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "dependency_violation")
        self.assertIn("cannot start before predecessor", res["message"])

    def test_07_event_isolation(self):
        """Cross-event resolution attempts must be blocked."""
        other_event_id = "evt-isolated-other-01"
        clear_schedule_items(other_event_id)

        # Attempt to modify item_1 (which belongs to test_event_id) under other_event_id
        res = apply_conflict_resolution(
            event_id=other_event_id,
            session_id=self.item_1["id"],
            proposed_changes={"start_time": "15:00", "end_time": "16:00"}
        )
        # Should not find the session under the wrong event
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "not_found")

    def test_08_rest_api_endpoints(self):
        """Verify GET proposals and POST apply REST endpoints via FastAPI TestClient."""
        # 1. GET proposals
        resp = self.client.get(f"/api/logistics/conflicts/proposals?event_id={self.test_event_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("proposals", data)
        self.assertGreater(data["total_proposals"], 0)

        first_proposal = data["proposals"][0]

        # 2. POST apply with valid proposal
        apply_payload = {
            "event_id": self.test_event_id,
            "session_id": first_proposal["target_session_id"],
            "proposed_changes": first_proposal["proposed_changes"],
            "expected_fingerprint": first_proposal["expected_fingerprint"],
            "conflict_id": first_proposal["conflict_id"]
        }
        resp = self.client.post("/api/logistics/conflicts/apply", json=apply_payload)
        self.assertEqual(resp.status_code, 200)
        apply_data = resp.json()
        self.assertEqual(apply_data["status"], "applied")
        self.assertTrue(apply_data["is_conflict_resolved"])

        # 3. POST apply with stale fingerprint (HTTP 409)
        stale_payload = {
            "event_id": self.test_event_id,
            "session_id": first_proposal["target_session_id"],
            "proposed_changes": {"start_time": "17:00", "end_time": "18:00"},
            "expected_fingerprint": "stale_hash_12345"
        }
        resp = self.client.post("/api/logistics/conflicts/apply", json=stale_payload)
        self.assertEqual(resp.status_code, 409)

        # 4. POST apply with invalid time (HTTP 400)
        bad_time_payload = {
            "event_id": self.test_event_id,
            "session_id": first_proposal["target_session_id"],
            "proposed_changes": {"start_time": "25:00", "end_time": "18:00"}
        }
        resp = self.client.post("/api/logistics/conflicts/apply", json=bad_time_payload)
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
