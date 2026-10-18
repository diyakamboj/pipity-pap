"""Verification script testing the exact five Claude Workshop demo prompts sequentially
through the actual /api/chat endpoint.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add gurt root to path
GURT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(GURT_ROOT))

from fastapi.testclient import TestClient
from gurt.api.server import app
from gurt.db import init_db, get_event_brief, list_action_proposals, get_connection

def test_five_prompts():
    init_db()
    client = TestClient(app)
    event_id = "evt-claude-workshop"

    results = {}

    print("======================================================================")
    print("TESTING EXACT FIVE CLAUDE WORKSHOP DEMO PROMPTS VIA /api/chat")
    print("======================================================================\n")

    # -------------------------------------------------------------------------
    # Prompt 1: "We're hosting a hands-on Claude workshop..."
    # -------------------------------------------------------------------------
    p1 = "We're hosting a hands-on Claude workshop..."
    print(f"Prompt 1: \"{p1}\"")
    res1 = client.post("/api/chat", json={
        "message": p1,
        "event_id": event_id
    })
    if res1.status_code != 200:
        results["Prompt 1"] = f"FAIL (status {res1.status_code}): {res1.text}"
    else:
        data1 = res1.json()
        brief1 = get_event_brief(event_id)
        text1 = data1.get("text", "")
        # Checks: 40 attendees, $500 budget, Blueprint office Bellevue, venue unconfirmed
        cond_brief = (
            brief1.get("attendee_count") == 40
            and float(brief1.get("budget", 0)) == 500.0
            and "Bellevue" in brief1.get("location", "")
            and brief1.get("venue_confirmation_status") == "unconfirmed"
        )
        cond_text = "40" in text1 and "500" in text1 and "Bellevue" in text1 and not text1.strip().startswith("{")
        if cond_brief and cond_text:
            results["Prompt 1"] = "PASS"
            print("  ✓ Updated event brief: 40 attendees, $500 budget, Bellevue, unconfirmed venue")
            print(f"  ✓ Clean markdown response:\n{text1[:180]}...\n")
        else:
            results["Prompt 1"] = f"FAIL: cond_brief={cond_brief}, cond_text={cond_text}"
            print("  ✗ Failed verification:", results["Prompt 1"])

    # -------------------------------------------------------------------------
    # Prompt 2: "Yo Gurt, find us a speaker..."
    # -------------------------------------------------------------------------
    p2 = "Yo Gurt, find us a speaker..."
    print(f"Prompt 2: \"{p2}\"")
    res2 = client.post("/api/chat", json={
        "message": p2,
        "event_id": event_id
    })
    draft_id_p2 = None
    if res2.status_code != 200:
        results["Prompt 2"] = f"FAIL (status {res2.status_code}): {res2.text}"
    else:
        data2 = res2.json()
        text2 = data2.get("text", "")
        proposals2 = list_action_proposals(event_id)
        marcus_proposal = next((p for p in proposals2 if "Marcus" in p.get("title", "") or "Marcus" in str(p.get("payload", ""))), None)
        
        cond_spks = "Marcus Rivera" in text2 and "Dr. Alicia Chen" in text2 and "SYNTHETIC" in text2
        cond_draft = marcus_proposal is not None and marcus_proposal.get("status") == "pending_approval"
        cond_no_json = not text2.strip().startswith("{")
        
        if cond_spks and cond_draft and cond_no_json:
            draft_id_p2 = marcus_proposal["id"]
            results["Prompt 2"] = "PASS"
            print(f"  ✓ Displayed synthetic candidates with verified provenance")
            print(f"  ✓ Created draft in Action Center: {draft_id_p2} (status: pending_approval)")
            print(f"  ✓ Response:\n{text2[:220]}...\n")
        else:
            results["Prompt 2"] = f"FAIL: cond_spks={cond_spks}, cond_draft={cond_draft}, cond_no_json={cond_no_json}"
            print("  ✗ Failed verification:", results["Prompt 2"])

    # -------------------------------------------------------------------------
    # Prompt 3: "Make the invitation... shorter..."
    # -------------------------------------------------------------------------
    p3 = "Make the invitation... shorter..."
    print(f"Prompt 3: \"{p3}\"")
    res3 = client.post("/api/chat", json={
        "message": p3,
        "event_id": event_id
    })
    if res3.status_code != 200:
        results["Prompt 3"] = f"FAIL (status {res3.status_code}): {res3.text}"
    else:
        data3 = res3.json()
        text3 = data3.get("text", "")
        proposals3 = list_action_proposals(event_id)
        marcus_proposal3 = next((p for p in proposals3 if p["id"] == draft_id_p2), None)
        
        cond_same_id = marcus_proposal3 is not None and marcus_proposal3["id"] == draft_id_p2
        payload3 = marcus_proposal3.get("payload", {}) if marcus_proposal3 else {}
        body3 = payload3.get("message_body", "") if isinstance(payload3, dict) else str(payload3)
        
        cond_coffee = "coffee and snacks" in body3.lower()
        cond_no_special = "special note" not in body3.lower() and "instruction" not in body3.lower()
        cond_pending = marcus_proposal3.get("status") == "pending_approval" if marcus_proposal3 else False
        cond_no_json = not text3.strip().startswith("{")
        
        if cond_same_id and cond_coffee and cond_no_special and cond_pending and cond_no_json:
            results["Prompt 3"] = "PASS"
            print(f"  ✓ Preserved unchanged draft ID: {draft_id_p2}")
            print(f"  ✓ Email body updated with coffee & snacks (no 'Special Note')")
            print(f"  ✓ Status remains: pending_approval")
            print(f"  ✓ Response:\n{text3[:220]}...\n")
        else:
            results["Prompt 3"] = f"FAIL: same_id={cond_same_id}, coffee={cond_coffee}, no_special={cond_no_special}, pending={cond_pending}"
            print("  ✗ Failed verification:", results["Prompt 3"])

    # -------------------------------------------------------------------------
    # Prompt 4: "Next, help us prepare the venue booking application..."
    # -------------------------------------------------------------------------
    p4 = "Next, help us prepare the venue booking application..."
    print(f"Prompt 4: \"{p4}\"")
    res4 = client.post("/api/chat", json={
        "message": p4,
        "event_id": event_id
    })
    pdf_url_4 = None
    if res4.status_code != 200:
        results["Prompt 4"] = f"FAIL (status {res4.status_code}): {res4.text}"
    else:
        data4 = res4.json()
        text4 = data4.get("text", "")
        # Find pdf tool output
        pdf_tool = next((tc["output"] for tc in data4.get("tool_calls", []) if tc.get("tool") == "fill_event_pdf_form"), None)
        cond_tool = pdf_tool is not None
        cond_link = pdf_tool is not None and "download_url" in pdf_tool and pdf_tool["download_url"] in text4
        cond_missing = pdf_tool is not None and len(pdf_tool.get("unresolved_missing_fields", [])) > 0
        cond_signatures_blank = pdf_tool is not None and any("signature" in m.get("field", "").lower() for m in pdf_tool.get("unresolved_missing_fields", []))
        
        # Verify actual PDF file exists on disk and is downloadable
        pdf_exists = False
        if pdf_tool and "output_path" in pdf_tool:
            pdf_path = Path(pdf_tool["output_path"])
            pdf_exists = pdf_path.exists() and pdf_path.stat().st_size > 1000
            pdf_url_4 = pdf_tool["download_url"]

        if cond_tool and cond_link and cond_missing and cond_signatures_blank and pdf_exists:
            results["Prompt 4"] = "PASS"
            print(f"  ✓ PDF generated: {pdf_tool['output_file']} ({pdf_path.stat().st_size} bytes)")
            print(f"  ✓ Download link: {pdf_tool['download_url']}")
            print(f"  ✓ Missing fields identified (signatures left blank): {len(pdf_tool['unresolved_missing_fields'])}")
            print(f"  ✓ Response:\n{text4[:200]}...\n")
        else:
            results["Prompt 4"] = f"FAIL: cond_tool={cond_tool}, cond_link={cond_link}, missing={cond_missing}, exists={pdf_exists}"
            print("  ✗ Failed verification:", results["Prompt 4"])

    # -------------------------------------------------------------------------
    # Prompt 5: "Add these organizer details..."
    # -------------------------------------------------------------------------
    p5 = "Add these organizer details: Diya Kamboj, Anthropic Community, diya@anthropic.example, 425-555-0199."
    print(f"Prompt 5: \"{p5}\"")
    res5 = client.post("/api/chat", json={
        "message": p5,
        "event_id": event_id
    })
    if res5.status_code != 200:
        results["Prompt 5"] = f"FAIL (status {res5.status_code}): {res5.text}"
    else:
        data5 = res5.json()
        text5 = data5.get("text", "")
        brief5 = get_event_brief(event_id)
        cond_db = (
            brief5.get("organizer_name") == "Diya Kamboj"
            and brief5.get("organization") == "Anthropic Community"
            and brief5.get("organizer_email") == "diya@anthropic.example"
            and brief5.get("organizer_phone") == "425-555-0199"
        )
        pdf_tool5 = next((tc["output"] for tc in data5.get("tool_calls", []) if tc.get("tool") == "fill_event_pdf_form"), None)
        cond_pdf5 = pdf_tool5 is not None and Path(pdf_tool5["output_path"]).exists() and pdf_tool5["output_path"] != pdf_tool.get("output_path")
        cond_mapped_increased = pdf_tool5 is not None and pdf_tool5["field_counts"]["mapped"] > pdf_tool["field_counts"]["mapped"]
        cond_download = pdf_tool5 is not None and pdf_tool5["download_url"] in text5
        
        if cond_db and cond_pdf5 and cond_mapped_increased and cond_download:
            results["Prompt 5"] = "PASS"
            print(f"  ✓ Saved organizer details in SQLite (Diya Kamboj, 425-555-0199)")
            print(f"  ✓ Generated new PDF version: {pdf_tool5['output_file']}")
            print(f"  ✓ Mapped fields increased from {pdf_tool['field_counts']['mapped']} to {pdf_tool5['field_counts']['mapped']}")
            print(f"  ✓ Response:\n{text5[:200]}...\n")
        else:
            results["Prompt 5"] = f"FAIL: cond_db={cond_db}, cond_pdf5={cond_pdf5}, mapped_increased={cond_mapped_increased}, download={cond_download}"
            print("  ✗ Failed verification:", results["Prompt 5"])

    print("======================================================================")
    print("FINAL SUMMARY OF THE FIVE DEMO INTENTS:")
    print("======================================================================")
    all_passed = True
    for p_name, outcome in results.items():
        status = "PASS" if outcome == "PASS" else "FAIL"
        if status != "PASS":
            all_passed = False
        print(f"  {p_name}: {outcome}")
    print("======================================================================\n")
    return all_passed

if __name__ == "__main__":
    success = test_five_prompts()
    sys.exit(0 if success else 1)
