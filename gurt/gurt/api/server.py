"""Gurt FastAPI Server.

Independently implemented API server for Gurt.
Exposes endpoints for chat, event brief management, event records,
action center approvals, run-of-show schedule, and PDF form filling.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from gurt.config import settings
from gurt.db import (
    init_db,
    query_records,
    get_event_summary,
    get_event_brief,
    update_event_brief,
    create_event_brief,
    list_all_events,
    get_vendor_requirements,
    save_vendor_requirement,
    get_schedule_items,
    get_pdf_documents,
    get_conversations,
    create_conversation,
    delete_conversation,
    get_conversation_messages,
    save_message,
    get_memories,
    save_memory,
    delete_memory,
    get_audit_logs
)
from gurt.orchestrator import run_orchestrator
from gurt.tools.outreach_tools import execute_approved_action, dismiss_action, tool_update_draft
from gurt.tools.event_tools import (
    tool_create_task,
    tool_update_task_status,
    tool_add_vendor_quote,
    tool_generate_schedule,
    tool_lookup_schedule
)
from gurt.tools.logistics_tools import (
    tool_detect_schedule_conflicts,
    tool_preview_schedule_change,
    tool_generate_role_briefing,
    tool_get_role_briefings,
    tool_build_precision_run_of_show,
    tool_propose_conflict_resolutions,
    tool_apply_conflict_resolution
)
from gurt.tools.pdf_tools import fill_event_pdf_form, inspect_template_fields

# Initialize DB tables and seed data
init_db()

app = FastAPI(title="Gurt — Event Operations Agent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
GENERATED_DOCS_DIR = STATIC_DIR / "generated_docs"
GENERATED_DOCS_DIR.mkdir(parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []
    event_id: str = "evt-dubhacks-2026"
    conversation_id: str | None = None
    model: str | None = None


class ConversationCreateRequest(BaseModel):
    title: str = "New Conversation"
    event_id: str = "evt-dubhacks-2026"


class MemoryCreateRequest(BaseModel):
    key: str
    value: str
    category: str = "preference"
    event_id: str = "evt-dubhacks-2026"


class EventCreateRequest(BaseModel):
    title: str
    attendee_count: int = 50
    budget: float = 1000.0
    location: str = "Seattle Tech Hub"
    date: str = "TBD"
    theme: str = ""
    goals: str = ""
    dietary_specs: str = ""
    av_requirements: str = ""


class TaskRequest(BaseModel):
    title: str
    owner: str
    category: str = "Logistics"
    deadline: str = "2026-11-10"
    dependencies: str = "None"
    event_id: str = "evt-dubhacks-2026"


class StatusUpdateRequest(BaseModel):
    status: str


class VendorRequest(BaseModel):
    company_name: str
    category: str
    quote_amount: float
    price_per_head: float = 0.0
    details: str = ""
    contact_email: str = ""
    event_id: str = "evt-dubhacks-2026"


class VendorRequirementRequest(BaseModel):
    category: str
    specification: str
    headcount: int = 80
    budget_allocated: float = 0.0
    unknowns: str = ""
    status: str = "quoted"
    event_id: str = "evt-dubhacks-2026"


class BriefUpdateRequest(BaseModel):
    title: str | None = None
    date: str | None = None
    location: str | None = None
    attendee_count: int | None = None
    budget: float | None = None
    status: str | None = None
    goals: str | None = None
    theme: str | None = None
    venue_contact: str | None = None
    dietary_specs: str | None = None
    av_requirements: str | None = None


class DraftUpdateRequest(BaseModel):
    subject: str | None = None
    message_body: str | None = None


class SchedulePreviewRequest(BaseModel):
    session_id: str
    proposed_changes: dict[str, Any]
    event_id: str = "evt-dubhacks-2026"


class ApplyResolutionRequest(BaseModel):
    event_id: str = "evt-dubhacks-2026"
    session_id: str
    proposed_changes: dict[str, Any]
    expected_fingerprint: str | None = None
    conflict_id: str | None = None


class BriefingGenerateRequest(BaseModel):
    role: str = "speaker"
    recipient_id: str = ""
    event_id: str = "evt-dubhacks-2026"


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "app": "Gurt Event Operations Agent",
        "provider": settings.llm_provider,
        "database": str(settings.db_path)
    }


@app.get("/api/overview")
def get_overview(event_id: str = Query("evt-dubhacks-2026")) -> dict[str, Any]:
    return get_event_summary(event_id)


@app.get("/api/event/brief")
def get_brief_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> dict[str, Any]:
    return get_event_brief(event_id)


@app.put("/api/event/brief")
def update_brief_endpoint(req: BriefUpdateRequest, event_id: str = Query("evt-dubhacks-2026")) -> dict[str, Any]:
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    return update_event_brief(event_id, updates)


@app.get("/api/events")
def list_events_endpoint() -> list[dict[str, Any]]:
    return list_all_events()


@app.post("/api/events")
def create_event_endpoint(req: EventCreateRequest) -> dict[str, Any]:
    brief_data = {
        "title": req.title,
        "attendee_count": req.attendee_count,
        "budget": req.budget,
        "location": req.location,
        "date": req.date,
        "theme": req.theme,
        "goals": req.goals,
        "dietary_specs": req.dietary_specs,
        "av_requirements": req.av_requirements,
        "status": "planning"
    }
    return create_event_brief(brief_data)


@app.get("/api/events/{event_id}")
def get_event_by_id(event_id: str) -> dict[str, Any]:
    brief = get_event_brief(event_id)
    if not brief or not brief.get("id"):
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return brief


@app.get("/api/records/{table}")
def get_table_records(table: str, event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return query_records(table, event_id=event_id)


@app.get("/api/models")
def list_models() -> list[dict[str, str]]:
    return [
        {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (Default)"},
        {"id": "gemini-3-flash-preview", "name": "Gemini 3.0 Flash Preview"},
        {"id": "xai/grok-2-latest", "name": "Grok 2 (xAI)"},
        {"id": "semantic-engine", "name": "Gurt Dynamic Semantic Engine"}
    ]


@app.get("/api/conversations")
def list_conversations(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return get_conversations(event_id)


@app.post("/api/conversations")
def create_conversation_endpoint(req: ConversationCreateRequest) -> dict[str, Any]:
    return create_conversation(event_id=req.event_id, title=req.title)


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_messages_endpoint(conversation_id: str) -> list[dict[str, Any]]:
    return get_conversation_messages(conversation_id)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation_endpoint(conversation_id: str) -> dict[str, Any]:
    delete_conversation(conversation_id)
    return {"status": "deleted", "id": conversation_id}


@app.get("/api/memories")
def get_memories_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return get_memories(event_id)


@app.post("/api/memories")
def create_memory_endpoint(req: MemoryCreateRequest) -> dict[str, Any]:
    return save_memory(
        event_id=req.event_id,
        key=req.key,
        value=req.value,
        category=req.category
    )


@app.delete("/api/memories/{memory_id}")
def delete_memory_endpoint(memory_id: str) -> dict[str, Any]:
    delete_memory(memory_id)
    return {"status": "deleted", "id": memory_id}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conv_id = req.conversation_id
    if not conv_id:
        title_snippet = req.message[:28] + ("..." if len(req.message) > 28 else "")
        conv = create_conversation(event_id=req.event_id, title=title_snippet)
        conv_id = conv["id"]

    history = req.history
    if not history and conv_id:
        db_msgs = get_conversation_messages(conv_id)
        history = [{"role": m["role"], "content": m["content"]} for m in db_msgs]

    # Save user turn into SQLite
    save_message(
        conversation_id=conv_id,
        role="user",
        content=req.message
    )

    # Run orchestrator
    resp = run_orchestrator(
        req.message,
        history,
        event_id=req.event_id,
        model_name=req.model
    )

    # Save assistant turn into SQLite
    save_message(
        conversation_id=conv_id,
        role="assistant",
        content=resp.get("text", ""),
        tool_calls=resp.get("tool_calls"),
        model_used=resp.get("model_used")
    )

    resp["conversation_id"] = conv_id
    return resp


@app.get("/api/actions")
def get_actions(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return query_records("action_proposals", event_id=event_id)


@app.patch("/api/actions/{action_id}")
def edit_action_endpoint(action_id: str, req: DraftUpdateRequest) -> dict[str, Any]:
    result = tool_update_draft(action_id, subject=req.subject, message_body=req.message_body)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/actions/{action_id}/approve")
def approve_action(action_id: str) -> dict[str, Any]:
    result = execute_approved_action(action_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/actions/{action_id}/dismiss")
def dismiss_action_endpoint(action_id: str) -> dict[str, Any]:
    return dismiss_action(action_id)


@app.patch("/api/tasks/{task_id}/status")
def update_task_status_endpoint(task_id: str, req: StatusUpdateRequest) -> dict[str, Any]:
    result = tool_update_task_status(task_id, req.status)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/tasks")
def create_task_endpoint(req: TaskRequest) -> dict[str, Any]:
    return tool_create_task(
        title=req.title,
        owner=req.owner,
        category=req.category,
        deadline=req.deadline,
        dependencies=req.dependencies,
        event_id=req.event_id
    )


@app.post("/api/vendors")
def create_vendor_endpoint(req: VendorRequest) -> dict[str, Any]:
    return tool_add_vendor_quote(
        company_name=req.company_name,
        category=req.category,
        quote_amount=req.quote_amount,
        price_per_head=req.price_per_head,
        details=req.details,
        contact_email=req.contact_email,
        event_id=req.event_id
    )


@app.get("/api/vendor-requirements")
def get_vendor_requirements_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return get_vendor_requirements(event_id)


@app.post("/api/vendor-requirements")
def create_vendor_requirement_endpoint(req: VendorRequirementRequest) -> dict[str, Any]:
    return save_vendor_requirement(
        event_id=req.event_id,
        category=req.category,
        specification=req.specification,
        headcount=req.headcount,
        budget_allocated=req.budget_allocated,
        unknowns=req.unknowns,
        status=req.status
    )


@app.get("/api/schedule")
def get_schedule_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return tool_lookup_schedule(event_id)


@app.post("/api/schedule/generate")
def generate_schedule_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return tool_generate_schedule(event_id)


@app.get("/api/pdf/inspect")
def inspect_pdf_endpoint() -> dict[str, Any]:
    return inspect_template_fields()


@app.post("/api/pdf/fill")
def fill_pdf_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> dict[str, Any]:
    return fill_event_pdf_form(event_id)


@app.get("/api/pdf/documents")
def list_pdf_documents_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return get_pdf_documents(event_id)


@app.get("/api/pdf/download/{filename}")
def download_pdf_endpoint(filename: str) -> FileResponse:
    file_path = GENERATED_DOCS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        str(file_path),
        media_type="application/pdf",
        filename=filename
    )


# ---------------------------------------------------------------------------
# Logistics & Safety Engine Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/logistics/conflicts")
def get_logistics_conflicts_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> dict[str, Any]:
    return tool_detect_schedule_conflicts(event_id=event_id)


@app.post("/api/logistics/schedule/preview")
def preview_schedule_impact_endpoint(req: SchedulePreviewRequest) -> dict[str, Any]:
    return tool_preview_schedule_change(
        session_id=req.session_id,
        proposed_changes=req.proposed_changes,
        event_id=req.event_id
    )


@app.get("/api/logistics/conflicts/proposals")
def get_conflict_proposals_endpoint(
    event_id: str = Query("evt-dubhacks-2026"),
    conflict_id: str | None = Query(None)
) -> dict[str, Any]:
    return tool_propose_conflict_resolutions(conflict_id=conflict_id, event_id=event_id)


@app.post("/api/logistics/conflicts/apply")
def apply_conflict_resolution_endpoint(req: ApplyResolutionRequest) -> JSONResponse:
    result = tool_apply_conflict_resolution(
        event_id=req.event_id,
        session_id=req.session_id,
        proposed_changes=req.proposed_changes,
        expected_fingerprint=req.expected_fingerprint,
        conflict_id=req.conflict_id
    )
    if result.get("status") == "error":
        err_type = result.get("error")
        if err_type in ("not_found",):
            return JSONResponse(status_code=404, content=result)
        elif err_type in ("stale_proposal", "conflict_already_resolved"):
            return JSONResponse(status_code=409, content=result)
        else:
            return JSONResponse(status_code=400, content=result)
    return JSONResponse(status_code=200, content=result)


@app.get("/api/logistics/briefings")
def get_briefings_endpoint(
    event_id: str = Query("evt-dubhacks-2026"),
    role: str | None = Query(None)
) -> list[dict[str, Any]]:
    return tool_get_role_briefings(event_id=event_id, role=role)


@app.post("/api/logistics/briefings/generate")
def generate_briefing_endpoint(req: BriefingGenerateRequest) -> dict[str, Any]:
    return tool_generate_role_briefing(
        role=req.role,
        recipient_id=req.recipient_id,
        event_id=req.event_id
    )


@app.get("/api/logistics/run-of-show")
def get_precision_run_of_show_endpoint(event_id: str = Query("evt-dubhacks-2026")) -> dict[str, Any]:
    return tool_build_precision_run_of_show(event_id=event_id)


@app.get("/api/logistics/audit-logs")
def get_audit_logs_endpoint(
    event_id: str = Query("evt-dubhacks-2026"),
    limit: int = Query(50)
) -> list[dict[str, Any]]:
    return get_audit_logs(event_id=event_id, limit=limit)


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))
