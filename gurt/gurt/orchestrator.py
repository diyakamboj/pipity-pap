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
from gurt.skills.vendor_intelligence import VENDOR_INTELLIGENCE_GUIDELINES
from gurt.skills.outreach_management import OUTREACH_MANAGEMENT_GUIDELINES
from gurt.tools.event_tools import (
    tool_get_event_overview,
    tool_get_event_brief,
    tool_update_event_brief,
    tool_list_events,
    tool_create_event,
    tool_switch_event,
    tool_lookup_speakers,
    tool_propose_speaker,
    tool_lookup_vendors,
    tool_add_vendor_quote,
    tool_lookup_vendor_requirements,
    tool_save_vendor_requirement,
    tool_discover_vendor_needs,
    tool_compare_vendor_quotes,
    tool_verify_vendor_compliance,
    tool_lookup_sponsors,
    tool_save_sponsor_candidate,
    tool_lookup_tasks,
    tool_create_task,
    tool_update_task_status,
    tool_lookup_schedule,
    tool_generate_schedule
)
from gurt.tools.research_tool import tool_web_research
from gurt.db import get_memories, save_memory
from gurt.tools.outreach_tools import (
    tool_draft_outreach,
    tool_draft_slack_message,
    tool_draft_teams_message,
    tool_update_draft,
    tool_process_outreach_reply,
    tool_record_sponsor_commitment,
    tool_check_outreach_followups
)
from gurt.tools.pdf_tools import (
    fill_event_pdf_form,
    inspect_template_fields
)


def get_system_instruction(event_id: str = "evt-dubhacks-2026") -> str:
    """Build dynamic system prompt with live event brief context and persistent memories."""
    try:
        ev = tool_get_event_brief(event_id)
    except Exception:
        ev = {}

    title = ev.get("title") or "Event"
    date = ev.get("date") or "TBD"
    location = ev.get("location") or "TBD"
    count = ev.get("attendee_count") or 50
    budget = float(ev.get("budget") or 1000.0)
    dietary = ev.get("dietary_specs") or "Standard accommodations"
    av = ev.get("av_requirements") or "Standard AV"

    try:
        mems = get_memories(event_id)
        if mems:
            mem_lines = "\n".join([f"- {m['key']} ({m['category']}): {m['value']}" for m in mems])
            memory_section = f"\nORGANIZER MEMORY & PERSISTENT CONSTRAINTS:\n{mem_lines}\n"
        else:
            memory_section = ""
    except Exception:
        memory_section = ""

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
{memory_section}
Guidelines:
CRITICAL EVENT CREATION & SETUP:
- When the user expresses intent to plan a new event (e.g. "I want to plan a new event"), invite them to share the event title, date, location, headcount, and budget.
- When the user provides the event name and details (e.g. "It a Loveable Community Workshop. I'm expecting 30 people... budget $400"), you MUST call `create_event(title="Loveable Community Workshop", attendee_count=30, budget=400.0, ...)` with those details.
- NEVER call `update_event_brief`, `list_events`, or `lookup_sponsors` when the user is giving you details to create a new event.
- NEVER assume or inject sponsors from other events into a new event.
- When switching between existing events, call `switch_event(event_id_or_title=...)`.

