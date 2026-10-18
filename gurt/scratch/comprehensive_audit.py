"""Comprehensive Feature Audit & Verification Test Suite for Gurt.

Audits the 3 core pillars:
1. Multi-Event Management & DB Isolation
2. Vendor Intelligence, Quotes Comparison & Compliance
3. Outreach Pipeline, Multi-Channel Drafting, HITL & Follow-ups
"""

import sys
import requests
import json
import uuid

BASE = "http://127.0.0.1:8000"

passed = 0
failed = 0

def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")

print("=" * 70)
print("COMPREHENSIVE AUDIT: 3 CORE EVENT OPERATIONS PILLARS")
print("=" * 70)

# ============================================================================
# PILLAR 1: MULTI-EVENT MANAGEMENT & DATABASE ISOLATION
# ============================================================================
print("\n" + "=" * 50)
print("PILLAR 1: Multi-Event Management & DB Isolation")
print("=" * 50)

# 1.1 List all existing events
r = requests.get(f"{BASE}/api/events")
check("1.1 GET /api/events returns 200", r.status_code == 200)
events = r.json()
check("1.1 Events list has DubHacks", any(e["id"] == "evt-dubhacks-2026" for e in events))
dh_initial = next(e for e in events if e["id"] == "evt-dubhacks-2026")
check("1.1 DubHacks title is intact", dh_initial["title"] == "DubHacks 2026 Agentic AI Workshop")

# 1.2 Create a completely new isolated event via REST API
audit_slug = uuid.uuid4().hex[:6]
new_event_title = f"Agentic AI Summit {audit_slug}"
r = requests.post(f"{BASE}/api/events", json={
    "title": new_event_title,
    "attendee_count": 150,
    "budget": 7500.0,
    "location": "Seattle Convention Center Room 301",
    "date": "2026-12-10 09:00",
    "goals": "Full-day agent architectures summit with 150 builders.",
    "theme": "Autonomous Agent Tooling",
    "dietary_specs": "Nut-free, 30 vegan, 20 halal, 15 GF boxes required.",
    "av_requirements": "3 wireless handheld mics, podium lapel, 4K projector."
})
check("1.2 POST /api/events returns 200", r.status_code == 200)
new_evt = r.json()
evt_id = new_evt.get("id")
check("1.2 New event has distinct unique ID", evt_id and evt_id.startswith("evt-") and evt_id != "evt-dubhacks-2026")
check("1.2 New event stores correct headcount", new_evt.get("attendee_count") == 150)
check("1.2 New event stores correct budget", new_evt.get("budget") == 7500.0)

# 1.3 Verify new event brief isolation via GET /api/event/brief?event_id=...
r = requests.get(f"{BASE}/api/event/brief?event_id={evt_id}")
check("1.3 GET /api/event/brief for new event returns 200", r.status_code == 200)
brief = r.json()
check("1.3 Brief returns correct event title", brief.get("title") == new_event_title)
check("1.3 Brief returns correct location", brief.get("location") == "Seattle Convention Center Room 301")

# 1.4 Update new event brief specifically and verify DubHacks is NOT affected
r = requests.put(f"{BASE}/api/event/brief?event_id={evt_id}", json={
    "title": f"Updated Summit {audit_slug}",
    "attendee_count": 160,
    "budget": 8000.0
})
check("1.4 PUT /api/event/brief for new event returns 200", r.status_code == 200)
r_updated = requests.get(f"{BASE}/api/event/brief?event_id={evt_id}")
check("1.4 New event updated title", r_updated.json().get("title") == f"Updated Summit {audit_slug}")
check("1.4 New event updated budget", r_updated.json().get("budget") == 8000.0)

# Check DubHacks again: must be 100% untouched!
r_dh = requests.get(f"{BASE}/api/event/brief?event_id=evt-dubhacks-2026")
check("1.4 DubHacks event brief remained completely unchanged", r_dh.json().get("title") == "DubHacks 2026 Agentic AI Workshop" and r_dh.json().get("budget") == 2500.0)

# 1.5 Create event via Chat Semantic Engine
r_chat = requests.post(f"{BASE}/api/chat", json={
    "message": f"Create event: AI Builders Hackathon {audit_slug} with 75 attendees and $3000 budget in Bellevue",
    "event_id": "evt-dubhacks-2026",
    "model": "semantic-engine"
})
check("1.5 Chat create event returns 200", r_chat.status_code == 200)
chat_res = r_chat.json()
check("1.5 Chat response confirms event creation", "New Event Created" in chat_res.get("text", "") or "AI Builders" in chat_res.get("text", ""))
check("1.5 Chat response returns switched_event_id", bool(chat_res.get("switched_event_id")))

