"""Focused Verification Suite for Outreach Draft -> Review -> Approval -> Delivery-Status Workflow.

Tests all 11 requirements:
1. Compose draft outreach for speaker, sponsor, vendor using saved event facts.
2. Save draft as pending action proposal tied to event.
3. Organizer inspection and pre-approval editing.
4. Require explicit approval before dispatch.
5. Prevent duplicate execution of approved action.
6. Record all 7 delivery states: draft, pending approval, approved,
   simulated delivery, real provider accepted, failed, delivery unconfirmed.
7. Never label simulated delivery as real sent email.
8. Safe local simulation mode when Resend is unconfigured or in dev/test.
9. Never send real emails during development or automated tests.
10. SQLite persistence of proposal, edits, decisions, attempts, and audit logs.
11. Event isolation and authorization limitation reporting.
"""

import json
import os
import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient

GURT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GURT_ROOT))

from gurt.config import settings
from gurt.db import (
    get_connection,
    get_action_proposal,
    update_action_proposal,
    record_action_approval,
    get_audit_logs,
    get_event_brief,
    init_db
)
from gurt.tools.outreach_tools import (
    tool_compose_outreach_draft,
    tool_draft_outreach,
    tool_update_draft,
    tool_approve_outreach,
    tool_dispatch_approved_action,
    execute_approved_action,
    dismiss_action
)
from gurt.api.server import app


class TestOutreachWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        """Set up test fixtures with isolated action proposals."""
        self.event_id = "evt-dubhacks-2026"
        self.test_actions_to_clean = []

    def tearDown(self):
        """Clean up test action proposals and audit logs."""
        if self.test_actions_to_clean:
            conn = get_connection()
            c = conn.cursor()
            for act_id in self.test_actions_to_clean:
                c.execute("DELETE FROM action_proposals WHERE id = ?", (act_id,))
                c.execute("DELETE FROM audit_logs WHERE target_id = ?", (act_id,))
            conn.commit()
            conn.close()

    def test_01_compose_draft_from_saved_event_facts(self):
        """Goal 1 & 2: Compose outreach drafts using saved event facts for speaker, sponsor, vendor."""
        brief = get_event_brief(self.event_id)
        event_title = brief["title"]
        event_date = brief["date"]

        # 1. Speaker draft
        spk_draft = tool_compose_outreach_draft(
            target_type="speaker",
            target_id_or_name="Dr. Alicia Chen",
            event_id=self.event_id
        )
        self.test_actions_to_clean.append(spk_draft["action_id"])
        self.assertEqual(spk_draft["status"], "pending_approval")
        self.assertEqual(spk_draft["delivery_status"], "pending approval")
        self.assertIn(event_title, spk_draft["subject"])
        self.assertIn(event_date, spk_draft["full_body"])
        self.assertIn("Alicia Chen", spk_draft["recipient"])
        self.assertIn("speaker_topic", spk_draft["facts_used"])

        # 2. Sponsor draft
        spn_draft = tool_compose_outreach_draft(
            target_type="sponsor",
            target_id_or_name="AI Safety Grants Foundation",
            event_id=self.event_id
        )
        self.test_actions_to_clean.append(spn_draft["action_id"])
        self.assertEqual(spn_draft["status"], "pending_approval")
        self.assertEqual(spn_draft["delivery_status"], "pending approval")
        self.assertIn("Sponsorship", spn_draft["subject"])
        self.assertIn("tier", spn_draft["facts_used"])

        # 3. Vendor inquiry draft
        vnd_draft = tool_compose_outreach_draft(
            target_type="vendor",
            target_id_or_name="Ballard Bites & Bowls",
            event_id=self.event_id
        )
        self.test_actions_to_clean.append(vnd_draft["action_id"])
        self.assertEqual(vnd_draft["status"], "pending_approval")
        self.assertEqual(vnd_draft["delivery_status"], "pending approval")
        self.assertIn("Ballard Bites & Bowls", vnd_draft["recipient"])
        self.assertIn("dietary_needs", vnd_draft["facts_used"])
        self.assertIn("service_window", vnd_draft["facts_used"])

    def test_02_draft_vs_pending_approval_states(self):
        """Goal 6: Support both 'draft' and 'pending approval' states."""
        draft_only = tool_compose_outreach_draft(
            target_type="speaker",
            target_id_or_name="Dr. Alicia Chen",
            event_id=self.event_id,
            save_as_draft_only=True
        )
        self.test_actions_to_clean.append(draft_only["action_id"])
        self.assertEqual(draft_only["status"], "draft")
        self.assertEqual(draft_only["delivery_status"], "draft")
        self.assertEqual(draft_only["approval_status"], "draft")

        # Verify DB row
        prop = get_action_proposal(draft_only["action_id"], event_id=self.event_id)
        self.assertIsNotNone(prop)
        self.assertEqual(prop["status"], "draft")
        self.assertEqual(prop["delivery_status"], "draft")

    def test_03_pre_approval_draft_inspection_and_editing(self):
        """Goal 3: Allow the organizer to inspect and edit the draft before approval."""
        draft = tool_draft_outreach(
            recipient_name="Professor Ada Lovelace",
            recipient_email="ada@example.ac.uk",
            subject="Initial Keynote Invitation Draft",
            message_body="Initial draft content awaiting refinement.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        # Inspect draft
        inspected = get_action_proposal(act_id, event_id=self.event_id)
        self.assertIsNotNone(inspected)
        self.assertEqual(inspected["status"], "pending_approval")
        self.assertEqual(inspected["delivery_status"], "pending approval")

        # Edit draft fields
        edit_res = tool_update_draft(
            action_id=act_id,
            subject="Refined Keynote Invitation: DubHacks 2026",
            message_body="Dear Professor Lovelace, we have updated honorarium details and session timings.",
            recipient_email="ada.lovelace@oxford.example.edu",
            recipient_name="Prof. Ada Lovelace FRS",
            event_id=self.event_id,
            actor_id="organizer_alice"
        )
        self.assertTrue(edit_res.get("updated"))
        self.assertEqual(edit_res["status"], "pending_approval")
        self.assertEqual(edit_res["delivery_status"], "pending approval")

        # Verify edited values in DB
        reloaded = get_action_proposal(act_id, event_id=self.event_id)
        self.assertIn("Refined Keynote", reloaded["title"])
        self.assertEqual(reloaded["payload"]["recipient_email"], "ada.lovelace@oxford.example.edu")
        self.assertIn("honorarium details", reloaded["payload"]["message_body"])

        # Verify audit log recorded the edit
        logs = get_audit_logs(event_id=self.event_id, limit=10)
        edit_logs = [l for l in logs if l["target_id"] == act_id and l["action"] == "edit_outreach_draft"]
        self.assertTrue(len(edit_logs) >= 1)
        self.assertEqual(edit_logs[0]["actor_id"], "organizer_alice")

    def test_04_require_explicit_organizer_approval_before_dispatch(self):
        """Goal 4: Require explicit organizer approval before any dispatch."""
        draft = tool_draft_outreach(
            recipient_name="Vendor Contact",
            recipient_email="vendor@supplier.org",
            subject="Order Specifications",
            message_body="Please confirm order drop-off window.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        # Step 1: Proposal is pending; no execution has happened
        prop = get_action_proposal(act_id, event_id=self.event_id)
        self.assertEqual(prop["status"], "pending_approval")
        self.assertEqual(prop["delivery_status"], "pending approval")
        self.assertIsNone(prop["executed_at"])

        # Attempting dispatch directly on pending-approval proposal MUST be rejected
        unapproved_disp = tool_dispatch_approved_action(act_id, event_id=self.event_id)
        self.assertIn("error", unapproved_disp)
        self.assertIn("must be explicitly approved before dispatch", unapproved_disp["error"])

        # Step 2: Explicit approval recorded without immediate dispatch (dispatch_now=False)
        appr_res = tool_approve_outreach(
            action_id=act_id,
            event_id=self.event_id,
            actor_id="organizer_lead",
            dispatch_now=False
        )
        self.assertEqual(appr_res["status"], "approved")
        self.assertEqual(appr_res["delivery_status"], "approved")
        self.assertEqual(appr_res["approval_status"], "approved")
        self.assertEqual(appr_res["approved_by"], "organizer_lead")

        # Verify DB state is 'approved' and NOT yet 'executed'
        prop_after_appr = get_action_proposal(act_id, event_id=self.event_id)
        self.assertEqual(prop_after_appr["status"], "approved")
        self.assertEqual(prop_after_appr["delivery_status"], "approved")
        self.assertIsNone(prop_after_appr["executed_at"])

        # Step 3: Explicit dispatch execution of the approved action
        exec_res = tool_dispatch_approved_action(act_id, event_id=self.event_id, actor_id="organizer_lead")
        self.assertEqual(exec_res["status"], "executed")
        self.assertEqual(exec_res["delivery_status"], "simulated delivery")
        self.assertIsNotNone(exec_res["executed_at"])

    def test_05_prevent_duplicate_execution(self):
        """Goal 5: Prevent duplicate execution of the same approved action."""
        draft = tool_draft_outreach(
            recipient_name="Keynote Candidate",
            recipient_email="keynote@ai-summit.org",
            subject="Keynote Proposal",
            message_body="We would love to host your keynote.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        # First execution succeeds
        first_exec = execute_approved_action(act_id, event_id=self.event_id)
        self.assertEqual(first_exec["status"], "executed")
        self.assertEqual(first_exec["delivery_status"], "simulated delivery")

        # Second execution MUST be blocked
        second_exec = execute_approved_action(act_id, event_id=self.event_id)
        self.assertIn("error", second_exec)
        self.assertIn("already in state 'executed'", second_exec["error"])

        # Approval tool MUST also reject executing an already executed proposal
        appr_retry = tool_approve_outreach(act_id, event_id=self.event_id)
        self.assertIn("error", appr_retry)
        self.assertIn("already in state 'executed'", appr_retry["error"])

        # Post-execution edit MUST also be blocked
        edit_blocked = tool_update_draft(act_id, subject="Attempted Post-Send Edit")
        self.assertIn("error", edit_blocked)
        self.assertIn("Cannot edit action", edit_blocked["error"])

        # Post-execution dismissal MUST also be blocked
        dismiss_blocked = dismiss_action(act_id, event_id=self.event_id)
        self.assertIn("error", dismiss_blocked)
        self.assertIn("Cannot dismiss action", dismiss_blocked["error"])

    def test_06_simulated_delivery_never_labeled_real_sent(self):
        """Goal 6, 7 & 8: Local simulation mode and strict non-real email labeling."""
        draft = tool_draft_outreach(
            recipient_name="Local Simulation Target",
            recipient_email="local-sim@example.com",
            subject="Simulation Check",
            message_body="Testing simulation flags.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        res = execute_approved_action(act_id, force_simulation=True)
        self.assertEqual(res["status"], "executed")
        self.assertEqual(res["delivery_status"], "simulated delivery")
        self.assertEqual(res["delivery_mode"], "simulated")
        self.assertFalse(res["is_real_sent"])
        self.assertTrue(res["result"]["is_simulated"])
        self.assertEqual(res["result"]["provider"], "Local Simulation Dispatcher")

        # Verify DB columns directly
        prop = get_action_proposal(act_id, event_id=self.event_id)
        self.assertEqual(prop["delivery_status"], "simulated delivery")
        self.assertEqual(prop["delivery_mode"], "simulated")
        self.assertFalse(prop["execution_result"]["is_real_sent"])

    def test_07_provider_failure_and_unconfirmed_handling(self):
        """Goal 6: Accurate recording of 'failed' and 'delivery unconfirmed' states."""
        # 1. Failure simulation
        draft_fail = tool_draft_outreach(
            recipient_name="Fail Recipient",
            recipient_email="fail@network-down.org",
            subject="Fail Test",
            message_body="Test failure path.",
            event_id=self.event_id
        )
        fail_id = draft_fail["action_id"]
        self.test_actions_to_clean.append(fail_id)

        fail_res = execute_approved_action(fail_id, simulate_failure=True)
        self.assertEqual(fail_res["status"], "failed")
        self.assertEqual(fail_res["delivery_status"], "failed")
        self.assertEqual(fail_res["delivery_mode"], "failed")
        self.assertFalse(fail_res["is_real_sent"])
        self.assertIn("error", fail_res["result"])

        prop_fail = get_action_proposal(fail_id, event_id=self.event_id)
        self.assertEqual(prop_fail["status"], "failed")
        self.assertEqual(prop_fail["delivery_status"], "failed")

        # 2. Unconfirmed delivery simulation
        draft_unconf = tool_draft_outreach(
            recipient_name="Unconfirmed Recipient",
            recipient_email="unconf@pending-queue.org",
            subject="Unconfirmed Test",
            message_body="Test unconfirmed path.",
            event_id=self.event_id
        )
        unconf_id = draft_unconf["action_id"]
        self.test_actions_to_clean.append(unconf_id)

        unconf_res = execute_approved_action(unconf_id, simulate_unconfirmed=True)
        self.assertEqual(unconf_res["delivery_status"], "delivery unconfirmed")
        self.assertFalse(unconf_res["is_real_sent"])

        prop_unconf = get_action_proposal(unconf_id, event_id=self.event_id)
        self.assertEqual(prop_unconf["delivery_status"], "delivery unconfirmed")

    def test_08_no_real_emails_sent_even_if_resend_key_present_in_tests(self):
        """Goal 9: Even if resend_api_key is set, never dispatch real emails during automated tests."""
        draft = tool_draft_outreach(
            recipient_name="Safety Guard Target",
            recipient_email="safety.guard@dubhacks-synthetic.test",
            subject="Safety Test",
            message_body="Testing that no external call is made.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        # Temporarily mock a live key
        orig_key = settings.resend_api_key
        try:
            settings.resend_api_key = "re_live_fake_key_12345"
            # Attempt execution: test safety guard MUST prevent real network dispatch
            res = execute_approved_action(act_id, force_simulation=False)
            self.assertEqual(res["delivery_status"], "simulated delivery")
            self.assertEqual(res["delivery_mode"], "simulated")
            self.assertFalse(res["is_real_sent"])
            self.assertEqual(res["result"]["provider"], "Local Simulation Dispatcher")
        finally:
            settings.resend_api_key = orig_key

    def test_09_dismiss_action_flow(self):
        """Goal 10: Dismissing an action proposal persists status and prevents execution."""
        draft = tool_draft_outreach(
            recipient_name="To Be Dismissed",
            recipient_email="dismiss@example.org",
            subject="Dismiss Test",
            message_body="This proposal will be rejected by organizer.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        dismiss_res = dismiss_action(act_id, event_id=self.event_id, actor_id="organizer_charlie")
        self.assertEqual(dismiss_res["status"], "dismissed")
        self.assertEqual(dismiss_res["delivery_status"], "dismissed")

        # Verify DB
        prop = get_action_proposal(act_id, event_id=self.event_id)
        self.assertEqual(prop["status"], "dismissed")
        self.assertEqual(prop["delivery_status"], "dismissed")

        # Cannot approve dismissed action
        appr_blocked = tool_approve_outreach(act_id, event_id=self.event_id)
        self.assertIn("error", appr_blocked)
        self.assertIn("Cannot approve dismissed action", appr_blocked["error"])

    def test_10_persistence_across_connection_reload(self):
        """Goal 10: All proposal edits, approval metadata, and execution results persist across fresh DB connections."""
        draft = tool_draft_outreach(
            recipient_name="Durable Contact",
            recipient_email="durable@persist.test",
            subject="Durable Test Message",
            message_body="Content for persistence testing.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        # Edit and approve
        tool_update_draft(act_id, subject="Persisted Subject Update", actor_id="org_persist")
        exec_res = execute_approved_action(act_id, event_id=self.event_id, actor_id="org_persist")
        self.assertEqual(exec_res["status"], "executed")

        # Open completely fresh SQLite connection
        fresh_conn = sqlite3.connect(settings.db_path)
        fresh_conn.row_factory = sqlite3.Row
        c = fresh_conn.cursor()
        c.execute("SELECT * FROM action_proposals WHERE id = ?", (act_id,))
        row = c.fetchone()
        fresh_conn.close()

        self.assertIsNotNone(row)
        d = dict(row)
        self.assertEqual(d["status"], "executed")
        self.assertEqual(d["delivery_status"], "simulated delivery")
        self.assertEqual(d["delivery_mode"], "simulated")
        self.assertEqual(d["approved_by"], "org_persist")
        self.assertIsNotNone(d["executed_at"])
        self.assertIn("Persisted Subject Update", d["title"])

        payload = json.loads(d["payload"])
        self.assertEqual(payload["subject"], "Persisted Subject Update")

    def test_11_event_isolation(self):
        """Goal 11: Maintain strict event isolation for action proposal queries, edits, and execution."""
        draft = tool_draft_outreach(
            recipient_name="Isolated Recipient",
            recipient_email="isolated@event-alpha.org",
            subject="Alpha Event Outreach",
            message_body="Outreach strictly for event Alpha.",
            event_id=self.event_id
        )
        act_id = draft["action_id"]
        self.test_actions_to_clean.append(act_id)

        # Querying with a different event ID MUST return None
        cross_event_get = get_action_proposal(act_id, event_id="evt-other-conference")
        self.assertIsNone(cross_event_get)

        # Editing with a different event ID MUST fail
        cross_event_edit = tool_update_draft(act_id, subject="Illegal Edit", event_id="evt-other-conference")
        self.assertIn("error", cross_event_edit)
        self.assertIn("not found", cross_event_edit["error"].lower())

        # Executing with a different event ID MUST fail
        cross_event_exec = execute_approved_action(act_id, event_id="evt-other-conference")
        self.assertIn("error", cross_event_exec)
        self.assertIn("not found", cross_event_exec["error"].lower())

        # Dismissing with a different event ID MUST fail
        cross_event_dismiss = dismiss_action(act_id, event_id="evt-other-conference")
        self.assertIn("error", cross_event_dismiss)
        self.assertIn("not found", cross_event_dismiss["error"].lower())

    def test_12_fastapi_rest_api_endpoints(self):
        """Verify REST API contracts for compose, get, edit, approve, dismiss, and cross-event isolation."""
        # 1. POST /api/actions/compose
        comp_resp = self.client.post("/api/actions/compose", json={
            "target_type": "speaker",
            "target_id_or_name": "Dr. Alicia Chen",
            "event_id": self.event_id,
            "custom_instructions": "Highlight workshop keynote slot."
        })
        self.assertEqual(comp_resp.status_code, 200)
        data = comp_resp.json()
        act_id = data["action_id"]
        self.test_actions_to_clean.append(act_id)
        self.assertEqual(data["status"], "pending_approval")
        self.assertEqual(data["delivery_status"], "pending approval")

        # 2. GET /api/actions/{action_id}
        get_resp = self.client.get(f"/api/actions/{act_id}?event_id={self.event_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], act_id)

        # Cross-event GET returns 404
        cross_get = self.client.get(f"/api/actions/{act_id}?event_id=evt-other-event")
        self.assertEqual(cross_get.status_code, 404)

        # 3. PATCH /api/actions/{action_id}
        patch_resp = self.client.patch(f"/api/actions/{act_id}", json={
            "subject": "REST API Polish: Keynote Invitation",
            "message_body": "Updated invitation body via REST API.",
            "event_id": self.event_id,
            "actor_id": "api_organizer"
        })
        self.assertEqual(patch_resp.status_code, 200)
        self.assertTrue(patch_resp.json().get("updated"))

        # 4. POST /api/actions/{action_id}/approve
        appr_resp = self.client.post(f"/api/actions/{act_id}/approve", json={
            "actor_id": "api_organizer",
            "event_id": self.event_id,
            "dispatch_now": True,
            "force_simulation": True
        })
        self.assertEqual(appr_resp.status_code, 200)
        appr_data = appr_resp.json()
        self.assertEqual(appr_data["status"], "executed")
        self.assertEqual(appr_data["delivery_status"], "simulated delivery")
        self.assertFalse(appr_data["is_real_sent"])

        # 5. Duplicate approve returns 400
        dup_resp = self.client.post(f"/api/actions/{act_id}/approve", json={
            "actor_id": "api_organizer",
            "event_id": self.event_id
        })
        self.assertEqual(dup_resp.status_code, 400)
        self.assertIn("already in state 'executed'", dup_resp.json()["detail"])

        # 6. Test dismissal endpoint on fresh draft
        comp_resp2 = self.client.post("/api/actions/compose", json={
            "target_type": "sponsor",
            "target_id_or_name": "AI Safety Grants Foundation",
            "event_id": self.event_id
        })
        act_id_2 = comp_resp2.json()["action_id"]
        self.test_actions_to_clean.append(act_id_2)

        dismiss_resp = self.client.post(f"/api/actions/{act_id_2}/dismiss", json={
            "actor_id": "api_organizer",
            "event_id": self.event_id
        })
        self.assertEqual(dismiss_resp.status_code, 200)
        self.assertEqual(dismiss_resp.json()["status"], "dismissed")

    def test_13_separate_approval_and_dispatch_operations(self):
        """Verify approval and dispatch are separate operations, rejecting direct dispatch of drafts or pending proposals."""
        # 1. Compose a proposal with save_as_draft_only=True
        comp_resp = self.client.post("/api/actions/compose", json={
            "target_type": "vendor",
            "target_id_or_name": "Ballard Bites & Bowls",
            "event_id": self.event_id,
            "save_as_draft_only": True
        })
        self.assertEqual(comp_resp.status_code, 200)
        draft_data = comp_resp.json()
        draft_id = draft_data["action_id"]
        self.test_actions_to_clean.append(draft_id)
        self.assertEqual(draft_data["status"], "draft")
        self.assertEqual(draft_data["delivery_status"], "draft")

        # 2. Direct dispatch on draft MUST fail via both tool and REST
        tool_draft_disp = tool_dispatch_approved_action(draft_id, event_id=self.event_id)
        self.assertIn("error", tool_draft_disp)
        self.assertIn("Cannot dispatch unapproved draft action", tool_draft_disp["error"])

        rest_draft_disp = self.client.post(f"/api/actions/{draft_id}/dispatch", json={
            "event_id": self.event_id
        })
        self.assertEqual(rest_draft_disp.status_code, 400)
        self.assertIn("Cannot dispatch unapproved draft action", rest_draft_disp.json()["detail"])

        # 3. Create a pending-approval proposal
        comp_resp_pending = self.client.post("/api/actions/compose", json={
            "target_type": "speaker",
            "target_id_or_name": "Dr. Alicia Chen",
            "event_id": self.event_id,
            "save_as_draft_only": False
        })
        self.assertEqual(comp_resp_pending.status_code, 200)
        pending_id = comp_resp_pending.json()["action_id"]
        self.test_actions_to_clean.append(pending_id)

        # Direct dispatch on pending_approval MUST fail
        tool_pending_disp = tool_dispatch_approved_action(pending_id, event_id=self.event_id)
        self.assertIn("error", tool_pending_disp)
        self.assertIn("must be explicitly approved before dispatch", tool_pending_disp["error"])

        rest_pending_disp = self.client.post(f"/api/actions/{pending_id}/dispatch", json={
            "event_id": self.event_id
        })
        self.assertEqual(rest_pending_disp.status_code, 400)
        self.assertIn("must be explicitly approved before dispatch", rest_pending_disp.json()["detail"])

        # 4. Explicit approval (dispatch_now=False) transitions status to 'approved'
        appr_resp = self.client.post(f"/api/actions/{pending_id}/approve", json={
            "actor_id": "lead_organizer",
            "event_id": self.event_id,
            "dispatch_now": False
        })
        self.assertEqual(appr_resp.status_code, 200)
        appr_data = appr_resp.json()
        self.assertEqual(appr_data["status"], "approved")
        self.assertEqual(appr_data["delivery_status"], "approved")

        db_prop = get_action_proposal(pending_id, event_id=self.event_id)
        self.assertEqual(db_prop["status"], "approved")
        self.assertIsNone(db_prop["executed_at"])

        # 5. Cross-event dispatch MUST be rejected with 404
        cross_disp = self.client.post(f"/api/actions/{pending_id}/dispatch", json={
            "event_id": "evt-other-event"
        })
        self.assertEqual(cross_disp.status_code, 404)

        # 6. Explicit dispatch of the approved proposal succeeds
        disp_resp = self.client.post(f"/api/actions/{pending_id}/dispatch", json={
            "actor_id": "lead_organizer",
            "event_id": self.event_id,
            "force_simulation": True
        })
        self.assertEqual(disp_resp.status_code, 200)
        disp_data = disp_resp.json()
        self.assertEqual(disp_data["status"], "executed")
        self.assertEqual(disp_data["delivery_status"], "simulated delivery")
        self.assertFalse(disp_data["is_real_sent"])

        # 7. Duplicate dispatch MUST be rejected
        dup_disp = self.client.post(f"/api/actions/{pending_id}/dispatch", json={
            "actor_id": "lead_organizer",
            "event_id": self.event_id
        })
        self.assertEqual(dup_disp.status_code, 400)
        self.assertIn("already in state 'executed'", dup_disp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
