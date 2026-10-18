# Gurt — Event Operations Agent

Autonomous, grounded operations assistant built for hackathons and workshops (DubHacks 2026).
Gurt coordinates **Outreach** (speakers & sponsors), **Vendors** (catering & badges), and **Logistics** (run-of-show & floor tasks).

---

## 1. Architectural Independence & Provenance

This application is built **independently from scratch** in a fresh repository layout.
It preserves the owner's original repository (`ClosedAI`) privately without copying its internal orchestration engine, conversation state machine, proprietary MCP implementations, or private UI canvas.

### Attribution of Reused Skill Concepts
- **Web Research Guidance (`gurt/skills/web_research.py`)**: Attributed to the research protocol concept from ClosedAI's `web-researcher.md`.
- **Task & Incident Logging (`gurt/skills/task_logger.py`)**: Attributed to the chaos triage concept from ClosedAI's `github-issue-creator/SKILL.md`.
- **Outreach Safety & Human-in-the-Loop (`gurt/skills/outreach_rules.py`)**: Enforces that draft proposals are never represented as sent messages.

---

## 2. Quick Setup & Run

### Prerequisites
- Python 3.11+
- Virtual environment with dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Configuration
Copy `.env.example` to `.env` and fill in your keys:
- `GEMINI_API_KEY`: Google Gemini API key (active: `gemini-3.8-flash`)
- `TAVILY_API_KEY`: Tavily search API key
- `RESEND_API_KEY`: Resend API key for approved email dispatches
- `SUPABASE_URL` / `SUPABASE_KEY`: Supabase Postgres connection

### Run Gurt
```bash
python run.py
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 3. Product Capabilities

| Domain | Capability | Status |
| :--- | :--- | :--- |
| **Outreach** | Speaker & sponsor database lookup (`lookup_speakers`) | **Working & Grounded** |
| **Outreach** | Web research on candidate bios and talk topics (`web_research`) | **Working (Tavily + Fixtures)** |
| **Outreach** | Draft invite creation with HITL signoff (`draft_outreach`) | **Working (Action Center)** |
| **Outreach** | One-click approved email dispatch (`execute_approved_action`) | **Working (Resend API)** |
| **Vendors** | Vendor quote comparison per head vs budget (`lookup_vendors`) | **Working & Grounded** |
| **Logistics** | Run-of-show checklist & dependency tracking (`lookup_tasks`) | **Working & Grounded** |
| **Logistics** | Floor task logging (`create_task`) | **Working & Grounded** |
| **Form Filling** | PDF permit/application filling | *Pending clarification on external PDF tool* |

---

## 4. Human-In-The-Loop Safety
Gurt guarantees that **no email is ever sent and no budget is committed automatically**.
All outreach messages appear in the **Action Center** with full preview and require an organizer to click **Approve & Send**.
