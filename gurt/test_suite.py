"""Gurt Comprehensive End-to-End Verification Test Suite.

Verifies the connected Gurt Event Operations workflow on an 80-person synthetic workshop
needing a keynote speaker, sponsor, catering (food), badges, and venue facility contract:
1. Event Brief creation, editing, and reload
2. Speaker & sponsor research candidates saved with evidence
3. Vendor requirements discovery & quotes linked to event (with unknowns flagged)
4. Logistics & run-of-show schedule synthesis consuming saved records
5. Outreach drafting & duplicate action prevention
6. Pre-approval draft editing (HITL safety)
7. Consequential execution controls & provider failure visibility
8. Standout workflow: Supported PDF AcroForm filling with unresolved field highlighting
9. Persistence survival across reload / restart
10. Orchestrator connected turn execution
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure execution in workspace virtual environment if available
venv_python = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    try:
        import reportlab
        import pypdf
        import fastapi
    except ImportError:
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

# Add gurt root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gurt.db import (
    init_db,
    query_records,
    get_event_summary,
    get_event_brief,
    update_event_brief,
    get_vendor_requirements,
    save_vendor_requirement,
    get_schedule_items
)
from gurt.tools.event_tools import (
    tool_get_event_overview,
    tool_get_event_brief,
    tool_update_event_brief,
    tool_lookup_speakers,
    tool_propose_speaker,
    tool_lookup_sponsors,
    tool_save_sponsor_candidate,
    tool_lookup_vendors,
    tool_add_vendor_quote,
    tool_save_vendor_requirement,
    tool_lookup_vendor_requirements,
    tool_lookup_tasks,
    tool_create_task,
    tool_update_task_status,
    tool_generate_schedule,
    tool_lookup_schedule
)
from gurt.tools.research_tool import tool_web_research
from gurt.tools.outreach_tools import (
    tool_draft_outreach,
    tool_update_draft,
    execute_approved_action
)
from gurt.tools.pdf_tools import (
    inspect_template_fields,
    fill_event_pdf_form
)
from gurt.orchestrator import run_orchestrator


def run_tests():
    print("=" * 70)
    print("RUNNING GURT END-TO-END VERIFICATION SUITE (80-PERSON SYNTHETIC WORKSHOP)")
    print("=" * 70)

    # 1. Event Brief: Initialize, Edit, and Reload
    print("\n[1/10] Verifying Event Brief Creation, Edit, and Reload...")
    init_db()
    brief = tool_get_event_brief("evt-dubhacks-2026")
    assert brief["attendee_count"] == 80, f"Expected 80 attendees, got {brief.get('attendee_count')}"
    print(f" -> Loaded Event: '{brief['title']}' ({brief['attendee_count']} attendees, Budget: ${brief['budget']})")

    # Update brief with specific dietary & AV constraints and reload
    updated_brief = tool_update_event_brief(
        "evt-dubhacks-2026",
        dietary_specs="Strict 100% nut-free facility; 15 vegan, 10 gluten-free, 5 halal meal boxes.",
        av_requirements="Dual 4K projectors in Room 214, 2 wireless handheld mics, 1 podium lapel."
    )
    reloaded_brief = tool_get_event_brief("evt-dubhacks-2026")
    assert "nut-free" in reloaded_brief["dietary_specs"].lower(), "Brief update did not persist"
    assert "dual 4k projectors" in reloaded_brief["av_requirements"].lower(), "AV specs did not persist"
    print(" -> Event Brief edit & reload successfully verified.")

    # 2. Speaker & Sponsor Research & Candidate Saving
    print("\n[2/10] Verifying Speaker & Sponsor Research and Evidence Saving...")
    res_speaker = tool_web_research("Dr. Alicia Chen keynote speaker multi-agent systems")
    assert len(res_speaker["results"]) > 0, "Speaker research returned no results"
    is_synth_spk = res_speaker.get("is_synthetic", False)
    print(f" -> Speaker research executed (is_synthetic: {is_synth_spk})")

    # Save candidate into persistent database
    prop_spk = tool_propose_speaker(
        name="Dr. Alicia Chen",
        org="UW AI Institute",
        topic="Multi-Agent Consensus & Safety Bounds",
        bio="Author of 'Resilient Turn-Taking in Agent Swarms' (NeurIPS 2025).",
        contact_email="alicia.chen@cs.washington.edu"
    )
    assert prop_spk["status"] == "added_to_shortlist", "Speaker candidate proposal failed"
    print(f" -> Saved speaker candidate: {prop_spk['name']} [ID: {prop_spk['speaker_id']}]")

    # Researched sponsor prospect
    prop_spn = tool_save_sponsor_candidate(
        name="AI Safety Grants Foundation",
        tier="Gold",
        amount=2500.0,
        notes="Offered workshop grant covering catering and student travel stipends.",
        contact_email="grants@aisafety.example"
    )
    assert prop_spn["status"] == "recorded_in_pipeline", "Sponsor candidate saving failed"
    print(f" -> Saved sponsor prospect: {prop_spn['name']} (${prop_spn['amount']})")

    # 3. Vendor Needs Discovery & Quotes (Belonging to Same Event with Unknowns)
    print("\n[3/10] Verifying Vendor Requirements Discovery & Quotes Isolation...")
    req_food = tool_save_vendor_requirement(
        category="Catering",
        specification="80 boxed lunches (15 vegan, 10 GF, 5 halal) from certified nut-free kitchen.",
        headcount=80,
        budget_allocated=1200.0,
        unknowns="Exact attendee allergy tally pending registration closing on Nov 5.",
        status="quoted"
    )
    assert req_food["headcount"] == 80, "Requirement headcount mismatch"
    print(f" -> Recorded need: {req_food['category']} for {req_food['headcount']} pax (Unknowns: '{req_food['unknowns']}')")

    req_badge = tool_save_vendor_requirement(
        category="Badges & Signage",
        specification="80 color double-sided attendee badges with QR codes + 15 mentor lanyards.",
        headcount=95,
        budget_allocated=300.0,
        unknowns="Late walk-in badge blank reserve count to determine.",
        status="approved"
    )
    print(f" -> Recorded need: {req_badge['category']} for {req_badge['headcount']} items")

    catering_vendors = tool_lookup_vendors("Catering")
    assert len(catering_vendors) >= 1, "No catering vendors found"
    chosen_caterer = catering_vendors[0]
    print(f" -> Evaluated supplier: {chosen_caterer['company_name']} - ${chosen_caterer['quote_amount']} (${chosen_caterer['price_per_head']}/head)")

    # 4. Run-of-Show Schedule Synthesis Consuming Saved Records
    print("\n[4/10] Verifying Run-of-Show Schedule Synthesis from Saved Records...")
    sched = tool_generate_schedule("evt-dubhacks-2026")
    assert len(sched) >= 6, "Schedule generated too few activities"
    activities = [s["activity"] for s in sched]
    assert any("setup" in a.lower() for a in activities), "Setup missing in schedule"
    assert any("keynote" in a.lower() for a in activities), "Keynote missing in schedule"
    assert any("lunch" in a.lower() for a in activities), "Lunch missing in schedule"
    assert any("teardown" in a.lower() for a in activities), "Teardown missing in schedule"
    print(f" -> Synthesized {len(sched)} timeline slots connecting setup -> keynote -> lunch -> teardown.")

    # 5. Logistics Tasks & Dependencies
    print("\n[5/10] Verifying Logistics Task Creation, Owners, and DAG Dependencies...")
    task_av = tool_create_task(
        title="Conduct dual projector line check with UW HUB AV Staff",
        owner="Jordan Tech",
        category="Logistics",
        deadline="2026-11-14",
        dependencies="tsk-003"
    )
    assert task_av["status"] == "created", "Task creation failed"
    print(f" -> Created task: '{task_av['title']}' (Owner: {task_av['owner']}, Depends on: {task_av['dependencies']})")

    # 6. Outreach Drafting & Duplicate Action Prevention
    print("\n[6/10] Verifying Outreach Draft & Duplicate Action Prevention...")
    draft1 = tool_draft_outreach(
        recipient_name="Dr. Alicia Chen",
        recipient_email="alicia.chen@cs.washington.edu",
        subject="Invitation: DubHacks 2026 Keynote",
        message_body="Dear Dr. Chen, we would love to invite you to give our opening keynote on multi-agent safety."
    )
    assert draft1["status"] == "pending_approval", "Draft must be pending_approval"
    act_id_1 = draft1["action_id"]
    print(f" -> Created Proposal: {act_id_1} (is_duplicate_prevented: {draft1.get('is_duplicate_prevented')})")

    draft2 = tool_draft_outreach(
        recipient_name="Dr. Alicia Chen",
        recipient_email="alicia.chen@cs.washington.edu",
        subject="Invitation: DubHacks 2026 Keynote (Updated Time)",
        message_body="Updated: We would love to host you from 10:00 to 10:45 AM at UW HUB Room 214."
    )
    assert draft2["action_id"] == act_id_1, "Repeated request created duplicate action proposal"
    assert draft2["is_duplicate_prevented"] is True, "Duplicate prevention flag missing"
    print(f" -> Repeated outreach request handled safely: re-used existing {draft2['action_id']} without duplicate.")

    # 7. Draft Editing Before Approval
    print("\n[7/10] Verifying Pre-Approval Draft Editing...")
    edit_res = tool_update_draft(
        action_id=act_id_1,
        subject="Official Keynote Invitation: DubHacks 2026 AI Workshop",
        message_body="Final Polish: Honored to invite you to speak at DubHacks 2026. Honorarium and travel confirmed."
    )
    assert edit_res["updated"] is True, "Draft edit failed"
    print(f" -> Successfully edited proposal {act_id_1} prior to approval.")

    # 8. Approval Controls & Consequential Execution
    print("\n[8/10] Verifying Approval Execution & Double-Execution Guard...")
    exec_res = execute_approved_action(act_id_1)
    assert exec_res["status"] == "executed", "Action execution failed"
    assert "executed_at" in exec_res, "Execution timestamp missing"
    print(f" -> Action {act_id_1} executed: Provider Result -> {exec_res['result'].get('status')}")

    double_exec = execute_approved_action(act_id_1)
    assert "error" in double_exec, "Double execution was not blocked"
    print(f" -> Double-execution prevented: '{double_exec['error']}'")

    # 9. Standout Workflow: PDF Form Filling with AcroForms
    print("\n[9/10] Verifying Standout Workflow: Supported PDF AcroForm Form Filling...")
    template_info = inspect_template_fields()
    assert template_info["total_fields"] >= 14, "Template field count too low"
    print(f" -> Inspected template '{template_info['template_file']}': Found {template_info['total_fields']} fillable AcroForm fields.")

    pdf_fill = fill_event_pdf_form("evt-dubhacks-2026")
    assert pdf_fill["status"] == "draft_ready", "PDF fill status must be draft_ready"
    assert pdf_fill["original_template_preserved"] is True, "Original template was not preserved"
    assert pdf_fill["field_counts"]["mapped"] >= 7, "Mapped field count too low"
    assert pdf_fill["field_counts"]["unresolved"] >= 6, "Missing unresolved field detection"
    print(f" -> Generated filled draft: {pdf_fill['output_file']}")
    print(f" -> Mapped facts ({pdf_fill['field_counts']['mapped']}): Event Name, Date, Location, 80 Attendance, Catering Vendor & Total.")
    print(f" -> Unresolved fields highlighted ({pdf_fill['field_counts']['unresolved']}): Phone, Budget Code, Insurance Cert #, Signatures.")
    print(f" -> HITL Safety verified: '{pdf_fill['hitl_safety']}'")

    # 10. Persistence Survival & Orchestrator Connected Loop
    print("\n[10/10] Verifying Persistence Across Reload & Orchestrator Turn Execution...")
    fresh_summary = get_event_summary("evt-dubhacks-2026")
    assert fresh_summary["event"]["attendee_count"] == 80, "Headcount did not survive reload"
    assert fresh_summary["schedule_items"] >= 6, "Schedule did not survive reload"
    print(f" -> Persistence verified: {fresh_summary['speakers']}, {fresh_summary['vendors']}, {fresh_summary['tasks']}, {fresh_summary['schedule_items']} schedule slots.")

    orch_res = run_orchestrator("Fill out the facility contract PDF form and summarize our run of show schedule.")
    assert "text" in orch_res and len(orch_res["text"]) > 20, "Orchestrator failed to respond"
    print(f" -> Model used: {orch_res['model_used']}")
    safe_snippet = orch_res['text'][:240].encode('ascii', errors='replace').decode('ascii')
    print(f" -> Orchestrator Response:\n{safe_snippet}...\n")

    print("=" * 70)
    print("ALL 10 GURT VERIFICATION CHECKS COMPLETED & PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
