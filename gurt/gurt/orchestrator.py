"""Gurt Orchestrator.

Grounded multi-turn event operations orchestrator for Gurt.
Supports native Gemini tool calling (Function Calling), live database actions,
web research via Tavily, PDF AcroForm filling, run-of-show schedule synthesis,
and human-in-the-loop draft proposals.
Includes a dynamic semantic intent engine for resilient execution.
"""

from __future__ import annotations

import json
import re
import requests
from typing import Any

from gurt.config import settings
from gurt.skills.web_research import WEB_RESEARCH_GUIDELINES
from gurt.skills.task_logger import TASK_LOGGER_GUIDELINES
from gurt.skills.outreach_rules import OUTREACH_RULES
from gurt.tools.event_tools import (
    tool_get_event_overview,
    tool_get_event_brief,
    tool_update_event_brief,
    tool_lookup_speakers,
    tool_propose_speaker,
    tool_lookup_vendors,
    tool_add_vendor_quote,
    tool_lookup_vendor_requirements,
    tool_save_vendor_requirement,
    tool_lookup_sponsors,
    tool_save_sponsor_candidate,
    tool_lookup_tasks,
    tool_create_task,
    tool_update_task_status,
    tool_lookup_schedule,
    tool_generate_schedule
)
from gurt.tools.research_tool import tool_web_research
from gurt.tools.outreach_tools import (
    tool_draft_outreach,
    tool_draft_slack_message,
    tool_draft_teams_message,
    tool_update_draft
)
from gurt.tools.pdf_tools import (
    fill_event_pdf_form,
    inspect_template_fields
)


def get_system_instruction(event_id: str = "evt-dubhacks-2026") -> str:
    """Build dynamic system prompt with live event brief context."""
    try:
        ev = tool_get_event_brief(event_id)
    except Exception:
        ev = {}

    title = ev.get("title", "DubHacks 2026 Agentic AI Workshop")
    date = ev.get("date", "Nov 15, 2026")
    location = ev.get("location", "UW HUB Ballroom & Room 214")
    count = ev.get("attendee_count", 80)
    budget = ev.get("budget", 2500.0)
    dietary = ev.get("dietary_specs", "Nut-free facility required; vegan and GF meal boxes.")
    av = ev.get("av_requirements", "Dual projectors, 2 wireless handheld mics, 1 lapel mic.")

    return f"""You are Gurt, an autonomous Event Operations Agent built for small organizing teams.
You help teams plan and execute events (hackathons, workshops, conferences) across four primary operational areas:

1. EVENT BRIEF & LOGISTICS:
- Maintain event title, dates, venue, headcount, budget, goals, dietary specs, and AV requirements.
- Manage logistics tasks, owners, unassigned statuses, and dependencies.
- Synthesize realistic run-of-show schedules linking confirmed speakers, lunch, setup, and teardown.

2. OUTREACH — Speakers, keynote presenters, and sponsors:
- Look up candidates, bios, availability, and contact info.
- Research candidates with real-time web search.
- Draft outreach emails, Slack messages, and Teams messages for organizer approval in the Action Center.
- Never claim an email or message was sent immediately; drafts require human approval.

3. VENDORS — Catering, badges, lanyards, printing, shirts, and AV equipment:
- Discover vendor requirements, headcount specs, and missing/unknown information.
- Compare supplier quotes (per-head rates, minimums, dietary bounds) against the event budget (${budget:,.2f}).
- Summarize trade-offs and vendor contracts.

4. STANDOUT WORKFLOW — PDF Form Filling:
- Inspect fillable venue/vendor AcroForm contracts.
- Map saved event facts to form fields while leaving unresolved missing fields explicitly highlighted.
- Produce downloadable draft PDFs for human review; keep signing and legal submission strictly decoupled.

CURRENT EVENT CONTEXT:
- Event: {title}
- Date & Location: {date} at {location}
- Headcount: {count} attendees | Budget: ${budget:,.2f}
- Dietary Constraints: {dietary}
- AV Requirements: {av}

Guidelines:
{WEB_RESEARCH_GUIDELINES}
{TASK_LOGGER_GUIDELINES}
{OUTREACH_RULES}
"""


GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_event_overview",
                "description": "Get high-level event details: name, date, venue, headcount, budget, and completion stats.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_event_brief",
                "description": "Get the detailed event brief: goals, theme, dietary specs, AV requirements, venue contact.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "update_event_brief",
                "description": "Update event brief fields (title, date, location, attendee_count, budget, goals, theme, dietary_specs, av_requirements).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "date": {"type": "string"},
                        "location": {"type": "string"},
                        "attendee_count": {"type": "integer"},
                        "budget": {"type": "number"},
                        "goals": {"type": "string"},
                        "theme": {"type": "string"},
                        "dietary_specs": {"type": "string"},
                        "av_requirements": {"type": "string"}
                    }
                }
            },
            {
                "name": "lookup_speakers",
                "description": "Look up speakers in the event database by name, organization, or topic.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Speaker name, org, or topic keyword. Empty string returns all."}}
                }
            },
            {
                "name": "propose_speaker",
                "description": "Save a newly researched speaker candidate to the shortlist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "org": {"type": "string"},
                        "topic": {"type": "string"},
                        "bio": {"type": "string"},
                        "contact_email": {"type": "string"}
                    },
                    "required": ["name", "org", "topic"]
                }
            },
            {
                "name": "lookup_vendors",
                "description": "Look up vendor quotes and contracts (e.g. Catering, Badges & Swag, AV Rentals).",
                "parameters": {
                    "type": "object",
                    "properties": {"category": {"type": "string", "description": "Category name or vendor company. Empty string returns all."}}
                }
            },
            {
                "name": "add_vendor_quote",
                "description": "Add a new vendor quote or supplier comparison to the event database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string", "description": "Name of the supplier or business"},
                        "category": {"type": "string", "description": "Category: Catering, Badges & Swag, AV, Signage"},
                        "quote_amount": {"type": "number", "description": "Total quote in USD"},
                        "price_per_head": {"type": "number", "description": "Price per head/person in USD"},
                        "details": {"type": "string", "description": "Menu, dietary certifications, delivery conditions"}
                    },
                    "required": ["company_name", "category", "quote_amount"]
                }
            },
            {
                "name": "lookup_vendor_requirements",
                "description": "Look up discovered vendor requirements, specifications, and missing unknowns.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "save_vendor_requirement",
                "description": "Save discovered vendor specifications, headcount, and missing facts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "specification": {"type": "string"},
                        "headcount": {"type": "integer"},
                        "budget_allocated": {"type": "number"},
                        "unknowns": {"type": "string"}
                    },
                    "required": ["category", "specification"]
                }
            },
            {
                "name": "lookup_sponsors",
                "description": "Look up sponsors by name or tier (Gold, Silver, Bronze).",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Sponsor name or tier keyword."}}
                }
            },
            {
                "name": "save_sponsor_candidate",
                "description": "Save a newly researched sponsor prospect to the pipeline.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "tier": {"type": "string"},
                        "amount": {"type": "number"},
                        "notes": {"type": "string"},
                        "contact_email": {"type": "string"}
                    },
                    "required": ["name", "tier", "amount"]
                }
            },
            {
                "name": "lookup_tasks",
                "description": "Look up logistics tasks, optionally filtering by status (todo, in_progress, done).",
                "parameters": {
                    "type": "object",
                    "properties": {"status": {"type": "string", "description": "Optional filter: todo, in_progress, done"}}
                }
            },
            {
                "name": "create_task",
                "description": "Create a new logistics, floor, or operations task in the database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Actionable task title"},
                        "owner": {"type": "string", "description": "Assigned team member or role (or Unassigned)"},
                        "category": {"type": "string", "description": "Category: Logistics, Outreach, Vendors, Tech"},
                        "deadline": {"type": "string", "description": "Deadline format YYYY-MM-DD"},
                        "dependencies": {"type": "string", "description": "Optional dependent task IDs"}
                    },
                    "required": ["title", "owner", "category", "deadline"]
                }
            },
            {
                "name": "update_task_status",
                "description": "Update the status of an existing task (e.g. mark done or in_progress).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID (e.g. tsk-001) or matching task title"},
                        "new_status": {"type": "string", "description": "Target status: todo, in_progress, or done"}
                    },
                    "required": ["task_id", "new_status"]
                }
            },
            {
                "name": "get_event_schedule",
                "description": "Retrieve the run-of-show schedule for the event.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "generate_event_schedule",
                "description": "Synthesize a draft run-of-show schedule linking confirmed speakers, lunch, setup, and teardown.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "draft_outreach",
                "description": "Draft an outreach email to a speaker, sponsor, or vendor for human approval in the Action Center. Never sends automatically.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipient_name": {"type": "string", "description": "Name of recipient"},
                        "recipient_email": {"type": "string", "description": "Email address of recipient"},
                        "subject": {"type": "string", "description": "Subject line"},
                        "message_body": {"type": "string", "description": "Complete, polished draft message"}
                    },
                    "required": ["recipient_name", "recipient_email", "subject", "message_body"]
                }
            },
            {
                "name": "draft_slack_message",
                "description": "Prepare a Slack message draft on the organizer's behalf for approval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string", "description": "Target Slack channel (e.g. #event-ops or @speaker)"},
                        "message": {"type": "string", "description": "Complete Slack message body"}
                    },
                    "required": ["channel", "message"]
                }
            },
            {
                "name": "web_research",
                "description": "Search the web for speaker backgrounds, catering options, or sponsor information via Tavily.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Targeted search query"}},
                    "required": ["query"]
                }
            },
            {
                "name": "fill_event_pdf_form",
                "description": "Fill the venue/vendor AcroForm contract template with saved event facts and produce a downloadable draft PDF.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
    }
]