{WEB_RESEARCH_GUIDELINES}
{TASK_LOGGER_GUIDELINES}
{OUTREACH_RULES}
{VENDOR_INTELLIGENCE_GUIDELINES}
{OUTREACH_MANAGEMENT_GUIDELINES}
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
            },
            {
                "name": "save_event_memory",
                "description": "Store an organizer preference, rule, constraint, or fact in persistent long-term memory across chats.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Short key identifier (e.g. catering_cutoff_time)"},
                        "value": {"type": "string", "description": "The exact rule or preference to remember"},
                        "category": {"type": "string", "description": "Category (preference, dietary_rule, budget_rule, contact)"}
                    },
                    "required": ["key", "value"]
                }
            },
            {
                "name": "list_events",
                "description": "List all registered events in the workspace database with task/speaker/vendor counts.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "create_event",
                "description": "Create a completely new event with its own brief, tasks, and requirements. Use this instead of update_event_brief when the user wants a NEW event.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Event title"},
                        "attendee_count": {"type": "integer", "description": "Expected number of attendees"},
                        "budget": {"type": "number", "description": "Total event budget in USD"},
                        "location": {"type": "string", "description": "Event venue or location"},
                        "date": {"type": "string", "description": "Event date/time"},
                        "theme": {"type": "string"},
                        "goals": {"type": "string"},
                        "dietary_specs": {"type": "string"},
                        "av_requirements": {"type": "string"}
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "switch_event",
                "description": "Switch the active event context by event ID or title.",
                "parameters": {
                    "type": "object",
                    "properties": {"event_id_or_title": {"type": "string", "description": "Event ID (e.g. evt-dubhacks-2026) or title keyword"}},
                    "required": ["event_id_or_title"]
                }
            },
            {
                "name": "discover_vendor_needs",
                "description": "Contextually discover overlooked operational and supplier requirements beyond food (badges, signage, AV, shirts). Seeds vendor requirements and asks clarifying questions.",
                "parameters": {
                    "type": "object",
                    "properties": {"event_type": {"type": "string", "description": "Type of event: workshop, hackathon, conference, meetup"}}
                }
            },
            {
                "name": "compare_vendor_quotes",
                "description": "Compare supplier quotes in a category, calculate cost-per-head, and evaluate budget feasibility.",
                "parameters": {
                    "type": "object",
                    "properties": {"category": {"type": "string", "description": "Vendor category to compare: Catering, Badges, AV, etc."}},
                    "required": ["category"]
                }
            },
            {
                "name": "verify_vendor_compliance",
                "description": "Verify vendor licensing, food safety permits, and Certificate of Insurance status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name_or_id": {"type": "string", "description": "Vendor company name or vendor ID"},
                        "verified": {"type": "boolean", "description": "Whether compliance is verified"},
                        "notes": {"type": "string", "description": "Optional compliance notes"}
                    },
                    "required": ["company_name_or_id"]
                }
            },
            {
                "name": "process_outreach_reply",
                "description": "Parse a pasted speaker or sponsor reply to extract availability, topic confirmation, dietary needs, sponsor commitment, and conditions. Updates persistent records.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_name": {"type": "string", "description": "Name of the person who replied"},
                        "reply_text": {"type": "string", "description": "The full text of their reply"}
                    },
                    "required": ["contact_name", "reply_text"]
                }
            },
            {
                "name": "record_sponsor_commitment",
                "description": "Record a confirmed sponsor pledge with tier, amount, and agreed benefits.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sponsor_name": {"type": "string"},
                        "tier": {"type": "string", "description": "Gold, Silver, or Bronze"},
                        "amount": {"type": "number", "description": "Committed sponsorship amount in USD"},
                        "benefits_agreed": {"type": "string", "description": "Agreed sponsor benefits (logo placement, booth, etc.)"},
                        "notes": {"type": "string"}
                    },
                    "required": ["sponsor_name", "tier", "amount"]
                }
            },
            {
                "name": "check_outreach_followups",
                "description": "Identify stalled outreach candidates (speakers in shortlist/contacted, sponsors in pipeline/discussion) and pending action proposals that need follow-up.",
                "parameters": {
                    "type": "object",
                    "properties": {"days_threshold": {"type": "integer", "description": "How many days without response to consider stalled (default 3)"}}
                }
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
    elif name == "inspect_template_fields":
        return inspect_template_fields()
    elif name == "save_event_memory":
        return save_memory(
            event_id=event_id,
            key=args.get("key", "preference"),
            value=args.get("value", ""),
            category=args.get("category", "preference")
        )
    elif name == "list_events":
        return {"events": tool_list_events()}
    elif name == "create_event":
        return tool_create_event(
            title=args.get("title", "New Event"),
            attendee_count=int(args.get("attendee_count", 50)),
            budget=float(args.get("budget", 1000.0)),
            location=args.get("location", "Seattle Tech Hub"),
            date=args.get("date", "TBD"),
            theme=args.get("theme", ""),
            goals=args.get("goals", ""),
            dietary_specs=args.get("dietary_specs", ""),
            av_requirements=args.get("av_requirements", "")
        )
    elif name == "switch_event":
        result = tool_switch_event(args.get("event_id_or_title", ""))
        return result
    elif name == "discover_vendor_needs":
        return tool_discover_vendor_needs(
            event_id=event_id,
            event_type=args.get("event_type", "workshop")
        )
    elif name == "compare_vendor_quotes":
        return tool_compare_vendor_quotes(
            category=args.get("category", "Catering"),
            event_id=event_id
        )
    elif name == "verify_vendor_compliance":
        return tool_verify_vendor_compliance(
            company_name_or_id=args.get("company_name_or_id", ""),
            event_id=event_id,
            verified=args.get("verified", True),
            notes=args.get("notes", "")
        )
    elif name == "process_outreach_reply":
        return tool_process_outreach_reply(
            contact_name=args.get("contact_name", ""),
            reply_text=args.get("reply_text", ""),
            event_id=event_id
        )
    elif name == "record_sponsor_commitment":
        return tool_record_sponsor_commitment(
            sponsor_name=args.get("sponsor_name", ""),
            tier=args.get("tier", "Silver"),
            amount=float(args.get("amount", 1500.0)),
            benefits_agreed=args.get("benefits_agreed", ""),
            notes=args.get("notes", ""),
            event_id=event_id
        )
    elif name == "check_outreach_followups":
        return tool_check_outreach_followups(
            event_id=event_id,
            days_threshold=int(args.get("days_threshold", 3))
        )
    return {"error": f"Unknown tool: {name}"}


def format_tool_execution_response(executed_tools: list[dict[str, Any]], event_id: str = "evt-dubhacks-2026") -> str:
    """Format executed tool calls into natural, user-friendly markdown rather than raw JSON."""
    tool_names = [et.get("tool") for et in executed_tools]

    if "create_event" in tool_names:
        for et in executed_tools:
            if et.get("tool") == "create_event":
                out = et.get("output", {})
                return (
                    f"🎉 **New Event Initialized!**\n\n"
                    f"- **Title:** {out.get('title', 'New Event')}\n"
                    f"- **Event ID:** `{out.get('event_id', '')}`\n"
                    f"- **Attendees:** {out.get('attendee_count', '?')} | **Budget:** ${out.get('budget', 0):,.2f} | **Location:** {out.get('location', 'TBD')}\n\n"
                    f"Active workspace switched to **{out.get('title')}**. We can now build tasks, shortlist speakers, compare vendors, or seek sponsorships!"
                )

    if "lookup_sponsors" in tool_names:
        sponsors = []
        for et in executed_tools:
            if et.get("tool") == "lookup_sponsors":
                out = et.get("output", {})
                if isinstance(out, dict):
                    sponsors = out.get("sponsors", [])
                elif isinstance(out, list):
                    sponsors = out
        if not sponsors:
            ev = tool_get_event_brief(event_id) or {}
            return f"There are currently no sponsors recorded or in discussion yet for **{ev.get('title', 'this event')}**. Would you like me to research and add prospective sponsors?"
        lines = [f"- **{s['name']}** ({s['tier']} Tier): **${s['amount']:,.2f}** — Status: `{s['status']}`" for s in sponsors]
        return "Here is the current sponsorship pipeline for this event:\n\n" + "\n".join(lines)

    if "lookup_speakers" in tool_names:
        speakers = []
        for et in executed_tools:
            if et.get("tool") == "lookup_speakers":
                out = et.get("output", {})
                speakers = out.get("speakers", []) if isinstance(out, dict) else out
        if not speakers:
            return "There are no speakers shortlisted yet for this event. Would you like me to research potential keynote speakers or workshop leaders?"
        lines = [f"- **{s['name']}** ({s['org']}): *{s['topic']}* — `{s['status']}`" for s in speakers]
        return "Here is our current speaker shortlist:\n\n" + "\n".join(lines)

    if "get_event_overview" in tool_names:
        ov = tool_get_event_overview(event_id)
        ev = ov.get("event", {})
        return (
            f"Here is the status for **{ev.get('title', 'our event')}**:\n\n"
            f"- **Date & Venue:** {ev.get('date')} at {ev.get('location')}\n"
            f"- **Scale:** {ev.get('attendee_count')} attendees | Budget: ${ev.get('budget', 0):,.2f}\n"
            f"- **Progress:** {ov.get('speakers')} | {ov.get('tasks')}"
        )

    lines = [f"- **{et['tool']}**: `{json.dumps(et['output'])[:120]}...`" for et in executed_tools]
    return "I executed the requested operations:\n\n" + "\n".join(lines)


def dynamic_semantic_executor(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Resilient dynamic intent router when external LLM API is rate-limited or experiencing 503 spikes."""
    msg = user_message.strip()
    msg_lower = msg.lower()
    executed_tools = []
    history = conversation_history or []

    # Memory: Save or query organizer preferences
    if any(k in msg_lower for k in ["remember that", "remember:", "note that", "save memory", "keep in mind"]):
        fact = re.sub(r'^(remember that|remember:|note that|save memory|keep in mind)\s*[:\-]?\s*', '', msg, flags=re.IGNORECASE).strip()
        key = re.sub(r'[^a-z0-9_]+', '_', fact[:24].lower()).strip('_') or "preference"
        saved = save_memory(event_id=event_id, key=key, value=fact, category="user_preference")
        executed_tools.append({"tool": "save_event_memory", "output": saved})
        return {
            "text": f"🧠 **Got it, I've committed that to memory!**\n\n- **Key:** `{saved['key']}`\n- **Rule / Fact:** {saved['value']}\n\nI will remember this across all chats and operations.",
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    if any(k in msg_lower for k in ["what do you remember", "show memory", "list memories", "my preferences"]):
        mems = get_memories(event_id=event_id)
        if not mems:
            return {"text": "I don't have any custom organizer memories stored yet. You can tell me *'Remember that lunch cutoff is 11:30 AM'*, and I will keep it in mind!", "tool_calls": [], "model_used": "gurt-semantic-engine"}
        lines = [f"- **{m['key']}** ({m['category']}): {m['value']}" for m in mems]
        return {
            "text": "🧠 **Here is what I have saved in persistent memory for this event:**\n\n" + "\n".join(lines),
            "tool_calls": [],
            "model_used": "gurt-semantic-engine"
        }

    # Detect if assistant previously asked to set up a new event
    last_assistant_msg = ""
    for h in reversed(history):
        if h.get("role") in ("assistant", "model"):
            last_assistant_msg = h.get("content", "").lower()
            break
    is_answering_event_setup = any(k in last_assistant_msg for k in ["new event set up", "event title", "headcount", "workspace", "initialize the new event"])

    # 0a. Event Creation (Explicit command, or answering follow-up, or natural event description)
    has_event_command = any(k in msg_lower for k in ["create event", "new event", "create a new event", "make a new event", "add event", "start a new event", "plan a new event"])
    has_event_details = any(w in msg_lower for w in ["workshop", "hackathon", "conference", "meetup", "summit", "gathering"]) and any(w in msg_lower for w in ["people", "attendee", "headcount", "budget", "rsvp"])

    if has_event_command or is_answering_event_setup or has_event_details:
        # If user is only stating they want to plan an event without details
        if (msg_lower in ["i want to plan a new event", "plan a new event", "new event", "create an event", "create a new event"] 
            or (has_event_command and not any(w in msg_lower for w in ["people", "attendee", "budget", "$", "workshop", "hackathon", "summit"]))):
            return {
                "text": (
                    "I'm ready! To get the new event set up in the system, just let me know:\n\n"
                    "1. **Event Title** (e.g., *'Loveable Community Workshop'*)\n"
                    "2. **Date & Location**\n"
                    "3. **Expected Headcount**\n"
                    "4. **Total Budget**\n\n"
                    "Once you give me the details, I'll initialize the new event workspace so we can start tracking tasks, speakers, and vendors without overwriting your other projects."
                ),
                "tool_calls": [],
                "model_used": "gurt-semantic-engine"
            }

        clean_text = re.sub(r'^(?:create event|new event|create a new event|make a new event|add event|start a new event|plan a new event)\s*[:—-]?\s*', '', msg, flags=re.IGNORECASE).strip()
        
        # Extract title
        title = None
        # Pattern like "It a Loveable Community Workshop" or "It's a Loveable Community Workshop"
        m_it = re.search(r'(?:it(?:\'s|\s+is|\s+a)?)\s+([A-Za-z0-9\s]+?(?:workshop|hackathon|conference|meetup|summit|event))\b', clean_text, flags=re.IGNORECASE)
        if m_it:
            title = m_it.group(1).strip()
        
        if not title:
            m_name = re.search(r'(?:called|named)\s+["\']?([^"\',]+)["\']?', clean_text, flags=re.IGNORECASE)
            if m_name:
                title = m_name.group(1).strip()

        if not title:
            # Fallback before conjunctions
            chunk = re.split(r'\s+(?:with|for|at|budget|expecting|i\'m expecting|we need)\b', clean_text, flags=re.IGNORECASE)[0].strip()
            chunk = re.sub(r'^(?:it(?:\'s|\s+is|\s+a)?)\s*', '', chunk, flags=re.IGNORECASE).strip()
            if len(chunk) > 2 and len(chunk) < 60:
                title = chunk

        if not title or len(title) < 2:
            title = "New Event Workshop"

        m_count = re.search(r'(\d+)\s*(?:attendees?|pax|people|guests?)', clean_text, flags=re.IGNORECASE)
        attendee_count = int(m_count.group(1)) if m_count else 30

        m_budget = re.search(r'(?:budget\s*(?:right now is|is|of|around)?\s*)?\$(\d[\d,]*)|(?:budget\s*(?:right now is|is|of|around)?\s*)(\d[\d,]*)', clean_text, flags=re.IGNORECASE)
        if m_budget:
            budget_str = m_budget.group(1) or m_budget.group(2)
            budget = float(budget_str.replace(',', ''))
        else:
            budget = 400.0

        m_loc = re.search(r'(?:at|in)\s+([A-Z][\w\s]+?)(?:\s+(?:with|for|budget|expecting)|\.|$)', clean_text)
        location = m_loc.group(1).strip() if m_loc else "TBD Location"

        result = tool_create_event(title=title, attendee_count=attendee_count, budget=budget, location=location)
        executed_tools.append({"tool": "create_event", "output": result})
        return {
            "text": (
                f"🎉 **New Event Created!**\n\n"
                f"- **Title:** {result['title']}\n"
                f"- **Event ID:** `{result['event_id']}`\n"
                f"- **Attendees:** {attendee_count} | **Budget:** ${budget:,.2f} | **Location:** {location}\n"
                f"- **Status:** Planning\n\n"
                f"This is a completely distinct event with its own tasks, vendors, and requirements. "
                f"Active event switched to `{result['title']}`."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine",
            "switched_event_id": result["event_id"]
        }

    # 0b. List Events
    if any(k in msg_lower for k in ["list events", "show events", "all events", "my events", "which events"]):
        events = tool_list_events()
        executed_tools.append({"tool": "list_events", "output": events})
        lines = [f"- **{e['title']}** (`{e['id']}`) — {e.get('attendee_count', '?')} attendees, ${e.get('budget', 0):,.0f} budget, {e.get('tasks_count', 0)} tasks" for e in events]
        return {
            "text": f"📋 **Registered Events ({len(events)}):**\n\n" + "\n".join(lines),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 0c. Switch Event
    if any(k in msg_lower for k in ["switch to", "switch event", "change event", "work on event"]):
        target = re.sub(r'^(switch to|switch event|change event|work on event)\s*[:—-]?\s*', '', msg, flags=re.IGNORECASE).strip()
        result = tool_switch_event(target)
        executed_tools.append({"tool": "switch_event", "output": result})
        if result.get("error"):
            return {"text": f"❌ {result['error']}", "tool_calls": executed_tools, "model_used": "gurt-semantic-engine"}
        return {
            "text": (
                f"🔄 **Switched active event to:** {result['title']} (`{result['event_id']}`)\n\n"
                f"All operations will now target this event."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine",
            "switched_event_id": result["event_id"]
        }

    # 0d. Discover Vendor Needs (V1)
    if any(k in msg_lower for k in ["discover vendor", "vendor needs", "what vendors", "overlooked needs", "what do we need", "vendor checklist"]):
        result = tool_discover_vendor_needs(event_id=event_id)
        executed_tools.append({"tool": "discover_vendor_needs", "output": result})
        req_lines = [f"- **{r.get('category', 'TBD')}**: {r.get('specification', '')[:80]}... — `{r.get('status')}`" for r in result.get("requirements", [])[:6]]
        q_lines = "\n".join(result.get("discovery_questions", []))
        return {
            "text": (
                f"🔍 **Vendor & Supplier Needs Discovery for {result.get('event_title', 'this event')}** ({result.get('headcount', '?')} attendees)\n\n"
                f"**Requirements ({result.get('discovered_categories_count', 0)} categories):**\n"
                + "\n".join(req_lines) +
                f"\n\n**Questions I Need Answered:**\n{q_lines}\n\n"
                f"*{result.get('summary', '')}*"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 0e. Compare Vendor Quotes (V2)
    if ("compare" in msg_lower and any(w in msg_lower for w in ["quote", "quotes", "vendor", "vendors", "catering", "cost", "price"])) or any(k in msg_lower for k in ["compare quote", "compare quotes", "compare vendor", "compare vendors", "vendor comparison", "quote comparison", "best vendor", "cheapest", "trade-off", "tradeoff"]):
        category = "Catering"
        for cat in ["catering", "badge", "av", "signage", "shirt", "printing"]:
            if cat in msg_lower:
                category = cat.capitalize()
                break
        result = tool_compare_vendor_quotes(category=category, event_id=event_id)
        executed_tools.append({"tool": "compare_vendor_quotes", "output": result})
        if result.get("status") == "no_quotes_found":
            return {"text": f"No vendor quotes found for **{category}**. Add quotes first with *'Add a vendor quote for...'*", "tool_calls": executed_tools, "model_used": "gurt-semantic-engine"}
        comp_lines = [f"- **{c['company_name']}**: ${c['quote_amount']:,.2f} (${c['price_per_head']:.2f}/head) {'✅ Within budget' if c['is_within_budget'] else '❌ Over budget'}" for c in result.get("comparison_matrix", [])]
        return {
            "text": (
                f"📊 **Vendor Quote Comparison: {category}**\n"
                f"Budget: ${result.get('event_budget', 0):,.2f} | Attendees: {result.get('attendee_count', '?')}\n\n"
                + "\n".join(comp_lines) +
                f"\n\n🏆 **Recommended:** {result.get('recommended_vendor', 'N/A')} — {result.get('recommendation_reason', '')}"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 0f. Verify Vendor Compliance (V2)
    if any(k in msg_lower for k in ["verify vendor", "compliance", "license check", "vendor compliance", "food safety"]):
        # Extract vendor name from message
        vname = re.sub(
            r'^(?:verify\s+vendor\s+compliance|verify\s+compliance|verify\s+vendor|vendor\s+compliance|compliance|license check|food safety)\s*(?:for|of|:|-)?\s*',
            '',
            msg,
            flags=re.IGNORECASE
        ).strip()
        vname = re.sub(r'\s+compliance$', '', vname, flags=re.IGNORECASE).strip()
        if not vname or len(vname) < 2:
            vname = "Ballard Bites"
        result = tool_verify_vendor_compliance(company_name_or_id=vname, event_id=event_id)
        executed_tools.append({"tool": "verify_vendor_compliance", "output": result})
        if result.get("error"):
            return {
                "text": f"❌ Vendor Compliance Error: {result['error']}",
                "tool_calls": executed_tools,
                "model_used": "gurt-semantic-engine"
            }
        return {
            "text": (
                f"🛡️ **Vendor Compliance Updated**\n\n"
                f"- **Vendor:** {result.get('company_name')} (`{result.get('vendor_id')}`)\n"
                f"- **Category:** {result.get('category')}\n"
                f"- **Verified:** {'✅ Yes' if result.get('compliance_verified') else '❌ No'}\n"
                f"- **Notes:** {result.get('compliance_notes', '')}\n\n"
                f"ℹ️ {result.get('king_county_regulatory_note', '')}"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 0g. Process Outreach Reply (O2)
    if any(k in msg_lower for k in ["reply from", "response from", "got a reply", "process reply", "they replied"]):
        # Try to extract contact name
        name_match = re.search(r'(?:reply|response)\s+from\s+([A-Z][\w\s\.]+?)(?:\s*[:—,]|\s+saying|\s+that|\s+who)', msg, flags=re.IGNORECASE)
        contact = name_match.group(1).strip() if name_match else "Unknown Contact"
        # The rest is the reply text
        reply = re.sub(r'^.*?(?:[:—]\s*|saying\s+)', '', msg, flags=re.IGNORECASE).strip() or msg
        result = tool_process_outreach_reply(contact_name=contact, reply_text=reply, event_id=event_id)
        executed_tools.append({"tool": "process_outreach_reply", "output": result})
        ext = result.get("extracted", {})
        return {
            "text": (
                f"📨 **Outreach Reply Processed — {result.get('contact_name')}**\n\n"
                f"- **Interest:** {ext.get('interest_level', 'unknown')}\n"
                f"- **Topic Confirmed:** {'✅' if ext.get('topic_confirmed') else '❌'}\n"
                f"- **Dietary Needs:** {', '.join(ext.get('dietary_needs', [])) or 'None specified'}\n"
                f"- **Conditions Flagged:** {len(ext.get('conditions', []))}\n"
                + (f"- **Record Updated:** {result['updated_record']['type'].title()} → `{result['updated_record']['new_status']}`\n" if result.get("updated_record") else "")
                + (f"- **Tasks Created:** {len(result.get('created_tasks', []))}\n" if result.get("created_tasks") else "")
                + f"\n*{result.get('summary', '')}*"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 0h. Check Outreach Follow-ups (O3)
    if any(k in msg_lower for k in ["follow up", "followup", "stalled", "check follow", "who hasn't replied", "pending outreach"]):
        result = tool_check_outreach_followups(event_id=event_id)
        executed_tools.append({"tool": "check_outreach_followups", "output": result})
        sugg_lines = [f"- **{s['name']}** ({s['type'].replace('_', ' ')}) — {s['suggested_action']}" for s in result.get("followup_suggestions", [])[:5]]
        pending_lines = [f"- `{a['id']}`: {a['title']}" for a in result.get("pending_action_details", [])[:5]]
        return {
            "text": (
                f"📬 **Outreach Follow-Up Report**\n\n"
                f"**Stalled Contacts:** {result.get('stalled_speakers', 0)} speakers, {result.get('stalled_sponsors', 0)} sponsors\n"
                f"**Pending Approval Actions:** {result.get('pending_actions', 0)}\n\n"
                + ("**Suggested Follow-ups:**\n" + "\n".join(sugg_lines) + "\n\n" if sugg_lines else "")
                + ("**Pending Actions in Action Center:**\n" + "\n".join(pending_lines) + "\n\n" if pending_lines else "")
                + f"*{result.get('summary', '')}*"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

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

        ev = tool_get_event_brief(event_id) or {}
        event_title = ev.get("title", "Event")
        event_date = ev.get("date", "upcoming date")
        event_loc = ev.get("location", "our venue")
        event_headcount = ev.get("attendee_count", 80)

        subject = f"Invitation: {event_title} ({event_date})"
        if "sponsor" in msg_lower:
            subject = f"Partnership: {event_title} Sponsorship"
        elif "catering" in msg_lower or "vendor" in msg_lower:
            subject = f"Vendor Quote Confirmation: {event_title} Catering"

        body = (
            f"Hi {recipient_name},\n\n"
            f"On behalf of the {event_title} organizing team, we would love to connect regarding the upcoming "
            f"{event_title} on {event_date} at {event_loc}.\n\n"
            f"We are bringing together {event_headcount} passionate builders and attendees. We'd love to collaborate with you.\n\n"
            f"Looking forward to hearing from you!\n\n"
            f"Best regards,\n{event_title} Operations Team"
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
        ev = tool_get_event_brief(event_id) or {}
        event_title = ev.get("title", "this event")
        attendees = ev.get("attendee_count", 80)
        budget = ev.get("budget", 2500.0)
        vendors = tool_lookup_vendors(event_id=event_id)
        executed_tools.append({"tool": "lookup_vendors", "output": vendors})
        lines = []
        for v in vendors:
            per_head = f"(${v.get('price_per_head', 0):.2f}/head)" if v.get('price_per_head') else ""
            lines.append(f"- **{v['company_name']}** ({v['category']}): **${v['quote_amount']:,.2f}** {per_head} — `{v['status']}`\n  *{v.get('details', '')}*")

        analysis_note = ""
        if vendors:
            best_v = min(vendors, key=lambda x: x.get("quote_amount", 999999))
            analysis_note = f"\n\n💡 **Trade-off Analysis:** *{best_v['company_name']}* offers the best value at ${best_v['quote_amount']:,.2f}."

        return {
            "text": (
                f"Here are the vendor quotes evaluated for **{event_title}** ({attendees} attendees, ${budget:,.2f} budget):\n\n"
                + ("\n".join(lines) if lines else "*No vendor quotes recorded yet for this event.*")
                + analysis_note
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 6. Speakers & Shortlist
    if any(k in msg_lower for k in ["speaker", "keynote", "presenter", "talk"]):
        ev = tool_get_event_brief(event_id) or {}
        event_title = ev.get("title", "our event")
        speakers = tool_lookup_speakers(event_id=event_id)
        executed_tools.append({"tool": "lookup_speakers", "output": speakers})
        lines = [f"- **{s['name']}** ({s['org']}): *{s['topic']}* — Status: `{s['status']}` (Slot: {s.get('proposed_time', 'TBD')})" for s in speakers]
        return {
            "text": (
                f"Here is our current speaker lineup and shortlist for **{event_title}**:\n\n"
                + ("\n".join(lines) if lines else "*No speakers shortlisted yet for this event.*")
                + f"\n\nWould you like me to draft an outreach invitation or search for additional speakers?"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 7. Sponsor Confirmation Breakdown
    if "confirmed" in msg_lower and any(w in msg_lower for w in ["sponsor", "sponsors", "these", "they"]):
        sponsors = tool_lookup_sponsors(event_id=event_id)
        executed_tools.append({"tool": "lookup_sponsors", "output": sponsors})
        confirmed = [s for s in sponsors if s.get("status") == "confirmed"]
        discussion = [s for s in sponsors if s.get("status") == "discussion"]
        pipeline = [s for s in sponsors if s.get("status") == "pipeline"]

        status_sections = []
        if confirmed:
            c_lines = "\n".join(f"- **{s['name']}** ({s['tier']} Tier): **${s['amount']:,.2f}** — `confirmed` ({s.get('notes', '')})" for s in confirmed)
            status_sections.append(f"✅ **Confirmed Sponsors:**\n{c_lines}")
        else:
            status_sections.append("✅ **Confirmed Sponsors:** None confirmed yet.")

        if discussion:
            d_lines = "\n".join(f"- **{s['name']}** ({s['tier']} Tier): **${s['amount']:,.2f}** — `discussion` ({s.get('notes', '')})" for s in discussion)
            status_sections.append(f"💬 **In Active Discussion:**\n{d_lines}")

        if pipeline:
            p_lines = "\n".join(f"- **{s['name']}** ({s['tier']} Tier): **${s['amount']:,.2f}** — `pipeline` ({s.get('notes', '')})" for s in pipeline)
            status_sections.append(f"⏳ **In Prospect Pipeline:**\n{p_lines}")

        return {
            "text": (
                "Here is the confirmation status for our sponsors:\n\n"
                + "\n\n".join(status_sections)
                + f"\n\nOnly the confirmed sponsors ({len(confirmed)}) have finalized commitments."
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 7b. Sponsors Pipeline
    if any(k in msg_lower for k in ["sponsor", "sponsorship", "funding", "grant"]):
        sponsors = tool_lookup_sponsors(event_id=event_id)
        executed_tools.append({"tool": "lookup_sponsors", "output": sponsors})
        lines = [f"- **{s['name']}** ({s['tier']} Tier): **${s['amount']:,.2f}** — Status: `{s['status']}`\n  *{s.get('notes', '')}*" for s in sponsors]
        total_funding = sum(s.get("amount", 0.0) for s in sponsors)
        confirmed_funding = sum(s.get("amount", 0.0) for s in sponsors if s.get("status") == "confirmed")
        summary_str = (
            f"Total pipeline funding: **${total_funding:,.2f}** (with **${confirmed_funding:,.2f}** confirmed)."
            if sponsors else "*No sponsors in pipeline for this event yet.*"
        )
        return {
            "text": (
                f"Here is our current sponsorship pipeline for this event:\n\n"
                + ("\n".join(lines) if lines else "*No sponsors recorded yet.*")
                + f"\n\n{summary_str}"
            ),
            "tool_calls": executed_tools,
            "model_used": "gurt-semantic-engine"
        }

    # 8. Clarification / Confusion handling
    if any(k in msg_lower for k in ["what are u saying", "what are you saying", "what do you mean", "confused", "makes no sense", "huh"]):
        ev = tool_get_event_brief(event_id) or {}
        event_title = ev.get("title", "our active event")
        return {
            "text": (
                f"Apologies for any confusion! We are currently operating in the workspace for **{event_title}**.\n\n"
                f"Tell me what you'd like to work on:\n"
                f"- **New Event:** *'I want to plan a Loveable Community Workshop for 30 people with a $400 budget'*\n"
                f"- **Outreach:** *'Draft an outreach invitation to Dr. Alicia Chen'*\n"
                f"- **Vendors:** *'Compare catering vendor quotes under $15/head'*\n"
                f"- **Schedule:** *'Generate the event run-of-show'* or *'Show tasks'*"
            ),
            "tool_calls": [],
            "model_used": "gurt-semantic-engine"
        }

    # Default Overview
    overview = tool_get_event_overview(event_id)
    executed_tools.append({"tool": "get_event_overview", "output": overview})
    ev = overview.get("event", {})
    ev_title = ev.get("title", "Event Operations")
    ev_date = ev.get("date", "Upcoming")
    ev_loc = ev.get("location", "TBD Venue")
    ev_headcount = ev.get("attendee_count", 0)
    ev_budget = ev.get("budget", 0.0)
    return {
        "text": (
            f"Yo! I'm Gurt, your event operations agent for **{ev_title}**.\n\n"
            f"- **Date & Venue:** {ev_date} at {ev_loc}\n"
            f"- **Scale:** {ev_headcount} attendees | **Budget:** ${ev_budget:,.2f}\n"
            f"- **Current Progress:** {overview.get('speakers', '0')} | {overview.get('tasks', '0')}\n"
            f"- **Pending Actions:** {overview.get('pending_actions', 0)} awaiting approval in Action Center\n\n"
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
    event_id: str = "evt-dubhacks-2026",
    model_name: str | None = None
) -> dict[str, Any]:
    """Execute the Gurt orchestrating turn:
    1. If model_name is 'semantic-engine', route directly to dynamic local engine.
    2. If model_name is Grok, route via xAI API.
    3. Try native Gemini Function Calling with selected or default Gemini model.
    4. Fall back to the dynamic semantic engine on rate-limit/error.
    """
    history = conversation_history or []
    system_prompt = get_system_instruction(event_id)

    # 1. Direct offline semantic engine option
    if model_name in ("semantic-engine", "gurt-semantic-engine"):
        return dynamic_semantic_executor(user_message, conversation_history=history, event_id=event_id)

    # 2. Grok / xAI model option
    if model_name and "grok" in model_name.lower() and settings.grok_api_key and not settings.grok_api_key.startswith("grok_dummy"):
        try:
            messages = [{"role": "system", "content": system_prompt}]
            for h in history[-4:]:
                messages.append({"role": "user" if h.get("role") == "user" else "assistant", "content": h.get("content", "")})
            messages.append({"role": "user", "content": user_message})

            grok_res = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.grok_api_key}",
                    "Content-Type": "application/json"
                },
                json={"model": "grok-2-latest", "messages": messages, "temperature": 0.3},
                timeout=10.0
            )
            if grok_res.status_code == 200:
                ans = grok_res.json()["choices"][0]["message"]["content"]
                return {
                    "text": ans,
                    "tool_calls": [],
                    "model_used": "xai/grok-2-latest"
                }
        except Exception:
            pass

    # 3. Gemini models
    api_key = settings.gemini_api_key
    if api_key and not api_key.startswith("AQ.dummy"):
        requested_gemini = model_name if (model_name and "gemini" in model_name.lower()) else settings.gemini_model
        models_to_try = [
            requested_gemini,
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest"
        ]
        seen = set()
        clean_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        for m_name in clean_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"

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

                    switched_id = None
                    for et in executed_tools:
                        if et.get("tool") in ("create_event", "switch_event"):
                            out = et.get("output", {})
                            if out.get("event_id"):
                                switched_id = out["event_id"]

                    r2 = requests.post(url, json=follow_up_payload, timeout=10.0)
                    if r2.status_code == 200:
                        cand2 = r2.json().get("candidates", [{}])[0]
                        text2 = cand2.get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text2:
                            resp_dict = {
                                "text": text2,
                                "tool_calls": executed_tools,
                                "model_used": f"gemini/{m_name}"
                            }
                            if switched_id:
                                resp_dict["switched_event_id"] = switched_id
                            return resp_dict

                    formatted_text = format_tool_execution_response(executed_tools, event_id=switched_id or event_id)
                    resp_dict = {
                        "text": formatted_text,
                        "tool_calls": executed_tools,
                        "model_used": f"gemini/{m_name}"
                    }
                    if switched_id:
                        resp_dict["switched_event_id"] = switched_id
                    return resp_dict

                text_part = next((p.get("text") for p in parts if "text" in p), None)
                if text_part:
                    return {
                        "text": text_part,
                        "tool_calls": [],
                        "model_used": f"gemini/{m_name}"
                    }

            except Exception:
                continue

    return dynamic_semantic_executor(user_message, conversation_history=history, event_id=event_id)
