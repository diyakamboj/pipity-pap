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
from fastapi.responses import FileResponse
from pydantic import BaseModel

from gurt.config import settings
from gurt.db import (
    init_db,
    query_records,
    get_event_summary,
    get_event_brief,
    update_event_brief,
    create_event_brief,
    get_vendor_requirements,
    save_vendor_requirement,
    get_schedule_items,
    get_pdf_documents
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


@app.get("/api/records/{table}")
def get_table_records(table: str, event_id: str = Query("evt-dubhacks-2026")) -> list[dict[str, Any]]:
    return query_records(table, event_id=event_id)


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return run_orchestrator(req.message, req.history, event_id=req.event_id)


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


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))
