"""hr-mcp: read-only HR data tools exposed over MCP (stdio).

The HRAgents backend launches this as a subprocess (see frontend's
app/api/chat/route.ts -> agent.mcp_config) and exposes each function below to
the agent as a tool. Every tool is READ-ONLY by design: this server never sends
messages, mutates records, or takes irreversible actions. Action/"send" tools
are handled separately as client_tools so a human approves them on the canvas.

Data backend is swappable via the HR_MCP_DATA_BACKEND env var:
  - "mock"  (default) -> realistic seed data, fully testable today.
  - "azure"           -> Azure SQL (structured data) + Azure AI Search (policy
                         RAG). Stubbed until credentials are provided; see
                         AzureBackend below.

Each tool returns a JSON object that includes a "_canvas" hint describing how
the frontend Side Canvas should render the result (module type + title). The
agent reads the data fields; the canvas reads "_canvas" + the payload.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastmcp import FastMCP

# The backend spawns this script via an absolute path and may use its own cwd,
# so make the sibling module importable regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_data import EMPLOYEES, POLICIES  # noqa: E402


mcp = FastMCP(name="hr-mcp")


# ---------------------------------------------------------------------------
# Data backends
# ---------------------------------------------------------------------------
class MockBackend:
    """Seed-data backend. Deterministic, offline, safe for demos/tests."""

    def find_employee(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        # Match on id, exact name, or name substring.
        for emp in EMPLOYEES:
            if q == emp["id"].lower() or q == emp["name"].lower():
                return emp
        for emp in EMPLOYEES:
            if q in emp["name"].lower() or q in emp["email"].lower():
                return emp
        return None

    def all_employees(self) -> list[dict[str, Any]]:
        return EMPLOYEES

    def search_policies(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return []
        terms = [t for t in q.replace("?", " ").split() if len(t) > 2]
        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in POLICIES:
            haystack = f"{doc['title']} {doc['section']} {doc['content']}".lower()
            score = sum(haystack.count(t) for t in terms)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:3]]


class AzureBackend(MockBackend):
    """Placeholder for the production backend.

    Intended wiring (Phase 2 completion, once creds exist):
      - find_employee / all_employees / *_balance -> parameterized, READ-ONLY
        queries against Azure SQL using AZURE_SQL_CONNECTION_STRING.
      - search_policies -> Azure AI Search (AZURE_SEARCH_ENDPOINT / _API_KEY /
        _INDEX) vector+keyword RAG over policy PDFs.

    Until implemented, we fall back to the seed data (inherited from
    MockBackend) so the pipeline stays functional, but log a clear warning.
    """

    def __init__(self) -> None:
        missing = [
            name
            for name in ("AZURE_SQL_CONNECTION_STRING", "AZURE_SEARCH_ENDPOINT")
            if not os.environ.get(name)
        ]
        if missing:
            print(
                f"[hr-mcp] WARNING: HR_MCP_DATA_BACKEND=azure but missing {missing}; "
                "falling back to seed data.",
                flush=True,
            )


def _backend() -> MockBackend:
    kind = (os.environ.get("HR_MCP_DATA_BACKEND") or "mock").lower()
    return AzureBackend() if kind == "azure" else MockBackend()


BACKEND = _backend()


def _not_found(query: str) -> dict[str, Any]:
    return {
        "found": False,
        "query": query,
        "message": (
            f"No employee matched '{query}'. Ask the HR user to confirm the "
            "full name or employee ID."
        ),
    }


# ---------------------------------------------------------------------------
# Tools (read-only)
# ---------------------------------------------------------------------------
@mcp.tool
def employee_lookup(name: str) -> dict[str, Any]:
    """Look up an employee's core profile by full name or employee ID.

    Returns identity, role, department, manager, location, start date, and
    compensation (salary, currency, pay frequency). Read-only. Use this for
    "who is X", "what team is X on", and "what is X's salary" questions from
    authorized HR users.
    """
    emp = BACKEND.find_employee(name)
    if not emp:
        return _not_found(name)
    return {
        "found": True,
        "employee": {
            "id": emp["id"],
            "name": emp["name"],
            "title": emp["title"],
            "department": emp["department"],
            "email": emp["email"],
            "manager": emp["manager"],
            "location": emp["location"],
            "start_date": emp["start_date"],
            "employment_type": emp["employment_type"],
            "salary": emp.get("salary"),
            "currency": emp.get("currency", "USD"),
            "pay_frequency": emp.get("pay_frequency", "annual"),
        },
        "_canvas": {"module": "employee_profile", "title": f"{emp['name']} — Profile"},
    }


@mcp.tool
def pto_balance(name: str) -> dict[str, Any]:
    """Get an employee's PTO (paid time off) accrual and current balance.

    Returns annual accrual, used, and remaining days. Read-only.
    """
    emp = BACKEND.find_employee(name)
    if not emp:
        return _not_found(name)
    pto = emp["pto"]
    return {
        "found": True,
        "employee": {"id": emp["id"], "name": emp["name"]},
        "pto": {
            "accrual_days_per_year": pto["accrual_days_per_year"],
            "used_days": pto["used_days"],
            "remaining_days": pto["remaining_days"],
            "as_of": pto["as_of"],
        },
        "_canvas": {"module": "pto", "title": f"{emp['name']} — PTO Balance"},
    }


@mcp.tool
def org_chart(name: str) -> dict[str, Any]:
    """Return an employee's place in the org: their manager, peers, and reports.

    Read-only. Use for org-structure and reporting-line questions.
    """
    emp = BACKEND.find_employee(name)
    if not emp:
        return _not_found(name)
    reports = [e for e in BACKEND.all_employees() if e["manager"] == emp["name"]]
    peers = [
        e
        for e in BACKEND.all_employees()
        if e["manager"] == emp["manager"] and e["id"] != emp["id"] and emp["manager"]
    ]
    return {
        "found": True,
        "employee": {"id": emp["id"], "name": emp["name"], "title": emp["title"]},
        "manager": emp["manager"],
        "peers": [{"name": e["name"], "title": e["title"]} for e in peers],
        "reports": [{"name": e["name"], "title": e["title"]} for e in reports],
        "_canvas": {"module": "org_chart", "title": f"{emp['name']} — Org Chart"},
    }


@mcp.tool
def benefits_lookup(name: str) -> dict[str, Any]:
    """Get an employee's benefits enrollment (medical, dental, retirement).

    Read-only. Use for benefits-enrollment and coverage questions.
    """
    emp = BACKEND.find_employee(name)
    if not emp:
        return _not_found(name)
    return {
        "found": True,
        "employee": {"id": emp["id"], "name": emp["name"]},
        "benefits": emp["benefits"],
        "_canvas": {"module": "benefits", "title": f"{emp['name']} — Benefits"},
    }


@mcp.tool
def policy_search(query: str) -> dict[str, Any]:
    """Search company HR policy documents (RAG) and return the top matches.

    Returns title, section, a snippet, and a source citation for each hit.
    Read-only. Use this to ground answers about policies, then CITE the source.
    """
    results = BACKEND.search_policies(query)
    return {
        "query": query,
        "results": [
            {
                "title": d["title"],
                "section": d["section"],
                "snippet": d["content"],
                "source": d["source"],
            }
            for d in results
        ],
        "_canvas": {"module": "policy", "title": "Policy Search"},
    }


if __name__ == "__main__":
    # stdio transport: the HRAgents backend spawns this process and speaks MCP
    # over stdin/stdout. No network port is opened.
    mcp.run(transport="stdio", show_banner=False)