# ============================================================================
# PILLAR 2: VENDORS CAPABILITIES (DISCOVERY, COMPARISON, COMPLIANCE)
# ============================================================================
print("\n" + "=" * 50)
print("PILLAR 2: Vendors Capabilities (Discovery, Quotes, Compliance)")
print("=" * 50)

# 2.1 Discover vendor needs for new event
r_disc = requests.post(f"{BASE}/api/chat", json={
    "message": "Discover vendor needs and requirements for our event",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("2.1 Discover vendor needs returns 200", r_disc.status_code == 200)
disc_text = r_disc.json().get("text", "")
check("2.1 Discovery output contains categories", "Requirements" in disc_text or "Discovery" in disc_text)

# 2.2 Add vendor quotes to new event via API
r_v1 = requests.post(f"{BASE}/api/vendors", json={
    "company_name": f"Cascade Catering Co {audit_slug}",
    "category": "Catering",
    "quote_amount": 2240.0,
    "price_per_head": 14.0,
    "contact_email": "orders@cascadecatering.example",
    "details": "Full buffet lunch with GF, vegan, and nut-free certified boxes.",
    "event_id": evt_id
})
check("2.2 Add vendor quote 1 returns 200", r_v1.status_code == 200)

r_v2 = requests.post(f"{BASE}/api/vendors", json={
    "company_name": f"Pike Place Box Lunches {audit_slug}",
    "category": "Catering",
    "quote_amount": 2880.0,
    "price_per_head": 18.0,
    "contact_email": "sales@pikeplacebox.example",
    "details": "Artisanal sandwich boxes with organic fruit and sparkling water.",
    "event_id": evt_id
})
check("2.2 Add vendor quote 2 returns 200", r_v2.status_code == 200)

# 2.3 Verify vendor quote isolation (should only exist for evt_id)
r_records = requests.get(f"{BASE}/api/records/vendors?event_id={evt_id}")
check("2.3 GET /api/records/vendors?event_id= returns 200", r_records.status_code == 200)
v_list = r_records.json()
check("2.3 Event has exactly 2 quotes recorded", len(v_list) == 2)
v_names = [v["company_name"] for v in v_list]
check("2.3 Vendor 1 present in event", f"Cascade Catering Co {audit_slug}" in v_names)
check("2.3 Vendor 2 present in event", f"Pike Place Box Lunches {audit_slug}" in v_names)

# Check DubHacks vendors: should still have original Ballard Bites, etc.
r_dh_vendors = requests.get(f"{BASE}/api/records/vendors?event_id=evt-dubhacks-2026")
dh_v_names = [v["company_name"] for v in r_dh_vendors.json()]
check("2.3 DubHacks vendor list untouched by new event quotes", f"Cascade Catering Co {audit_slug}" not in dh_v_names)

# 2.4 Compare vendor quotes via Chat
r_comp = requests.post(f"{BASE}/api/chat", json={
    "message": "Compare catering vendor quotes and find the best vendor",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("2.4 Compare vendor quotes returns 200", r_comp.status_code == 200)
comp_text = r_comp.json().get("text", "")
check("2.4 Comparison contains comparison header", "Comparison" in comp_text)
check("2.4 Comparison mentions recommended vendor", "Cascade Catering Co" in comp_text or "Recommended" in comp_text)

# 2.5 Verify vendor compliance via Chat
r_verify = requests.post(f"{BASE}/api/chat", json={
    "message": f"Verify vendor compliance for Cascade Catering Co {audit_slug}",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("2.5 Verify compliance returns 200", r_verify.status_code == 200)
verify_text = r_verify.json().get("text", "")
check("2.5 Response confirms compliance updated", "Compliance" in verify_text or "Verified" in verify_text)

# ============================================================================
# PILLAR 3: OUTREACH CAPABILITIES (DRAFTING, HITL, REPLIES, FOLLOWUPS)
# ============================================================================
print("\n" + "=" * 50)
print("PILLAR 3: Outreach Capabilities (Drafts, HITL, Replies, Follow-ups)")
print("=" * 50)

# 3.1 Draft Outreach Email (HITL interception)
r_draft = requests.post(f"{BASE}/api/chat", json={
    "message": "Draft an outreach invitation email to Dr. Alicia Chen",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("3.1 Draft outreach returns 200", r_draft.status_code == 200)
draft_res = r_draft.json()
check("3.1 Intercepted action mentions Action Center / Approval", "Approval" in draft_res.get("text", "") or "Action Center" in draft_res.get("text", ""))

# 3.2 Verify pending action was logged in Action Center
r_actions = requests.get(f"{BASE}/api/actions?event_id={evt_id}")
check("3.2 GET /api/actions returns 200", r_actions.status_code == 200)
actions = r_actions.json()
check("3.2 At least 1 pending proposal in event", len(actions) >= 1)
pending_act = next((a for a in actions if a["status"] == "pending_approval"), None)
check("3.2 Found pending action proposal", pending_act is not None)
action_id = pending_act["id"] if pending_act else ""

# 3.3 Edit Action Draft Before Approval (HITL Safety)
if action_id:
    r_patch = requests.patch(f"{BASE}/api/actions/{action_id}", json={
        "subject": f"Custom Keynote Invitation: {audit_slug}",
        "message_body": "Updated draft with custom honorarium and presentation track."
    })
    check("3.3 PATCH /api/actions/{id} returns 200", r_patch.status_code == 200)
    check("3.3 Edited subject updated", r_patch.json().get("payload", {}).get("subject") == f"Custom Keynote Invitation: {audit_slug}")

# 3.4 Approve & Dispatch Action Proposal
if action_id:
    r_appr = requests.post(f"{BASE}/api/actions/{action_id}/approve")
    check("3.4 POST /api/actions/{id}/approve returns 200", r_appr.status_code == 200)
    check("3.4 Action marked executed", r_appr.json().get("status") == "executed")

    # Double-approval prevention guard
    r_double = requests.post(f"{BASE}/api/actions/{action_id}/approve")
    check("3.4 Double-approval prevented with 400", r_double.status_code == 400)

# 3.5 Process Inbound Outreach Reply (O2)
r_reply = requests.post(f"{BASE}/api/chat", json={
    "message": f"Reply from Dr. Alicia Chen: I would be thrilled to keynote the summit! I will talk about Autonomous Multi-Agent Reasoning. I am strictly gluten-free.",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("3.5 Process outreach reply returns 200", r_reply.status_code == 200)
reply_text = r_reply.json().get("text", "")
check("3.5 Response confirms reply parsed", "Reply Processed" in reply_text or "Confirmed" in reply_text or "Dr. Alicia Chen" in reply_text)

# Verify speaker record updated in DB
r_spk = requests.get(f"{BASE}/api/records/speakers?event_id={evt_id}")
check("3.5 Speaker saved to event DB", len(r_spk.json()) >= 1)
alicia = next((s for s in r_spk.json() if "Alicia" in s["name"]), None)
check("3.5 Speaker status confirmed in DB", alicia is not None and alicia.get("status") == "confirmed")

# 3.6 Check Stalled Outreach & Follow-ups (O3)
r_fol = requests.post(f"{BASE}/api/chat", json={
    "message": "Check follow ups and who has not replied yet",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("3.6 Check outreach follow-ups returns 200", r_fol.status_code == 200)
fol_text = r_fol.json().get("text", "")
check("3.6 Follow-ups response active", "Follow" in fol_text or "Stalled" in fol_text or "Outreach" in fol_text)

# 3.7 Draft Slack Message
r_slack = requests.post(f"{BASE}/api/chat", json={
    "message": "Draft a slack message to #general announcing our speaker lineup",
    "event_id": evt_id,
    "model": "semantic-engine"
})
check("3.7 Draft Slack message returns 200", r_slack.status_code == 200)
check("3.7 Slack proposal queued in Action Center", "Action proposal" in r_slack.json().get("text", "") or "Slack" in r_slack.json().get("text", ""))

# ============================================================================
# AUDIT SUMMARY
# ============================================================================
print("\n" + "=" * 70)
total = passed + failed
print(f"AUDIT SUMMARY: {passed}/{total} CHECKS PASSED, {failed} FAILED")
if failed == 0:
    print("ALL 3 CORE FEATURE PILLARS ARE FULLY IMPLEMENTED AND VERIFIED!")
    sys.exit(0)
else:
    print(f"WARNING: {failed} checks failed. See details above.")
    sys.exit(1)
