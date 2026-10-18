"""End-to-End 14-Step Organizer Journey Verification for Gurt Integration.

Validates the full system flow specified in Phase 7:
1. Open Gurt
2. Create or select an event
3. Ask the AI agent about the event
4. View event requirements and available vendor quotes
5. Compare vendors and save a preferred selection
6. Detect a schedule conflict
7. Review and apply a proposed resolution
8. Generate an outreach draft
9. Review and edit the draft
10. Explicitly approve the draft
11. Simulate dispatch and verify delivery status
12. Generate a PDF contract draft
13. Download the document
14. Refresh application and verify data persistence
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Set safe test environment
os.environ["GURT_SIMULATE_OUTREACH"] = "true"
os.environ["GURT_RESEND_API_KEY"] = ""

from gurt.api.server import app
from gurt.db import (
    get_connection,
    init_db,
    update_event_brief,
    get_event_brief,
    get_vendor_by_id,
    query_records,
    get_vendor_requirements,
    list_action_proposals,
    get_pdf_documents,
    get_audit_logs,
)
from gurt.tools.logistics_tools import (
    tool_detect_schedule_conflicts,
    tool_propose_conflict_resolutions,
    tool_apply_conflict_resolution,
)
from gurt.tools.outreach_tools import (
    tool_draft_outreach,
    tool_compose_outreach_draft,
    tool_approve_outreach,
    tool_dispatch_approved_action,
)
from gurt.tools.pdf_tools import (
    inspect_template_fields,
    fill_event_pdf_form,
)


class TestGurtDemoE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        init_db()

    def setUp(self):
        self.event_id = "evt-dubhacks-2026"

    def test_complete_14_step_organizer_journey(self):
        print("\n" + "=" * 70)
        print("STARTING COMPLETE 14-STEP ORGANIZER JOURNEY VALIDATION")
        print("=" * 70)

        # -------------------------------------------------------------
        # STEP 1: Open Gurt
        # -------------------------------------------------------------
        print("\n[Step 1/14] Open Gurt...")
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Gurt", res.text)
        self.assertIn("DubHacks", res.text)

        res_events = self.client.get("/api/events")
        self.assertEqual(res_events.status_code, 200)
        events = res_events.json()
        self.assertTrue(any(e["id"] == self.event_id for e in events))
        print("  ✓ Step 1 Passed: UI loaded and events listed.")

        # -------------------------------------------------------------
        # STEP 2: Create or select an event
        # -------------------------------------------------------------
        print("\n[Step 2/14] Select an event & inspect brief...")
        res_brief = self.client.get(f"/api/event/brief?event_id={self.event_id}")
        self.assertEqual(res_brief.status_code, 200)
        brief = res_brief.json()
        self.assertEqual(brief["id"], self.event_id)
        self.assertIn("DubHacks", brief["title"])
        self.assertEqual(brief["attendee_count"], 80)
        self.assertEqual(brief["budget"], 2500.0)

        res_overview = self.client.get(f"/api/overview?event_id={self.event_id}")
        self.assertEqual(res_overview.status_code, 200)
        overview = res_overview.json()
        self.assertEqual(overview["event"]["id"], self.event_id)
        print(f"  ✓ Step 2 Passed: Event brief loaded for '{brief['title']}' (${brief['budget']}, {brief['attendee_count']} pax).")

        # -------------------------------------------------------------
        # STEP 3: Ask the AI agent about the event
        # -------------------------------------------------------------
        print("\n[Step 3/14] Ask AI Agent about the event...")
        chat_payload = {
            "message": "What is the budget and attendee count for this event, and what are the catering constraints?",
            "history": [],
            "event_id": self.event_id,
        }
        res_chat = self.client.post("/api/chat", json=chat_payload)
        self.assertEqual(res_chat.status_code, 200)
        chat_data = res_chat.json()
        self.assertIn("text", chat_data)
        self.assertTrue(len(chat_data["text"]) > 20)
        self.assertIn("model_used", chat_data)
        print(f"  ✓ Step 3 Passed: AI agent responded via {chat_data['model_used']}.")

        # -------------------------------------------------------------
        # STEP 4: View event requirements and available vendor quotes
        # -------------------------------------------------------------
        print("\n[Step 4/14] View event requirements and vendor quotes...")
        res_reqs = self.client.get(f"/api/vendor-requirements?event_id={self.event_id}")
        self.assertEqual(res_reqs.status_code, 200)
        reqs = res_reqs.json()
        self.assertTrue(len(reqs) >= 1)
        catering_req = next((r for r in reqs if r["category"] == "Catering"), None)
        self.assertIsNotNone(catering_req)
        self.assertEqual(catering_req["headcount"], 80)

        res_vendors = self.client.get(f"/api/records/vendors?event_id={self.event_id}")
        self.assertEqual(res_vendors.status_code, 200)
        quotes = res_vendors.json()
        self.assertTrue(len(quotes) >= 1)
        print(f"  ✓ Step 4 Passed: Retrieved {len(reqs)} requirements and {len(quotes)} vendor quotes.")

        # -------------------------------------------------------------
        # STEP 5: Compare vendors and save a preferred selection
        # -------------------------------------------------------------
        print("\n[Step 5/14] Compare vendors and select preferred proposal...")
        res_compare = self.client.get(f"/api/vendors/compare?event_id={self.event_id}&category=Catering")
        self.assertEqual(res_compare.status_code, 200)
        comparison = res_compare.json()
        self.assertIn("comparison_matrix", comparison)
        matrix = comparison["comparison_matrix"]
        self.assertTrue(len(matrix) >= 1)
        
        target_vendor = matrix[0]
        vendor_id = target_vendor["vendor_id"]
        vendor_name = target_vendor["company_name"]

        res_select = self.client.post(
            f"/api/vendors/{vendor_id}/select?event_id={self.event_id}",
            json={"actor_id": "organizer", "selection_notes": "Selected as best dietary match for DubHacks 2026."}
        )
        self.assertEqual(res_select.status_code, 200)
        sel_data = res_select.json()
        self.assertEqual(sel_data["vendor_id"], vendor_id)
        self.assertEqual(sel_data["status"], "selected")
        self.assertTrue(sel_data["is_preferred"])
        self.assertFalse(sel_data["is_booked"])
        self.assertIn("does not book", sel_data["booking_disclaimer"].lower())
        print(f"  ✓ Step 5 Passed: Selected '{vendor_name}' ({vendor_id}) as preferred proposal (non-binding).")

        # -------------------------------------------------------------
        # STEP 6: Detect a schedule conflict
        # -------------------------------------------------------------
        print("\n[Step 6/14] Detect schedule conflict...")
        # Add a conflicting session to trigger a verifiable conflict
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO schedules 
                (id, event_id, activity, time_slot, location, owner, activity_type, notes)
                VALUES ('ses-conflict-test', ?, 'Surprise Sponsor Workshop', '10:00 - 11:30', 'Room 214', 'Tech Sponsor', 'workshop', 'Conflicting room reservation')
                """,
                (self.event_id,)
            )
            # Ensure another session overlaps in Room 214
            conn.execute(
                """
                INSERT OR REPLACE INTO schedules 
                (id, event_id, activity, time_slot, location, owner, activity_type, notes)
                VALUES ('ses-parallel-test', ?, 'Hands-on Agentic Coding Track', '10:30 - 12:00', 'Room 214', 'Alex Rivera', 'workshop', 'Parallel workshop')
                """,
                (self.event_id,)
            )

        res_conflicts = self.client.get(f"/api/logistics/conflicts?event_id={self.event_id}")
        self.assertEqual(res_conflicts.status_code, 200)
        conflicts_data = res_conflicts.json()
        self.assertTrue(conflicts_data["total_conflicts"] > 0)
        print(f"  ✓ Step 6 Passed: Detected {conflicts_data['total_conflicts']} schedule conflict(s).")

        # -------------------------------------------------------------
        # STEP 7: Review and apply a proposed resolution
        # -------------------------------------------------------------
        print("\n[Step 7/14] Review and apply conflict resolution proposal...")
        res_proposals = self.client.get(f"/api/logistics/conflicts/proposals?event_id={self.event_id}")
        self.assertEqual(res_proposals.status_code, 200)
        prop_data = res_proposals.json()
        resolutions = prop_data.get("resolutions", []) or prop_data.get("proposals", [])
        self.assertTrue(len(resolutions) > 0)

        proposal = resolutions[0]
        session_id = proposal["target_session_id"]
        proposed_changes = proposal["proposed_changes"]
        expected_fp = proposal["expected_fingerprint"]
        conflict_id = proposal.get("conflict_id")

        apply_payload = {
            "event_id": self.event_id,
            "session_id": session_id,
            "proposed_changes": proposed_changes,
            "expected_fingerprint": expected_fp,
            "conflict_id": conflict_id
        }
        res_apply = self.client.post("/api/logistics/conflicts/apply", json=apply_payload)
        self.assertEqual(res_apply.status_code, 200)
        applied_result = res_apply.json()
        self.assertEqual(applied_result["status"], "applied")
        self.assertEqual(applied_result["session_id"], session_id)
        self.assertTrue(applied_result["is_conflict_resolved"])
        print(f"  ✓ Step 7 Passed: Successfully applied resolution for session '{session_id}'. Conflict resolved: {applied_result['is_conflict_resolved']}.")

        # -------------------------------------------------------------
        # STEP 8: Generate an outreach draft
        # -------------------------------------------------------------
        print("\n[Step 8/14] Generate outreach draft...")
        draft_result = tool_compose_outreach_draft(
            target_type="speaker",
            target_id_or_name="Dr. Alicia Chen",
            recipient_email="alicia.chen@cs.washington.edu",
            custom_instructions="Keynote on Autonomous Agent Reliability",
            event_id=self.event_id
        )
        self.assertIn("action_id", draft_result)
        action_id = draft_result["action_id"]
        self.assertEqual(draft_result["status"], "pending_approval")
        print(f"  ✓ Step 8 Passed: Created draft proposal '{action_id}' (status: pending_approval).")

        # -------------------------------------------------------------
        # STEP 9: Review and edit the draft
        # -------------------------------------------------------------
        print("\n[Step 9/14] Review and edit outreach draft...")
        new_subject = "Invitation: Keynote Speaker at DubHacks 2026 (Updated by Organizer)"
        new_body = "Dear Dr. Chen,\n\nWe are excited to formally invite you as our opening keynote speaker for DubHacks 2026."
        res_patch = self.client.patch(
            f"/api/actions/{action_id}",
            json={"subject": new_subject, "message_body": new_body}
        )
        self.assertEqual(res_patch.status_code, 200)
        patched_action = res_patch.json()
        raw_payload = patched_action["payload"]
        payload = raw_payload if isinstance(raw_payload, dict) else json.loads(raw_payload)
        self.assertEqual(payload["subject"], new_subject)
        self.assertEqual(payload["message_body"], new_body)
        print(f"  ✓ Step 9 Passed: Successfully updated subject and body for '{action_id}'.")

        # -------------------------------------------------------------
        # STEP 10: Explicitly approve the draft
        # -------------------------------------------------------------
        print("\n[Step 10/14] Explicitly approve the draft (without dispatching)...")
        res_approve = self.client.post(
            f"/api/actions/{action_id}/approve",
            json={
                "actor_id": "organizer",
                "event_id": self.event_id,
                "dispatch_now": False,
                "force_simulation": True
            }
        )
        self.assertEqual(res_approve.status_code, 200)
        approved_data = res_approve.json()
        self.assertEqual(approved_data["status"], "approved")
        self.assertIsNone(approved_data.get("executed_at"))
        print(f"  ✓ Step 10 Passed: Action '{action_id}' marked as 'approved'. Dispatch decoupled.")

        # -------------------------------------------------------------
        # STEP 11: Simulate dispatch and verify delivery status
        # -------------------------------------------------------------
        print("\n[Step 11/14] Simulate dispatch of approved draft...")
        res_dispatch = self.client.post(
            f"/api/actions/{action_id}/dispatch",
            json={
                "actor_id": "organizer",
                "event_id": self.event_id,
                "force_simulation": True
            }
        )
        self.assertEqual(res_dispatch.status_code, 200)
        dispatched_data = res_dispatch.json()
        self.assertEqual(dispatched_data["status"], "executed")
        self.assertEqual(dispatched_data["delivery_status"], "simulated delivery")
        self.assertFalse(dispatched_data["is_real_sent"])
        self.assertTrue(dispatched_data.get("result", {}).get("is_simulated", True))
        self.assertIn("simulation", dispatched_data.get("result", {}).get("provider", "").lower())
        print(f"  ✓ Step 11 Passed: Dispatched safely. Delivery status: '{dispatched_data['delivery_status']}'.")

        # -------------------------------------------------------------
        # STEP 12: Generate a PDF contract draft
        # -------------------------------------------------------------
        print("\n[Step 12/14] Generate PDF contract draft...")
        res_fill = self.client.post(f"/api/pdf/fill?event_id={self.event_id}")
        self.assertEqual(res_fill.status_code, 200)
        pdf_data = res_fill.json()
        self.assertIn("output_file", pdf_data)
        self.assertIn("download_url", pdf_data)
        output_filename = pdf_data["output_file"]
        mapped_count = pdf_data["field_counts"]["mapped"]
        unresolved_count = pdf_data["field_counts"]["unresolved"]
        self.assertTrue(mapped_count >= 8)
        self.assertTrue(unresolved_count >= 6)
        self.assertIn("DRAFT ONLY", pdf_data["hitl_safety"])
        print(f"  ✓ Step 12 Passed: Generated draft '{output_filename}' ({mapped_count} mapped, {unresolved_count} unresolved).")

        # -------------------------------------------------------------
        # STEP 13: Download the document
        # -------------------------------------------------------------
        print("\n[Step 13/14] Download generated PDF document...")
        res_download = self.client.get(f"/api/pdf/download/{output_filename}")
        self.assertEqual(res_download.status_code, 200)
        self.assertEqual(res_download.headers.get("content-type"), "application/pdf")
        self.assertTrue(res_download.content.startswith(b"%PDF-"))
        print(f"  ✓ Step 13 Passed: Downloaded {len(res_download.content)} bytes of valid PDF.")

        # -------------------------------------------------------------
        # STEP 14: Refresh the application and verify saved data persists
        # -------------------------------------------------------------
        print("\n[Step 14/14] Verify complete data persistence across simulated refresh...")
        # 14.1 Verify brief
        reloaded_brief = get_event_brief(self.event_id)
        self.assertIsNotNone(reloaded_brief)
        self.assertEqual(reloaded_brief["id"], self.event_id)

        # 14.2 Verify preferred vendor
        pref_v = get_vendor_by_id(vendor_id, event_id=self.event_id)
        self.assertIsNotNone(pref_v)
        self.assertEqual(pref_v["status"], "selected")

        # 14.3 Verify outreach action status
        actions = list_action_proposals(self.event_id)
        saved_action = next((a for a in actions if a["id"] == action_id), None)
        self.assertIsNotNone(saved_action)
        self.assertEqual(saved_action["status"], "executed")
        self.assertEqual(saved_action["delivery_status"], "simulated delivery")

        # 14.4 Verify PDF documents recorded
        docs = get_pdf_documents(self.event_id)
        self.assertTrue(any(output_filename in d["file_path"] for d in docs))

        # 14.5 Verify activity logs
        activities = self.client.get(f"/api/activity?event_id={self.event_id}").json()
        self.assertTrue(len(activities) > 0)
        print(f"  ✓ Step 14 Passed: All entities, audit logs ({len(activities)} events), and states persist in SQLite.")

        print("\n" + "=" * 70)
        print("ALL 14 STEPS OF THE ORGANIZER JOURNEY VERIFIED AND PASSED!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    unittest.main()
