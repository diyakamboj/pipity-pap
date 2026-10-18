# Gurt — Reuse Boundaries Audit

**Date:** October 17, 2026  
**Project:** Gurt — Event Operations Agent (DubHacks)  
**Source Repository:** `ClosedAI` (HR-agent / OpenHands-derived copilot)  
**Owner Guideline:** Reuse of skill instructions approved; underlying application infrastructure remains private. Gurt must be constructed independently in a clean directory.

---

## 1. Classification of Components

| Component / Asset | Source Path in `ClosedAI` | Classification | Gurt Strategy & Attribution |
| :--- | :--- | :--- | :--- |
| **Skill Instructions: Web Research** | `HRAgent_Main/tools/preset/subagents/web_researcher.md` | **Portable Skill Instruction** | **Reuse Prompt Concept** with attribution. Teaches the agent to query Tavily, cross-reference sources, and return structured research citations. |
| **Skill Instructions: Task / Chaos Logger** | `.agents/skills/github-issue-creator/SKILL.md` | **Portable Skill Instruction** | **Reuse Prompt Concept** with attribution. Adapts the pattern of taking chaotic floor messages and extracting structured tasks, zones, and severity. |
| **Skill Instructions: Multi-Step Planning** | `HRAgent_Main/tools/preset/planning.py` | **Portable Skill Instruction** | **Reuse Architectural Pattern**. Agent builds an explicit 4-stage plan (Objective, Constraints, Actions, Validation). |
| **Skill Instructions: Continual Learning** | `.agents/skills/continual-learning/SKILL.md` | **Portable Skill Instruction** | **Reuse Guidance**. Incorporate feedback loops for organizer preferences. |
| **Public Dependencies** | `pydantic`, `fastapi`, `uvicorn`, `litellm`, `tavily`, `resend`, `supabase`, `sqlite3` | **Public Third-Party Dependencies** | **Install Independently** via standard package managers (`pip` / `npm`). |
| **Document Editor MCP (`office-oxide-mcp`)** | `marketplaces/integrations/document-editor` | **Custom / Ambiguous Implementation** | **Pending Clarification — Do Not Copy**. Fills AcroForm PDFs using custom Rust binary. Gurt will provide structured form data schemas and use synthetic / open-source PDF fill tools if needed, leaving binary integration pending. |
| **Custom HR MCP (`hr_mcp`)** | `ClosedAI-main/hr_mcp/server.py` | **Custom MCP Implementation** | **Pending Clarification — Do Not Copy**. Replaced in Gurt by an independent, native Event Records database. |
| **Orchestration & Conversation Loop** | `HRAgent_Main/core/conversation/impl/local_conversation.py` | **Private Infrastructure** | **DO NOT REUSE**. Gurt implements its own clean, deterministic single-agent loop. |
| **Subagent Delegation Engine** | `HRAgent_Main/tools/delegate/impl.py` | **Private Infrastructure** | **DO NOT REUSE**. Gurt uses one orchestrating agent with bounded tool adapters. |
| **Next.js Frontend & Generative UI** | `chat_interface/` & `ui-block-canvas.tsx` | **Private Infrastructure** | **DO NOT REUSE**. Gurt implements an independent, lightweight, modern web interface. |
| **HITL Approval Engine** | `tools/client_tool.py`, `hr-actions.ts` | **Private Infrastructure** | **DO NOT REUSE**. Gurt implements an independent, backend-controlled Action Approval model (draft -> review -> approve/reject -> execute). |
| **Two-Tier Memory Loader** | `HRAgent_Main/memory/memory.py` | **Private Infrastructure** | **DO NOT REUSE**. Gurt uses direct database persistence for event constraints. |
| **Marketplace & Plugin Dynamic Loader** | `HRAgent_Main/marketplaces/` | **Private Infrastructure** | **DO NOT REUSE**. Gurt statically wires explicit, bounded tool adapters. |

---

## 2. Dependencies of Reusable Skills

1. **Web Research (`web-researcher`)**:
   - *Requires:* Web search API (`TAVILY_API_KEY`).
   - *Original Dependency:* Ran inside `DelegateExecutor` with `tavily-mcp` subprocess.
   - *Gurt Independent Implementation:* Direct Python tool adapter calling Tavily REST API with bounded query parameters and structured JSON output.

2. **Incident & Task Logger (`github-issue-creator`)**:
   - *Requires:* Persistent storage for tasks.
   - *Original Dependency:* GitHub API MCP.
   - *Gurt Independent Implementation:* Native SQLite/Supabase `tasks` table with severity, owner, status, and zone attributes.

3. **Event Planning & Outreach**:
   - *Requires:* Email drafting and sending.
   - *Original Dependency:* Custom ClientTools WebSocket confirmation.
   - *Gurt Independent Implementation:* Native `draft_outreach` tool returning an action proposal; backend holds execution until user approves via `/api/actions/{id}/approve`. Upon approval, executed via Resend API.

---

## 3. What Gurt Implements Independently

- **Unified Event Store**: SQLite persistent database (`gurt_events.db`) with schemas for `events`, `speakers`, `vendors`, `sponsors`, `tasks`, and `action_proposals`.
- **Bounded Tool Adapters**:
  - `tavily_search`: Real-time web research on potential speakers, sponsors, and suppliers.
  - `speaker_lookup` & `speaker_propose`: Query or record speaker availability and talk proposals.
  - `vendor_lookup` & `vendor_quote_compare`: Query and evaluate vendor bids (price per head, dietary, minimums).
  - `task_create` & `task_list`: Operations and logistics task DAG.
  - `draft_outreach`: Generates outreach drafts marked `status="pending_approval"`.
  - `execute_approved_action`: Backend endpoint executing approved actions (e.g., sending emails via Resend).
- **Orchestrator**: Single Python orchestrating agent with clear system prompt, bounded function calling, and structured outputs.
- **Frontend Interface**: Clean, responsive single-page web app with:
  - Interactive Chat with Gurt
  - Real-time Event Operations Dashboard (Speakers, Vendors, Tasks)
  - Action Approval Center (Review drafts, see quote comparisons, one-click Approve & Execute)
