"""Gurt FastAPI Server.

Independently implemented API server for Gurt.
Exposes endpoints for chat, event records, action center approvals, and web UI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from gurt.config import settings
from gurt.db import init_db, query_records, get_event_summary, get_connection
from gurt.orchestrator import run_orchestrator
from gurt.tools.outreach_tools import execute_approved_action
from gurt.tools.event_tools import tool_create_task

# Initialize DB tables and seed data
init_db()

app = FastAPI(title="Gurt — Event Operations Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class TaskRequest(BaseModel):
    title: str
    owner: str
    category: str = "Logistics"
    deadline: str = "2026-11-10"
    dependencies: str = "None"


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "app": "Gurt Event Operations Agent",
        "provider": settings.llm_provider,
        "database": str(settings.db_path)
    }


@app.get("/api/overview")
def get_overview() -> dict[str, Any]:
    return get_event_summary()


@app.get("/api/records/{table}")
def get_table_records(table: str) -> list[dict[str, Any]]:
    return query_records(table)


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return run_orchestrator(req.message, req.history)


@app.get("/api/actions")
def get_actions() -> list[dict[str, Any]]:
    return query_records("action_proposals")


@app.post("/api/actions/{action_id}/approve")
def approve_action(action_id: str) -> dict[str, Any]:
    result = execute_approved_action(action_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/actions/{action_id}/dismiss")
def dismiss_action_endpoint(action_id: str) -> dict[str, Any]:
    from gurt.tools.outreach_tools import dismiss_action
    return dismiss_action(action_id)


class StatusUpdateRequest(BaseModel):
    status: str


@app.patch("/api/tasks/{task_id}/status")
def update_task_status_endpoint(task_id: str, req: StatusUpdateRequest) -> dict[str, Any]:
    from gurt.tools.event_tools import tool_update_task_status
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
        dependencies=req.dependencies
    )


class VendorRequest(BaseModel):
    company_name: str
    category: str
    quote_amount: float
    price_per_head: float = 0.0
    details: str = ""
    contact_email: str = ""


@app.post("/api/vendors")
def create_vendor_endpoint(req: VendorRequest) -> dict[str, Any]:
    from gurt.tools.event_tools import tool_add_vendor_quote
    return tool_add_vendor_quote(
        company_name=req.company_name,
        category=req.category,
        quote_amount=req.quote_amount,
        price_per_head=req.price_per_head,
        details=req.details,
        contact_email=req.contact_email
    )



# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))
