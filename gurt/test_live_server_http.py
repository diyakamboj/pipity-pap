"""Test the actual running server on http://localhost:8000/api/chat
using the exact payload structure sent by app.js.
"""
import json
import urllib.request
from pathlib import Path

BASE_URL = "http://localhost:8000"

def post_chat(message: str, event_id: str = "evt-claude-workshop", history=None):
    payload = {
        "message": message,
        "history": history or [],
        "conversation_id": None,
        "model": "gemini-3.1-flash-lite",
        "event_id": event_id
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("======================================================================")
    print("TESTING LIVE SERVER HTTP: http://localhost:8000/api/chat")
    print("======================================================================\n")

    results = {}
    history = []

    # 1. Prompt 1: Even if sent from Chrome with another or stale event_id (e.g. evt-claude-workshop-3050 or evt-dubhacks-2026)
    p1 = "We're hosting a hands-on Claude workshop..."
    print(f"Prompt 1: \"{p1}\" (sending with event_id=evt-claude-workshop-3050 to verify resolution)")
    r1 = post_chat(p1, event_id="evt-claude-workshop-3050", history=history)
    text1 = r1.get("text", "")
    t_calls1 = [t.get("tool") for t in r1.get("tool_calls", [])]
    cond1 = (
        "40 attendees" in text1
        and "$500.00" in text1
        and "Blueprint" in text1
        and "update_event_brief" in t_calls1
        and r1.get("switched_event_id") == "evt-claude-workshop"
    )
    results["Prompt 1"] = "PASS" if cond1 else "FAIL"
    print(f"  Result: {results['Prompt 1']}")
    print(f"  Switched Event ID: {r1.get('switched_event_id')}")
    print(f"  Tools called: {t_calls1}")
    print(f"  Response Preview: {text1[:160]}...\n")
    history.append({"role": "user", "content": p1})
    history.append({"role": "assistant", "content": text1})

    # 2. Prompt 2: "Yo Gurt, find us a speaker..."
    p2 = "Yo Gurt, find us a speaker..."
    print(f"Prompt 2: \"{p2}\" (sending with event_id=evt-claude-workshop)")
    r2 = post_chat(p2, event_id="evt-claude-workshop", history=history)
    text2 = r2.get("text", "")
    t_calls2 = [t.get("tool") for t in r2.get("tool_calls", [])]
    cond2 = (
        "Marcus Rivera" in text2
        and "Dr. Alicia Chen" in text2
        and "SYNTHETIC" in text2
        and "compose_outreach_draft" in t_calls2
    )
    results["Prompt 2"] = "PASS" if cond2 else "FAIL"
    # Extract draft action ID
    import re
    m_act = re.search(r'act-[a-f0-9]+', text2)
    draft_id = m_act.group(0) if m_act else None
    print(f"  Result: {results['Prompt 2']}")
    print(f"  Action Center Draft ID: {draft_id}")
    print(f"  Tools called: {t_calls2}")
    print(f"  Response Preview: {text2[:180]}...\n")
    history.append({"role": "user", "content": p2})
    history.append({"role": "assistant", "content": text2})

    # 3. Prompt 3: "Make the invitation... shorter..."
    p3 = "Make the invitation... shorter..."
    print(f"Prompt 3: \"{p3}\" (sending with event_id=evt-claude-workshop)")
    r3 = post_chat(p3, event_id="evt-claude-workshop", history=history)
    text3 = r3.get("text", "")
    t_calls3 = [t.get("tool") for t in r3.get("tool_calls", [])]
    cond3 = (
        draft_id in text3
        and "coffee and snacks" in text3.lower()
        and "special note" not in text3.lower()
        and "update_draft" in t_calls3
    )
    results["Prompt 3"] = "PASS" if cond3 else "FAIL"
    print(f"  Result: {results['Prompt 3']}")
    print(f"  Draft ID Preserved: {draft_id in text3}")
    print(f"  Tools called: {t_calls3}")
    print(f"  Response Preview: {text3[:180]}...\n")
    history.append({"role": "user", "content": p3})
    history.append({"role": "assistant", "content": text3})

    # 4. Prompt 4: "Next, help us prepare the venue booking application..."
    p4 = "Next, help us prepare the venue booking application..."
    print(f"Prompt 4: \"{p4}\" (sending with event_id=evt-claude-workshop)")
    r4 = post_chat(p4, event_id="evt-claude-workshop", history=history)
    text4 = r4.get("text", "")
    t_calls4 = [t.get("tool") for t in r4.get("tool_calls", [])]
    pdf_tool = next((tc["output"] for tc in r4.get("tool_calls", []) if tc.get("tool") == "fill_event_pdf_form"), None)
    pdf_url4 = pdf_tool.get("download_url") if pdf_tool else None
    pdf_file4 = pdf_tool.get("output_file") if pdf_tool else None
    cond4 = (
        "fill_event_pdf_form" in t_calls4
        and pdf_url4 is not None
        and pdf_url4 in text4
        and "Missing Unresolved Fields" in text4
        and "HITL Safety Notice" in text4
    )
    # Check if download endpoint serves actual PDF bytes
    if pdf_url4:
        with urllib.request.urlopen(f"{BASE_URL}{pdf_url4}") as resp:
            pdf_bytes = resp.read()
            cond4 = cond4 and len(pdf_bytes) > 1000 and resp.headers.get("content-type") == "application/pdf"
    results["Prompt 4"] = "PASS" if cond4 else "FAIL"
    print(f"  Result: {results['Prompt 4']}")
    print(f"  Generated PDF: {pdf_file4} ({len(pdf_bytes)} bytes downloaded via HTTP)")
    print(f"  Tools called: {t_calls4}")
    print(f"  Response Preview: {text4[:180]}...\n")
    history.append({"role": "user", "content": p4})
    history.append({"role": "assistant", "content": text4})

    # 5. Prompt 5: "Add these organizer details..."
    p5 = "Add these organizer details: Diya Kamboj, Anthropic Community, diya@anthropic.example, 425-555-0199."
    print(f"Prompt 5: \"{p5}\" (sending with event_id=evt-claude-workshop)")
    r5 = post_chat(p5, event_id="evt-claude-workshop", history=history)
    text5 = r5.get("text", "")
    t_calls5 = [t.get("tool") for t in r5.get("tool_calls", [])]
    pdf_tool5 = next((tc["output"] for tc in r5.get("tool_calls", []) if tc.get("tool") == "fill_event_pdf_form"), None)
    pdf_url5 = pdf_tool5.get("download_url") if pdf_tool5 else None
    pdf_file5 = pdf_tool5.get("output_file") if pdf_tool5 else None
    cond5 = (
        "Diya Kamboj" in text5
        and "425-555-0199" in text5
        and pdf_url5 is not None
        and pdf_url5 in text5
        and pdf_file5 != pdf_file4
    )
    if pdf_url5:
        with urllib.request.urlopen(f"{BASE_URL}{pdf_url5}") as resp:
            pdf_bytes5 = resp.read()
            cond5 = cond5 and len(pdf_bytes5) > 1000 and resp.headers.get("content-type") == "application/pdf"
    results["Prompt 5"] = "PASS" if cond5 else "FAIL"
    print(f"  Result: {results['Prompt 5']}")
    print(f"  New PDF Version: {pdf_file5} ({len(pdf_bytes5)} bytes downloaded via HTTP)")
    print(f"  Tools called: {t_calls5}")
    print(f"  Response Preview: {text5[:180]}...\n")

    print("======================================================================")
    print("LIVE RUNNING SERVER FINAL SUMMARY:")
    print("======================================================================")
    for p_name, outcome in results.items():
        print(f"  {p_name}: {outcome}")
    print("======================================================================\n")

if __name__ == "__main__":
    main()
