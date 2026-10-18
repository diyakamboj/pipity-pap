# Gurt — Event Operations Agent

Autonomous, grounded event operations assistant built for hackathons and workshops (DubHacks 2026).
Gurt independently coordinates **Event Brief & Constraints**, **Outreach** (speakers & sponsors), **Vendors & Needs Discovery** (catering, badges, AV), **Logistics** (run-of-show schedule & tasks), and **Supported PDF Form Filling**.

---

## 1. Architectural Independence & Provenance Boundary

This application is built **independently from scratch** in a clean, self-contained directory (`gurt/`).
It strictly respects the owner's privacy boundary:
- The owner's original repository (`ClosedAI` / `HRAgent_Main`) remains private and untouched.
- Custom MCP servers with unclear permission (`office-oxide-mcp`, `hr_mcp`) are left out of Gurt. Instead, Gurt uses standard public open-source libraries (`pypdf`, `reportlab`) and a native SQLite persistent store (`gurt_events.db`).
- Private infrastructure (OpenHands-derived conversation FSM, delegate subagent engines, React side-canvas) is **not reused**. Gurt implements its own single-agent orchestrator with bounded tool adapters, an event isolation layer, and a vanilla HTML5/CSS3/ES6 responsive web interface.

### Attribution of Approved Portable Skill Concepts
- **Web Research Guidance (`gurt/skills/web_research.py`)**: Attributed to the research protocol concept from ClosedAI's `web-researcher.md`.
- **Task & Chaos Floor Triage (`gurt/skills/task_logger.py`)**: Attributed to the incident logging concept from ClosedAI's `.agents/skills/github-issue-creator/SKILL.md`.
- **Outreach Safety & Human-in-the-Loop (`gurt/skills/outreach_rules.py`)**: Attributed to the HITL safety pattern ensuring consequential actions require explicit organizer approval.

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
- `GEMINI_API_KEY`: Google Gemini API key (defaults to `gemini-3.8-flash` or `gemini-3-flash-preview`)
- `TAVILY_API_KEY`: Tavily web search API key (falls back to labeled synthetic fixtures if unconfigured)
- `RESEND_API_KEY`: Resend API key for approved email dispatches (falls back to recorded sandbox delivery)
- `PORT`: Server port (default `8000`)

### Run Verification Test Suite
```bash
python test_suite.py
```
Executes all 10 automated end-to-end verification checks across an 80-person synthetic workshop scenario.

### Launch the Application
```bash
python run.py
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 3. Product Capabilities & Status

| Domain | Capability | File / Adapter | Status |
| :--- | :--- | :--- | :--- |
| **Event Brief** | Create, edit in-place, and reload event brief (headcount, budget, goals, dietary specs, AV specs) | `gurt/tools/event_tools.py`, `gurt/db.py` | **Working & Verified** |
| **Outreach** | Speaker & sponsor database lookup (`lookup_speakers`, `lookup_sponsors`) | `gurt/tools/event_tools.py` | **Working & Verified** |
| **Outreach** | Candidate research via real-time web search (`web_research`) | `gurt/tools/research_tool.py` | **Working (Tavily / Fixtures)** |
| **Outreach** | Candidate evidence saving to shortlist & pipeline (`propose_speaker`, `save_sponsor_candidate`) | `gurt/tools/event_tools.py` | **Working & Verified** |
| **Outreach** | Draft invite creation with duplicate prevention (`draft_outreach`, `draft_slack_message`) | `gurt/tools/outreach_tools.py` | **Working & Verified** |
| **Outreach** | Pre-approval draft editing (`tool_update_draft`, `PATCH /api/actions/{id}`) | `gurt/tools/outreach_tools.py` | **Working & Verified** |
| **Action Center** | Consequential action approval & dispatch (`execute_approved_action`) | `gurt/tools/outreach_tools.py` | **Working (Resend / Sandbox)** |
| **Vendors** | Requirements discovery & missing unknowns tracking (`save_vendor_requirement`) | `gurt/tools/event_tools.py` | **Working & Verified** |
| **Vendors** | Supplier quote comparison per head against $2,500 budget (`lookup_vendors`, `add_vendor_quote`) | `gurt/tools/event_tools.py` | **Working & Verified** |
| **Logistics** | Run-of-show schedule synthesis linking setup, keynote, tracks, lunch, and teardown | `gurt/tools/event_tools.py` | **Working & Verified** |
| **Logistics** | Logistics task DAG with dependencies & status cycling (`create_task`, `update_task_status`) | `gurt/tools/event_tools.py` | **Working & Verified** |
| **PDF Workflow** | AcroForm template inspection & fillable field extraction (`inspect_template_fields`) | `gurt/tools/pdf_tools.py` | **Working & Verified** |
| **PDF Workflow** | Map saved event facts, isolate unresolved answers, produce downloadable draft, preserve original | `gurt/tools/pdf_tools.py` | **Working & Verified** |
| **PDF Workflow** | Decoupled signing & submission safety guard | `gurt/tools/pdf_tools.py` | **Working & Verified** |

---

## 4. Standout Workflow: Supported PDF Form Filling

Gurt features an independent, native PDF form filling engine powered by `pypdf` and `reportlab`:
1. **Template Inspection:** Analyzes `UW_HUB_Event_Facility_Booking_Contract.pdf` and extracts 16 AcroForm fields.
2. **Fact Mapping:** Maps 8 known facts from persistent records:
   - Event Title -> `event_name`
   - Date & Time -> `event_date`
   - Reserved Venue -> `event_location`
   - Expected Attendance -> `expected_attendance` (80)
   - Lead Organizer -> `organizer_name` & `organizer_email`
   - Catering Supplier -> `catering_vendor` & `catering_total_cost` ($1,080.00)
   - Dietary Specifications -> `dietary_requirements`
   - AV Tech Specifications -> `av_equipment_requested`
3. **Missing / Unresolved Answers:** Identifies unresolved items requiring human review:
   - On-site emergency phone number
   - UW Budget Code / Workday Index
   - Event Liability Insurance Certificate Number
4. **Preservation & Decoupling:** Generates a new downloadable draft (`doc-hub-booking-dubhacks-2026_draft.pdf`), leaves the original template completely unmodified, and marks legal signature fields as unsigned and unsubmitted pending human signoff.

---

## 5. Human-In-The-Loop Safety Boundary

Gurt enforces that **no email is ever sent, no contract is ever submitted, and no budget is committed automatically**:
- Outreach drafts are queued in the **Action Center** in `pending_approval` state.
- Organizers can edit subjects and message bodies prior to approval.
- One-click approval executes through configured providers and locks the action to prevent double execution.

---

## 6. Modern Dashboard & Multi-Session Experience

Gurt provides an independent, clean user experience inspired by top modern AI interfaces:
- **Collapsible Chat Sidebar:** Create, switch between, and delete multiple conversation threads with distinct focus areas (e.g. "Speaker Outreach", "Catering & Budget").
- **Persistent Messages (SQLite):** Every user turn, model response, tool execution tag, and model identifier is stored in `gurt_events.db` and reloaded automatically when toggling between threads.
- **Model Selector Dropdown:** Seamlessly switch between **Gemini 3.8 Flash (Default)**, **Gemini 3.0 Flash Preview**, **Grok 2 (xAI)**, and the offline **Dynamic Semantic Engine** directly from the header without server restarts.
- **Persistent Organizer Memory:** Store custom rules, dietary constraints, and preferences (e.g., *"Always order 20% certified vegan boxed meals"*). Stored memories are dynamically injected into Gurt's system instructions and persist across all chats.

