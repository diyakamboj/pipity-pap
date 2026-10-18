"""Gurt End-to-End Verification Test Suite.

Verifies the smallest connected Gurt workflow:
1. Unified Event Records Database (SQLite)
2. Bounded Tool Adapters (Speakers, Vendors, Tasks, Outreach)
3. Action Proposal & Backend Approval Execution (HITL Safety)
4. Orchestrator turn handling and grounding
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add gurt root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gurt.db import init_db, query_records, get_event_summary
from gurt.tools.event_tools import (
    tool_get_event_overview,
    tool_lookup_speakers,
    tool_lookup_vendors,
    tool_lookup_tasks,
    tool_create_task,
    tool_propose_speaker,
)
from gurt.tools.research_tool import tool_web_research
from gurt.tools.outreach_tools import tool_draft_outreach, execute_approved_action
from gurt.orchestrator import run_orchestrator


def run_tests():
    print("=" * 60)
    print("RUNNING GURT COMPONENT & WORKFLOW TESTS")
    print("=" * 60)

    # 1. DB Init
    print("\n[1/6] Initializing Event Database...")
    init_db()
    summary = get_event_summary()
    assert summary["event"]["id"] == "evt-dubhacks-2026", "Event record mismatch"
    print(f" -> Event initialized: '{summary['event']['title']}'")
    print(f" -> Speakers count: {summary['speakers']}, Vendors count: {summary['vendors']}")

    # 2. Speaker & Vendor Lookups
    print("\n[2/6] Testing Speaker & Vendor Lookup Adapters...")
    speakers = tool_lookup_speakers("Chen")
    assert len(speakers) >= 1, "Speaker lookup failed"
    print(f" -> Found speaker: {speakers[0]['name']} ({speakers[0]['org']})")

    vendors = tool_lookup_vendors("Catering")
    assert len(vendors) >= 1, "Vendor lookup failed"
    print(f" -> Found vendor: {vendors[0]['company_name']} - ${vendors[0]['quote_amount']}")

    # 3. Web Research & Synthetic Fixture
    print("\n[3/6] Testing Web Research Tool Adapter...")
    res = tool_web_research("Dr. Alicia Chen keynote speaker")
    assert "results" in res and len(res["results"]) > 0, "Research results empty"
    print(f" -> Research query: '{res['query']}', is_synthetic: {res.get('is_synthetic')}")

    # 4. Draft Outreach (HITL - Proposal only, never sent)
    print("\n[4/6] Testing Outreach Draft & HITL Safety Boundary...")
    draft = tool_draft_outreach(
        recipient_name="Dr. Alicia Chen",
        recipient_email="alicia.chen@cs.washington.edu",
        subject="DubHacks Keynote Invitation",
        message_body="We would love to invite you to speak at DubHacks 2026."
    )
    assert draft["status"] == "pending_approval", "Draft must be pending_approval"
    action_id = draft["action_id"]
    print(f" -> Draft created with ID: {action_id} (Status: {draft['status']})")
    print(f" -> Safety warning: {draft['warning']}")

    # 5. Backend Approval & Execution
    print("\n[5/6] Testing Consequential Action Approval Execution...")
    exec_res = execute_approved_action(action_id)
    assert exec_res["status"] == "executed", "Action must be executed upon approval"
    print(f" -> Action {action_id} executed at: {exec_res['executed_at']}")
    print(f" -> Dispatch result: {exec_res['result']}")

    # 6. Logistics Task Creation
    print("\n[6/6] Testing Logistics Task Creation & DAG Tracking...")
    task = tool_create_task(
        title="Confirm AV Projector and Microphones with HUB Venue",
        owner="Logistics Lead",
        category="Logistics",
        deadline="2026-11-05",
        dependencies="None"
    )
    assert task["status"] == "created", "Task creation failed"
    print(f" -> Created Task: '{task['title']}' [ID: {task['task_id']}]")

    # 7. Orchestrator Connected Loop
    print("\n[7/7] Testing Orchestrator Response Flow...")
    orch_res = run_orchestrator("Can you review the logistics checklist and current vendor quotes?")
    assert "text" in orch_res and len(orch_res["text"]) > 20, "Orchestrator failed to respond"
    print(f" -> Model/Engine used: {orch_res['model_used']}")
    print(f" -> Orchestrator Response:\n{orch_res['text'][:250]}...\n")

    print("=" * 60)
    print("ALL 7 GURT WORKFLOW CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