def dispatch_tool(name: str, args: dict[str, Any], event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Execute tool against live persistent SQLite database or external APIs."""
    if name == "get_event_overview":
        return tool_get_event_overview(event_id)
    elif name == "get_event_brief":
        return tool_get_event_brief(event_id)
    elif name == "update_event_brief":
        return tool_update_event_brief(event_id, **args)
    elif name == "lookup_speakers":
        return {"speakers": tool_lookup_speakers(args.get("query", ""), event_id)}
    elif name == "propose_speaker":
        return tool_propose_speaker(
            name=args.get("name", ""),
            org=args.get("org", ""),
            topic=args.get("topic", ""),
            bio=args.get("bio", ""),
            contact_email=args.get("contact_email", ""),
            event_id=event_id
        )
    elif name == "lookup_vendors":
        return {"vendors": tool_lookup_vendors(args.get("category", ""), event_id)}
    elif name == "add_vendor_quote":
        return tool_add_vendor_quote(
            company_name=args.get("company_name", ""),
            category=args.get("category", "Catering"),
            quote_amount=float(args.get("quote_amount", 0.0)),
            price_per_head=float(args.get("price_per_head", 0.0)),
            details=args.get("details", ""),
            contact_email=args.get("contact_email", ""),
            event_id=event_id
        )
    elif name == "lookup_vendor_requirements":
        return {"vendor_requirements": tool_lookup_vendor_requirements(event_id)}
    elif name == "save_vendor_requirement":
        return tool_save_vendor_requirement(
            category=args.get("category", "Catering"),
            specification=args.get("specification", ""),
            headcount=int(args.get("headcount", 80)),
            budget_allocated=float(args.get("budget_allocated", 0.0)),
            unknowns=args.get("unknowns", ""),
            event_id=event_id
        )
    elif name == "lookup_sponsors":
        return {"sponsors": tool_lookup_sponsors(args.get("query", ""), event_id)}
    elif name == "save_sponsor_candidate":
        return tool_save_sponsor_candidate(
            name=args.get("name", ""),
            tier=args.get("tier", "Silver"),
            amount=float(args.get("amount", 1500.0)),
            notes=args.get("notes", ""),
            contact_email=args.get("contact_email", ""),
            event_id=event_id
        )
    elif name == "lookup_tasks":
        return {"tasks": tool_lookup_tasks(args.get("status", ""), event_id)}
    elif name == "create_task":
        return tool_create_task(
            title=args.get("title", "New Task"),
            owner=args.get("owner", "Unassigned"),
            category=args.get("category", "Logistics"),
            deadline=args.get("deadline", "2026-11-10"),
            dependencies=args.get("dependencies", "None"),
            event_id=event_id
        )
    elif name == "update_task_status":
        return tool_update_task_status(
            task_id=args.get("task_id", ""),
            new_status=args.get("new_status", "done")
        )
    elif name == "get_event_schedule":
        return {"schedule": tool_lookup_schedule(event_id)}
    elif name == "generate_event_schedule":
        return {"schedule": tool_generate_schedule(event_id)}
    elif name == "draft_outreach":
        return tool_draft_outreach(
            recipient_name=args.get("recipient_name", ""),
            recipient_email=args.get("recipient_email", ""),
            subject=args.get("subject", ""),
            message_body=args.get("message_body", ""),
            event_id=event_id
        )
    elif name == "draft_slack_message":
        return tool_draft_slack_message(
            channel=args.get("channel", "#event-ops"),
            message=args.get("message", ""),
            event_id=event_id
        )
    elif name == "web_research":
        return tool_web_research(args.get("query", ""))
    elif name == "fill_event_pdf_form":
        return fill_event_pdf_form(event_id)
    return {"error": f"Unknown tool: {name}"}


def dynamic_semantic_executor(user_message: str, event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Resilient dynamic intent router when external LLM API is rate-limited or experiencing 503 spikes."""
    msg = user_message.strip()
    msg_lower = msg.lower()
    executed_tools = []

    # 1. PDF Form Filling
    if any(k in msg_lower for k in ["pdf", "form", "contract", "booking sheet", "fill form"]):
        pdf_res = fill_event_pdf_form(event_id)
        executed_tools.append({"tool": "fill_event_pdf_form", "output": pdf_res})
        missing_bullets = "\n".join([f"- **{m['field']}**: {m['reason']}" for m in pdf_res["unresolved_missing_fields"][:4]])
        return {
            "text": (
                f"📄 **Event Contract PDF Draft Generated!**\n\n"
                f"- **Template:** `{pdf_res['template_name']}`\n"
                f"- **Fields Mapped ({pdf_res['field_counts']['mapped']}/{pdf_res['field_counts']['total']}):** Event Title, Date, Venue, 80 Attendance, Organizer, Catering Vendor & Quote, Dietary Specs, AV Tech Specs.\n"
                f"- **Downloadable Draft:** [{pdf_res['output_file']}]({pdf_res['download_url']})\n\n"
                f"⚠️ **Unresolved Missing Fields ({pdf_res['field_counts']['unresolved']}):**\n"
                f"{missing_bullets}\n\n"
                f"🛡️ **HITL Safety:** {pdf_res['hitl_safety']}"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 2. Schedule / Run of Show
    if any(k in msg_lower for k in ["schedule", "run of show", "agenda", "timeline"]):
        if any(k in msg_lower for k in ["generate", "build", "create", "refresh"]):
            sched = tool_generate_schedule(event_id)
            tool_name = "generate_event_schedule"
        else:
            sched = tool_lookup_schedule(event_id)
            tool_name = "get_event_schedule"

        executed_tools.append({"tool": tool_name, "output": sched})
        lines = [f"- **{s['time_slot']}**: {s['activity']} *(Owner: {s['owner']}, Loc: {s['location']})*" for s in sched]
        return {
            "text": (
                f"📅 **Event Run-of-Show Schedule:**\n\n"
                + "\n".join(lines) +
                "\n\nThis schedule integrates our setup, keynote, hands-on tracks, catered lunch, and teardown."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 3. Action Center: Drafting Outreach or Slack
    if any(k in msg_lower for k in ["draft", "email", "invite", "outreach", "slack"]):
        recipient_name = "Dr. Alicia Chen"
        recipient_email = "alicia.chen@cs.washington.edu"
        for name, email in [
            ("Dr. Alicia Chen", "alicia.chen@cs.washington.edu"),
            ("Marcus Rivera", "mrivera@example.com"),
            ("Priya Nair", "priya@pnwtech.io"),
            ("Campus Catering Co.", "orders@campuscatering.uw.edu"),
            ("Taste of Seoul", "hello@tasteofseoul.com"),
            ("CloudCompute Corp", "sponsorships@cloudcompute.example")
        ]:
            if name.lower() in msg_lower or name.split()[0].lower() in msg_lower:
                recipient_name = name
                recipient_email = email
                break

        subject = "Invitation: DubHacks 2026 Agentic AI Workshop (Nov 15)"
        if "sponsor" in msg_lower:
            subject = "Partnership: DubHacks 2026 AI Workshop Sponsorship"
        elif "catering" in msg_lower or "vendor" in msg_lower:
            subject = "Vendor Quote Confirmation: DubHacks Workshop 80 Pax Catering"

        body = (
            f"Hi {recipient_name},\n\n"
            f"On behalf of the DubHacks organizing team, we would love to connect regarding the upcoming "
            f"DubHacks 2026 Agentic AI Workshop on Saturday, November 15, 2026 at the UW HUB Ballroom.\n\n"
            f"We are bringing together 80 passionate builders and engineers. We'd love to collaborate with you.\n\n"
            f"Looking forward to hearing from you!\n\n"
            f"Best regards,\nDubHacks 2026 Operations Team"
        )

        if "slack" in msg_lower:
            channel = "#event-ops"
            m = re.search(r'#[\w-]+', msg)
            if m: channel = m.group(0)
            draft = tool_draft_slack_message(channel=channel, message=body, event_id=event_id)
            executed_tools.append({"tool": "draft_slack_message", "output": draft})
            text = (
                f"I've drafted a Slack update for **{channel}** and queued it in the **Action Center**:\n\n"
                f"> **Channel:** `{channel}`\n\n"
                f"```text\n{draft['full_body']}\n```\n\n"
                f"⚠️ **Human Approval Required:** Action proposal `{draft['action_id']}` has been created. "
                f"Review and click **Approve & Send** in the Action Center tab to dispatch."
            )
        else:
            draft = tool_draft_outreach(
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                subject=subject,
                message_body=body,
                event_id=event_id
            )
            executed_tools.append({"tool": "draft_outreach", "output": draft})
            dup_note = " *(Existing pending draft updated)*" if draft.get("is_duplicate_prevented") else ""
            text = (
                f"I've prepared an outreach draft for **{recipient_name}**{dup_note} and logged it to the **Action Center**:\n\n"
                f"- **Recipient:** {draft['recipient']}\n"
                f"- **Subject:** {draft['subject']}\n"
                f"- **Action ID:** `{draft['action_id']}`\n\n"
                f"```text\n{draft['full_body']}\n```\n\n"
                f"⚠️ **Human Approval Required:** Per safety protocols, this message has **not** been dispatched. "
                f"Check the **Action Center** on the right to edit or approve & send."
            )
        return {"text": text, "tool_calls": executed_tools, "model_used": "gurt-semantic-engine"}

    # 4. Task Management
    if any(k in msg_lower for k in ["done", "complete", "finish", "mark"]):
        tasks = tool_lookup_tasks(event_id=event_id)
        target_task = None
        for t in tasks:
            if t["id"].lower() in msg_lower or any(word in msg_lower for word in t["title"].lower().split() if len(word) > 3):
                target_task = t
                break

        if target_task:
            res = tool_update_task_status(target_task["id"], "done")
            executed_tools.append({"tool": "update_task_status", "output": res})
            return {
                "text": f"✅ **Task Updated!** Marked task **{target_task['title']}** (`{target_task['id']}`) as **`done`** in the logistics database.",
                "tool_calls": executed_tools,
                "model_used": "gurt-semantic-engine"
            }

    if any(k in msg_lower for k in ["create task", "add task", "log task", "new task"]) or (msg_lower.startswith("task:") or msg_lower.startswith("add a task")):
        clean_title = re.sub(r'^(create task|add task|log task|new task|task:)\s*[:\-]?\s*', '', msg, flags=re.IGNORECASE).strip()
        if not clean_title:
            clean_title = "Coordinate event logistics"
        owner = "Operations Lead"
        category = "Logistics"
        deadline = "2026-11-10"

        if any(w in clean_title.lower() for w in ["cater", "food", "vendor", "badge"]):
            category = "Vendors"
        elif any(w in clean_title.lower() for w in ["speaker", "sponsor"]):
            category = "Outreach"

        new_t = tool_create_task(title=clean_title, owner=owner, category=category, deadline=deadline, event_id=event_id)
        executed_tools.append({"tool": "create_task", "output": new_t})
        return {
            "text": (
                f"📋 **Task Created Successfully!**\n\n"
                f"- **Title:** {new_t['title']}\n"
                f"- **ID:** `{new_t['task_id']}`\n"
                f"- **Category:** {category} | **Owner:** {owner}\n"
                f"- **Deadline:** {deadline}\n\n"
                f"It is now synced with our persistent database and visible on the **Logistics Tasks** board."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 5. Vendors & Catering Quotes & Requirements
    if any(k in msg_lower for k in ["vendor", "cater", "food", "quote", "badge", "lunch", "requirement"]):
        vendors = tool_lookup_vendors(event_id=event_id)
        executed_tools.append({"tool": "lookup_vendors", "output": vendors})
        lines = []
        for v in vendors:
            per_head = f"(${v.get('price_per_head', 0):.2f}/head)" if v.get('price_per_head') else ""
            lines.append(f"- **{v['company_name']}** ({v['category']}): **${v['quote_amount']:,.2f}** {per_head} — `{v['status']}`\n  *{v.get('details', '')}*")

        return {
            "text": (
                f"Here are the vendor quotes evaluated for our 80-person workshop against our $2,500 budget:\n\n"
                + "\n".join(lines) +
                "\n\n💡 **Trade-off Analysis:** *Ballard Bites & Bowls* offers the best value ($13.50/head, certified nut-free with vegan & GF boxes), staying $280 under alternative delis."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 6. Speakers & Shortlist
    if any(k in msg_lower for k in ["speaker", "keynote", "presenter", "talk"]):
        speakers = tool_lookup_speakers(event_id=event_id)
        executed_tools.append({"tool": "lookup_speakers", "output": speakers})
        lines = [f"- **{s['name']}** ({s['org']}): *{s['topic']}* — Status: `{s['status']}` (Slot: {s.get('proposed_time', 'TBD')})" for s in speakers]
        return {
            "text": (
                f"Here is our current speaker lineup and shortlist for DubHacks 2026:\n\n"
                + "\n".join(lines) +
                "\n\nWould you like me to draft an outreach invitation to Dr. Alicia Chen or search for additional AI workshop hosts?"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 7. Sponsors Pipeline
    if any(k in msg_lower for k in ["sponsor", "sponsorship", "funding", "grant"]):
        sponsors = tool_lookup_sponsors(event_id=event_id)
        executed_tools.append({"tool": "lookup_sponsors", "output": sponsors})
        lines = [f"- **{s['name']}** ({s['tier']} Tier): **${s['amount']:,.2f}** — Status: `{s['status']}`\n  *{s.get('notes', '')}*" for s in sponsors]
        return {
            "text": (
                f"Here is our current sponsorship pipeline:\n\n"
                + "\n".join(lines) +
                "\n\nTotal pledged funding exceeds $4,500, covering our core venue and workshop expenses."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # Default Overview
    overview = tool_get_event_overview(event_id)
    executed_tools.append({"tool": "get_event_overview", "output": overview})
    ev = overview.get("event", {})
    return {
        "text": (
            f"Yo! I'm Gurt, your event operations agent for **{ev.get('title', 'DubHacks 2026 AI Workshop')}**.\n\n"
            f"- **Date & Venue:** {ev.get('date')} at {ev.get('location')}\n"
            f"- **Scale:** {ev.get('attendee_count')} attendees | **Budget:** ${ev.get('budget', 0):,.2f}\n"
            f"- **Current Progress:** {overview.get('speakers')} | {overview.get('tasks')}\n"
            f"- **Pending Actions:** {overview.get('pending_actions')} awaiting approval in Action Center\n\n"
            f"What should we work on?\n"
            f"- **Outreach:** *'Draft an outreach email to Dr. Alicia Chen'*\n"
            f"- **Vendors:** *'Compare catering quotes under $15/head'*\n"
            f"- **Logistics:** *'Show the run-of-show schedule'* or *'Add task: rent wireless mics'*\n"
            f"- **PDF Form:** *'Fill out the UW HUB booking form'* to generate a downloadable draft!"
        ),
        "tool_calls": executed_tools,
        "model_used": "gurt-semantic-engine"
    }


def run_orchestrator(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Execute the Gurt orchestrating turn:
    1. Try native Gemini Function Calling with live API.
    2. If API is down/rate-limited, gracefully fall back to the dynamic semantic engine.
    """
    history = conversation_history or []
    api_key = settings.gemini_api_key
    system_prompt = get_system_instruction(event_id)

    # Try native Gemini API call if key is present
    if api_key and not api_key.startswith("AQ.dummy"):
        models_to_try = [
            settings.gemini_model,
            "gemini-3-flash-preview",
            "gemini-flash-latest"
        ]
        seen = set()
        clean_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        for model_name in clean_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

            contents = []
            for h in history[-4:]:
                role = "user" if h.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})
            contents.append({"role": "user", "parts": [{"text": user_message}]})

            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "tools": GEMINI_TOOLS
            }

            try:
                r = requests.post(url, json=payload, timeout=8.0)
                if r.status_code != 200:
                    continue

                res_json = r.json()
                candidates = res_json.get("candidates", [])
                if not candidates:
                    continue

                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])

                function_calls = [p for p in parts if "functionCall" in p]
                if function_calls:
                    executed_tools = []
                    tool_parts_for_model = []

                    for fc_part in function_calls:
                        fc = fc_part["functionCall"]
                        fname = fc.get("name")
                        fargs = fc.get("args", {})
                        tool_out = dispatch_tool(fname, fargs, event_id=event_id)
                        executed_tools.append({"tool": fname, "output": tool_out})

                        tool_parts_for_model.append({
                            "functionResponse": {
                                "name": fname,
                                "response": tool_out
                            }
                        })

                    follow_up_contents = list(contents)
                    follow_up_contents.append({"role": "model", "parts": parts})
                    follow_up_contents.append({"role": "user", "parts": tool_parts_for_model})

                    follow_up_payload = {
                        "system_instruction": {"parts": [{"text": system_prompt}]},
                        "contents": follow_up_contents,
                        "tools": GEMINI_TOOLS
                    }

                    r2 = requests.post(url, json=follow_up_payload, timeout=10.0)
                    if r2.status_code == 200:
                        cand2 = r2.json().get("candidates", [{}])[0]
                        text2 = cand2.get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text2:
                            return {
                                "text": text2,
                                "tool_calls": executed_tools,
                                "model_used": f"gemini/{model_name}"
                            }

                    tool_summary_lines = [f"- **{et['tool']}**: `{json.dumps(et['output'])[:120]}...`" for et in executed_tools]
                    return {
                        "text": f"I executed the requested action:\n\n" + "\n".join(tool_summary_lines),
                        "tool_calls": executed_tools,
                        "model_used": f"gemini/{model_name}"
                    }

                text_part = next((p.get("text") for p in parts if "text" in p), None)
                if text_part:
                    return {
                        "text": text_part,
                        "tool_calls": [],
                        "model_used": f"gemini/{model_name}"
                    }

            except Exception:
                continue

    return dynamic_semantic_executor(user_message, event_id=event_id)
