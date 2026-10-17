# Gurt Demo Scenario: 80-Person AI Workshop

Demonstrates the connected workflow across all three domains — outreach, vendors, and logistics —
with a persistence check across a backend restart.

> **Event:** DubHacks Workshop 2026, Nov 15, Gates Hall 106, ~80 attendees, AI for Social Good theme.

---

## Step-by-step conversation

### 1. Brief the agent

> **Organizer:** "Yo Gurt, we're organizing an 80-person AI workshop on Nov 15 at UW Gates Hall.
> Theme is AI for Social Good. Budget is $5k. We need a speaker, a sponsor, food, and badges."

**Expected Gurt behavior:**
- Greets warmly in 1–2 sentences.
- Reads `event_brief.md` from the workspace via `read_file`.
- Calls `event_lookup()` to confirm stored event context.
- Returns a structured checklist of what's needed (speaker, sponsor, food, badges) with quick-action suggestions.
- Canvas: `event_profile` module showing the event brief.

---

### 2. Research speakers

> **Organizer:** "Find me speaker candidates for the AI for Social Good theme."

**Expected Gurt behavior:**
- Calls `speaker_lookup("")` to list all candidates.
- Returns a shortlist of 3 with fit notes:
  - spk-001 Dr. Alicia Chen (Google DeepMind) — *prospecting*, NeurIPS keynote track record
  - spk-002 Marcus Rivera (CivicTech) — *contacted*, civic AI angle
  - spk-003 Prof. Sara Kim (UW) — **confirmed**, local, ML fairness
- Canvas: `speaker_profile` module with the full shortlist.
- Flags that Sara Kim is already confirmed and suggests confirming the others next.

---

### 3. Draft speaker outreach

> **Organizer:** "Draft an outreach email to Dr. Alicia Chen."

**Expected Gurt behavior:**
- Calls `speaker_lookup("Dr. Alicia Chen")` to get contact details.
- Calls `event_lookup()` for event context.
- Calls `send_email` client tool with:
  - `to`: achen@example.com
  - `subject`: "Speaker Invitation — DubHacks Workshop 2026 (AI for Social Good)"
  - `body`: Complete, ready-to-send draft referencing the event theme, date, venue, and expected audience.
- **HITL card** appears in chat: "Approve & Send" — nothing is sent until organizer clicks it.
- Canvas: Email draft rendered in Side Canvas.
- Gurt tells organizer it's ready for review, does NOT claim it was sent.

---

### 4. Find catering vendors

> **Organizer:** "Find catering vendors under $15 per head."

**Expected Gurt behavior:**
- Calls `vendor_lookup("food")` to get all food vendors.
- Returns comparison:
  - vnd-001 Campus Catering Co. — $15/head ($1,200 total), vegan/GF available
  - vnd-003 Taste of Seoul — $12/head ($960 total), vegan/GF/Halal
- Canvas: `vendor_profile` module with side-by-side quote comparison.
- Recommends Taste of Seoul as the better value; notes the $240 budget difference.

---

### 5. Find badge vendor

> **Organizer:** "What about badges?"

**Expected Gurt behavior:**
- Calls `vendor_lookup("badges")`.
- Returns PrintFast UW: $3/badge = $240 for 80, 4-day lead time, includes lanyards.
- Notes the Nov 11 ordering deadline for Nov 15 delivery.

---

### 6. Find sponsors

> **Organizer:** "Who are our sponsor prospects?"

**Expected Gurt behavior:**
- Calls `sponsor_lookup("")` to list all sponsors.
- Returns:
  - spo-001 Acme AI Labs — gold ($2,000), prospecting, prior DubHacks sponsor
  - spo-002 Northwest Tech Fund — silver ($1,000), contacted, 30-day approval cycle
- Flags that Northwest Tech Fund's 30-day timeline means contact by Oct 18 at latest.
- Canvas: `sponsor_profile` module with pipeline view.

---

### 7. Draft sponsor outreach

> **Organizer:** "Draft a sponsor email to Acme AI Labs."

**Expected Gurt behavior:**
- Calls `sponsor_lookup("Acme AI Labs")`.
- Calls `send_email` client tool with a complete gold-tier sponsorship pitch.
- HITL card appears. Canvas shows draft.

---

### 8. Build the logistics task list

> **Organizer:** "Build the full task list with owners and deadlines."

**Expected Gurt behavior:**
- Calls `task_list("", "")` to fetch all tasks.
- Renders the 7-task board with owners, due dates, and dependency chains.
- Highlights the critical path: tsk-001 + tsk-002 → tsk-004 → tsk-007.
- Canvas: `task_board` module showing all tasks.

---

### 9. Persistence check (restart the backend)

**Test:** Restart `HRAgent_Main` (`uv run server`, or `start_server.ps1`). Open a new chat.

> **Organizer:** "What's the status of our workshop?"

**Expected Gurt behavior:**
- Calls `event_lookup()` — event record returns from seed data / Cosmos.
- Reads `event_brief.md` from workspace — file persists on disk.
- Returns a status summary with outstanding tasks and pending vendor/speaker decisions.
- **This proves records survive restart** — the workspace file and MCP seed data are durable.

---

## Tool coverage matrix

| Scenario step | Tools called | Canvas module |
|---|---|---|
| Brief | `event_lookup`, `read_file` | `event_profile` |
| Speaker research | `speaker_lookup("")` | `speaker_profile` |
| Speaker outreach | `speaker_lookup`, `send_email` | Email draft |
| Catering vendors | `vendor_lookup("food")` | `vendor_profile` |
| Badge vendor | `vendor_lookup("badges")` | `vendor_profile` |
| Sponsors | `sponsor_lookup("")` | `sponsor_profile` |
| Sponsor outreach | `sponsor_lookup`, `send_email` | Email draft |
| Task list | `task_list("", "")` | `task_board` |
| Restart check | `event_lookup`, `read_file` | `event_profile` |

---

## Running the demo

```powershell
# Terminal 1 — backend
cd ClosedAI-main\HRAgent_Main
uv run python -m runtime.server.server

# Terminal 2 — frontend
cd ClosedAI-main\chat_interface
npm run dev
```

Open http://localhost:3000 and start with: **"Yo Gurt, we're organizing an 80-person AI workshop..."**
