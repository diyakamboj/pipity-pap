"""Seven-Step Claude Workshop Demo Regression Test Suite.

Verifies the 7-step Gurt organizer journey for the Claude Workshop:
1. Create/update the event with a $500 budget and 40 attendees.
2. Find verifiable speakers or clearly labeled pre-researched candidates.
3. Generate and save an editable outreach draft (without calling get_event_brief).
4. Edit, approve, and simulate dispatch with approval gates preserved.
5. Inspect and fill the venue PDF application (without invoking unrelated tools).
6. Save additional organizer details and regenerate the PDF (mapped fields increase).
7. Display a final review summary and downloadable unsigned draft (clean markdown, no raw JSON).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Add gurt root to path
GURT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GURT_ROOT))

from fastapi.testclient import TestClient
from gurt.api.server import app
from gurt.db import (
    init_db,
    get_connection,
    get_event_brief,
    update_event_brief,
    list_action_proposals,
    query_records
)
from gurt.orchestrator import run_orchestrator, dynamic_semantic_executor
from gurt.tools.event_tools import tool_compare_vendor_quotes, tool_lookup_speakers
from gurt.tools.outreach_tools import (
    tool_compose_outreach_draft,
    tool_update_draft,
    tool_approve_outreach,
    tool_dispatch_approved_action
)
from gurt.tools.pdf_tools import fill_event_pdf_form, inspect_template_fields


class TestClaudeWorkshopDemo(unittest.TestCase):
    """Automated verification suite for the 7-step Claude Workshop demo."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.event_id = "evt-claude-workshop"

    def setUp(self):
        # Reset Claude Workshop to clean initial state before each test
        update_event_brief(self.event_id, {
            "title": "Claude Workshop",
            "budget": 500.0,
            "attendee_count": 40,
            "location": "Blueprint office in Bellevue",
            "status": "planning",
            "organizer_name": "",
            "organizer_email": "",
            "organizer_phone": "",
            "organization": "",
            "venue_confirmation_status": "unconfirmed"
        })
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE vendor_requirements SET budget_allocated = 500.0, headcount = 40 WHERE event_id = ?", (self.event_id,))
        conn.commit()
        conn.close()

    def test_step_1_create_update_event_budget_and_scale(self):
        """Step 1: Event scale is $500 budget and 40 attendees at Blueprint office."""
        brief = get_event_brief(self.event_id)
        self.assertEqual(brief.get("id"), self.event_id)
        self.assertEqual(brief.get("title"), "Claude Workshop")
        self.assertEqual(float(brief.get("budget", 0)), 500.0)
        self.assertEqual(brief.get("attendee_count"), 40)
        self.assertIn("Bellevue", brief.get("location", ""))

        # Verify vendor comparison uses the $500 budget, NOT $2,500
        cmp_res = tool_compare_vendor_quotes("Catering", event_id=self.event_id)
        self.assertEqual(float(cmp_res.get("event_budget", 0)), 500.0)
        self.assertEqual(cmp_res.get("attendee_count"), 40)

        # Verify through REST endpoint
        res = self.client.get(f"/api/vendors/compare?category=Catering&event_id={self.event_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(float(data.get("event_budget", 0)), 500.0)

    def test_step_2_find_verifiable_speakers_with_provenance(self):
        """Step 2: Find verifiable speakers with clear provenance notes and no invented contacts."""
        # Query via orchestrator
        resp = dynamic_semantic_executor(
            "Find verifiable speakers or clearly labeled pre-researched candidates for the Claude Workshop",
            event_id=self.event_id
        )
        text = resp.get("text", "")
        self.assertIn("Marcus Rivera", text)
        self.assertIn("Dr. Alicia Chen", text)
        # Provenance must be explicitly surfaced
        self.assertTrue(
            "Research Provenance" in text or "Synthetic Research Fixture" in text or "Verified" in text,
            "Response must include explicit research provenance"
        )
        # Tools executed must be lookup_speakers and web_research
        tool_names = [t.get("tool") for t in resp.get("tool_calls", [])]
        self.assertIn("lookup_speakers", tool_names)
        self.assertIn("web_research", tool_names)

        # Verify candidates exist in database with verifiable contact emails
        speakers = tool_lookup_speakers(event_id=self.event_id)
        names = [s["name"] for s in speakers]
        self.assertIn("Marcus Rivera", names)
        self.assertIn("Dr. Alicia Chen", names)

    def test_step_3_speaker_outreach_drafting_tool_routing(self):
        """Step 3: Speaker drafting requests compose outreach and DO NOT call get_event_brief."""
        resp = dynamic_semantic_executor(
            "Draft an outreach invitation to Marcus Rivera",
            event_id=self.event_id
        )
        tool_names = [t.get("tool") for t in resp.get("tool_calls", [])]
        # Must call outreach drafting, NOT get_event_brief
        self.assertNotIn("get_event_brief", tool_names)
        self.assertTrue(
            any(t in ("compose_outreach_draft", "draft_outreach") for t in tool_names),
            f"Expected outreach drafting tool, got: {tool_names}"
        )

        text = resp.get("text", "")
        # Must produce clean markdown, not raw JSON
        self.assertFalse(text.strip().startswith("{"), "Response should be natural markdown, not raw JSON")
        self.assertIn("Action ID", text)
        self.assertIn("Human Approval Required", text)

        # Verify action proposal in SQLite has status pending_approval and modest budget warning
        proposals = list_action_proposals(self.event_id)
        self.assertTrue(len(proposals) > 0)
        latest = proposals[0]
        self.assertEqual(latest["status"], "pending_approval")
        self.assertIn("Marcus Rivera", latest["title"])

        payload = latest.get("payload", {})
        body = payload.get("message_body", "") if isinstance(payload, dict) else ""
        self.assertIn("$500", body)

    def test_step_4_edit_approve_and_simulate_dispatch(self):
        """Step 4: Edit draft, approve via human gate, and simulate dispatch without real external emails."""
        # 4a. Create draft
        draft = tool_compose_outreach_draft(
            target_type="speaker",
            target_id_or_name="Marcus Rivera",
            event_id=self.event_id
        )
        action_id = draft["action_id"]

        # 4b. Edit draft before approval
        edit_resp = dynamic_semantic_executor(
            f"Edit the outreach draft {action_id} to mention we will provide coffee and snacks",
            event_id=self.event_id
        )
        self.assertIn("Updated", edit_resp.get("text", ""))

        # Verify database record reflects edit and remains pending_approval
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
        row = dict(c.fetchone())
        conn.close()
        self.assertEqual(row["status"], "pending_approval")
        self.assertIn("coffee and snacks", row["payload"])

        # 4c. Approve draft
        appr_resp = dynamic_semantic_executor(
            f"Approve outreach {action_id}",
            event_id=self.event_id
        )
        self.assertIn("Approved", appr_resp.get("text", ""))

        # Verify status is now approved
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
        row = dict(c.fetchone())
        conn.close()
        self.assertEqual(row["status"], "approved")

        # 4d. Simulate dispatch
        disp_resp = dynamic_semantic_executor(
            f"Dispatch action {action_id}",
            event_id=self.event_id
        )
        disp_text = disp_resp.get("text", "")
        self.assertIn("Dispatched", disp_text)
        self.assertIn("Simulation Mode", disp_text)

        # Verify delivery status is simulated delivery
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
        row = dict(c.fetchone())
        conn.close()
        self.assertEqual(row["delivery_status"], "simulated delivery")

    def test_step_5_inspect_and_fill_venue_paperwork(self):
        """Step 5: Venue paperwork requests invoke PDF tools, not unrelated overview or vendor tools."""
        # Test inspect template fields
        insp_resp = dynamic_semantic_executor(
            "Inspect the venue paperwork template fields",
            event_id=self.event_id
        )
        tool_names = [t.get("tool") for t in insp_resp.get("tool_calls", [])]
        self.assertIn("inspect_template_fields", tool_names)
        self.assertNotIn("lookup_vendors", tool_names)

        # Test fill venue paperwork
        fill_resp = dynamic_semantic_executor(
            "Inspect and fill the venue PDF application",
            event_id=self.event_id
        )
        tool_names = [t.get("tool") for t in fill_resp.get("tool_calls", [])]
        self.assertIn("fill_event_pdf_form", tool_names)
        self.assertNotIn("lookup_vendors", tool_names)
        self.assertNotIn("get_event_overview", tool_names)

        text = fill_resp.get("text", "")
        self.assertIn("Contract PDF Draft Generated", text)
        self.assertIn("Unresolved Missing Fields", text)
        self.assertIn("DRAFT ONLY", text)

        # Verify PDF file created on disk
        pdf_res = next(t["output"] for t in fill_resp["tool_calls"] if t["tool"] == "fill_event_pdf_form")
        self.assertTrue(Path(pdf_res["output_path"]).exists())
        self.assertGreater(Path(pdf_res["output_path"]).stat().st_size, 1000)

    def test_step_6_save_organizer_details_and_regenerate_pdf(self):
        """Step 6: Saving organizer details updates SQLite and increases mapped fields in regenerated PDF."""
        # Initial PDF generation before organizer details
        pdf_before = fill_event_pdf_form(self.event_id)
        mapped_before = pdf_before["field_counts"]["mapped"]
        unresolved_before = pdf_before["field_counts"]["unresolved"]

        # Save organizer details via natural language command
        resp = dynamic_semantic_executor(
            "Save organizer details: Diya Kamboj, diya@anthropic.example, 425-555-0199, Anthropic Community and regenerate the PDF",
            event_id=self.event_id
        )
        text = resp.get("text", "")
        self.assertIn("Organizer Details Saved", text)
        self.assertIn("Diya Kamboj", text)

        # Verify organizer details persisted in SQLite
        brief = get_event_brief(self.event_id)
        self.assertEqual(brief.get("organizer_name"), "Diya Kamboj")
        self.assertEqual(brief.get("organizer_email"), "diya@anthropic.example")
        self.assertEqual(brief.get("organizer_phone"), "425-555-0199")
        self.assertEqual(brief.get("organization"), "Anthropic Community")

        # Verify regenerated PDF has MORE mapped fields and FEWER unresolved fields
        pdf_res = next(t["output"] for t in resp["tool_calls"] if t["tool"] == "fill_event_pdf_form")
        mapped_after = pdf_res["field_counts"]["mapped"]
        unresolved_after = pdf_res["field_counts"]["unresolved"]

        self.assertGreater(mapped_after, mapped_before, f"Expected mapped fields to increase from {mapped_before}, got {mapped_after}")
        self.assertLess(unresolved_after, unresolved_before, f"Expected unresolved fields to decrease from {unresolved_before}, got {unresolved_after}")

    def test_step_7_final_review_summary_and_downloadable_draft(self):
        """Step 7: Final operations review displays clean summary with downloadable unsigned draft link."""
        resp = dynamic_semantic_executor(
            "Show final review summary and downloadable draft for Claude Workshop",
            event_id=self.event_id
        )
        text = resp.get("text", "")

        # Must not be raw JSON
        self.assertFalse(text.strip().startswith("{"), "Response must be clean markdown, not raw JSON")
        self.assertIn("Final Operations Review", text)
        self.assertIn("$500.00", text)
        self.assertIn("40 attendees", text)
        self.assertIn("Downloadable Unsigned Draft", text)
        self.assertIn(".pdf", text)
        self.assertIn("HITL Safety Assurance", text)

        # Verify downloadable endpoint works via TestClient
        pdf_output = next(t["output"] for t in resp["tool_calls"] if t["tool"] == "fill_event_pdf_form")
        download_url = pdf_output["download_url"]
        dl_res = self.client.get(download_url)
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers.get("content-type"), "application/pdf")
        self.assertGreater(len(dl_res.content), 1000)


if __name__ == "__main__":
    unittest.main()
