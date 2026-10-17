# Recent Bug Fixes (August 2026)

## 1. Next.js Hydration Crash (Missing Responses)

**Symptom:**
When a message was sent, the UI would go blank or fail to update with the incoming streaming responses. The browser console showed a Next.js Hydration Error (`A tree hydrated but some attributes of the server rendered HTML didn't match the client properties`). 

**Root Cause:**
The Radix UI `DropdownMenuTrigger` components within `chat_interface/components/app-sidebar.tsx` were dynamically generating random IDs during Server-Side Rendering (SSR) that didn't match the IDs generated on the client. This mismatch caused React's virtual DOM to crash, preventing any subsequent UI updates (like rendering the AI responses).

**Fix:**
Explicit, stable `id` properties were added to the `DropdownMenuTrigger` elements in the sidebar to ensure consistency between SSR and client renders:
- Added `id="sidebar-new-chat-trigger"` to the New Chat dropdown trigger.
- Added `id="sidebar-user-menu-trigger"` to the User Profile dropdown trigger.

## 2. Azure AI Search Startup Delay (~30s Buffering)

**Symptom:**
Sending a message in a new conversation would result in a ~30 second buffering delay before the agent began to process or respond to the request.

**Root Cause:**
The backend's MCP tool loader uses the `@ignitionai/azure-ai-search-mcp` package, which automatically connects to the configured Azure Search resource on startup to list available indexes as tools. The `.env` file had `AZURE_SEARCH_ENDPOINT` set to `https://closedai-dev-search.search.windows.net`, which was an invalid/placeholder hostname. The Node.js `getaddrinfo` DNS resolution for this nonexistent host takes approximately 30 seconds to time out, blocking the agent from starting its task.

**Fix:**
1. Queried the Azure CLI for the correct instance within the `Closed_AI` resource group, discovering it was actually named `closedai-search`.
2. Extracted the admin key for this valid instance.
3. Updated the `.env` file to use the correct endpoint and key, enabling the MCP server to connect instantly without timing out:
   - `AZURE_SEARCH_ENDPOINT=https://closedai-search.search.windows.net`
   - `AZURE_SEARCH_API_KEY=...`
   - `AZURE_SEARCH_INDEX=hr-policies`

## 3. Public/Marketplace Skills Silently Never Loaded

**Symptom:**
`load_public_skills()` always returned 0 skills and logged `Failed to load public skills from https://github.com/HRAgents/extensions: unsupported operand type(s) for /: 'bool' and 'str'`. Because the exception was caught and logged as a warning, this failure was invisible unless you were watching backend logs.

**Root Cause:**
`update_skills_repository()` in `HRAgent_Main/skills/utils.py` was declared to return `Path | None`, but its body did `return try_cached_clone_or_update(...)` directly. `try_cached_clone_or_update()` (in `HRAgent_Main/utilities/git.py`) actually returns a `bool` (clone/update succeeded or not), not a path. Downstream, `load_public_skills()` then tried `repo_path / "skills"` where `repo_path` was `True`, causing the `bool / str` TypeError.

**Fix:**
`update_skills_repository()` now returns the constructed `repo_path` on success and `None` on failure:
```python
succeeded = try_cached_clone_or_update(repo_url, repo_path, ref=ref, update=True)
return repo_path if succeeded else None
```

**Remaining issue (not fixed, needs a decision):** even with the type bug fixed, `https://github.com/HRAgents/extensions` (the hardcoded default public-skills repo, `PUBLIC_SKILLS_REPO` in `skills/skill.py`) returns a real `404` — the repo does not exist. This looks like a leftover placeholder from the OpenHands→HRAgents rename described in `agent_docs/context.md`. Public/marketplace-repo skill loading will keep failing (harmlessly, just 0 skills) until either a real skills repo is set there or that tier is intentionally left unused in favor of the plugin marketplace (`marketplaces/integrations/`), which is a separate, working mechanism.

## 4. Frontend Skills Management Page Is Disconnected Mock Data

**Symptom:**
The "Skills" page in the chat UI (left nav → Skills) always shows the same 8 hardcoded skills (Pull Request Reviewer, SSH Microagent, agent_memory, code-review, Meeting Summarizer, Data Analyst, Incident Responder, default-tools) regardless of what's actually installed/discoverable on the backend. Enabling/disabling a skill here has no effect on the real agent.

**Root Cause:**
`chat_interface/lib/skills-store.tsx` (`SkillsProvider`) initializes its React state from `INITIAL_SKILLS`, a hardcoded array in `chat_interface/components/pages/skills/skill-data.ts`, and never calls any backend endpoint. This is despite `chat_interface/app/api/skills/[...path]/route.ts` already existing as a correct, working proxy to the backend's real skills API (`POST /api/skills`, `GET /api/skills/installed`, `PATCH /api/skills/{name}/enabled`, etc. — see `HRAgent_Main/runtime/server/skills_router.py`). Nothing in the frontend calls `/api/skills` at all.

**Status: NOT FIXED.** This is a genuine disconnect matching the failure mode described in `agent_docs/context.md`, but rewiring it properly is a real feature change, not a plumbing fix: the mock `Skill` type carries fields the backend doesn't track at all (per-skill `activity` log, `runCount`, `successRate`, `avgDurationMs`, granular `permissions`). Wiring the page to live data either means dropping those fields from the UI or adding new backend telemetry — a scope decision, not a bug fix. Flagging for a decision before touching it.

**Important distinction:** this does *not* affect whether the agent can actually use skills in conversation — that path (`discover_profile_skills()` → `runtime/server/conversation_service.py` → agent context) is separate code and was verified working end-to-end (see `docs/project_audit.md`, Skills section).

## 5. Frontend Had No Working LLM Provider Configured

**Symptom:**
Every new chat conversation hung in "Executing" indefinitely. Backend logs showed repeated `litellm.ServiceUnavailableError: ... No available channel for model moonshotai/kimi-k3-free under group default (distributor)`.

**Root Cause:**
`chat_interface/app/api/chat/route.ts` defaults `LLM_PROVIDER` to `'tokenrouter'` and `TOKENROUTER_MODEL` to `'moonshotai/kimi-k3-free'` when no env vars are set. The repo-root `.env` *does* have a working provider configured (`LLM_PROVIDER=openai`, pointing at an Azure AI Foundry GPT-5.2 endpoint with a real key), but Next.js only auto-loads env files from its own directory (`chat_interface/`), not the repo root — so the frontend process never saw it and silently fell back to the unconfigured TokenRouter default.

**Fix:**
Created `chat_interface/.env.local` mirroring the working provider config from the repo-root `.env`:
```
LLM_PROVIDER=openai
OPENAI_API_KEY=<same key as repo-root .env>
OPENAI_MODEL=gpt-5.2
OPENAI_BASE_URL=https://sharedfoundry.services.ai.azure.com/openai/v1
```
Restarted the frontend (env changes require a restart, per `STARTUP.md`). Conversations now complete normally.

## 6. Marketplace Plugins Spawned Per-Conversation Can't Use Paths Relative to Their Own Vendored Location

**Symptom:** while building the new `cosmos-db` marketplace integration (see `docs/project_audit.md`), a launcher script (`server/run.sh`) that located the backend's Python venv via a path relative to its own location (`$(dirname "$0")/../../../..`) worked fine when tested by hand from the source tree, but failed with `backend venv python not found at /Users/anushkaboran/.HRAgent/.venv/bin/python` when actually invoked by the agent.

**Root Cause:** installing a plugin through the marketplace *copies* its files to `~/.HRAgent/plugins/installed/<name>/` (`HRAgent_Main/plugins/installed.py`) before the runtime ever spawns it. A script's path relative to its own post-install location has no relationship to the original repo checkout it was vendored from — `../../../..` from the installed copy lands in `~/.HRAgent/`, not the repo.

**Fix:** `server/run.sh` now resolves the venv Python via an overridable env var with a hardcoded absolute default (`COSMOS_MCP_VENV_PYTHON`, defaulting to this checkout's `HRAgent_Main/.venv/bin/python`) — the same hardcoded-with-env-override pattern already used by `HR_MCP_PYTHON` in `chat_interface/app/api/chat/route.ts` for exactly this reason. Worth remembering for any future plugin that needs to locate this repo's venv or other fixed local resources: don't derive it from the plugin's own path once installed.

## 7. `onboarding_checklists` Not Actually Linked to `employees` by ID (data issue, not code)

**Symptom:** while testing the first real HR skill (`hr-onboarding.md`, see `docs/project_audit.md`), a live-chat request to onboard `emp-0001` (a real employee, confirmed to exist — "Joseph Johnson") correctly found no matching onboarding checklist.

**Root Cause:** this is a Cosmos DB seed-data issue, not an integration bug. The `onboarding_checklists` container's `employee_id` field holds a self-referential UUID matching the record's own `id` (e.g. `employee_id: "b5a5f9c7-4b55-41b9-97ec-dfa9515198b7"`, `employee_name: "Areef Shaik"`) — not the `employees` container's `emp-XXXX` ID scheme. The two containers were seeded independently and don't actually cross-reference real employee records.

**Status: NOT FIXED — flagging for a decision, not silently patching seed data.** Not fixed here because it's unclear whether the intended fix is re-seeding `onboarding_checklists` with real `emp-XXXX` IDs, or whether checklists are meant to reference applicants/new-hires who aren't in `employees` yet (plausible for an *onboarding* checklist — new hires may not have an employee record yet). Don't assume which without checking intent. Any future onboarding-related skill work should account for this — `hr-onboarding.md` already does, by reporting "couldn't find a match" rather than guessing.

## 8. Azure AI Search Marketplace Config Had Completely Wrong Tool Names (major)

**Context:** this was found doing a rigorous, UI-driven re-test of every integration after being told that prior claims of "tested and working" weren't trustworthy enough — testing each MCP tool in isolation had missed this.

**Symptom:** asking the live chat "Using the azure-ai-search tool, list the available indexes" produced: *"I can't do that here: there is no 'azure-ai-search' tool/integration available in this workspace... listing Azure AI Search indexes is also outside my HR copilot scope."* — despite `docs/project_audit.md` previously documenting this integration as "confirmed working end-to-end."

**Two separate root causes, both real:**

1. **Never installed on this machine.** `~/.HRAgent/plugins/installed/` (a machine-local directory, not part of the git repo) had `cosmos-db` and `document-editor` (installed earlier this session) but no `azure-ai-search` — the original "confirmed working" testing happened on a different machine/session, and that installed state was never something a fresh clone could inherit. This is exactly the class of problem the user was worried about: a thing genuinely worked once, got documented as done, and then silently stopped being true for anyone else running the repo.
2. **The tool names in `plugin.json`/`marketplaces/default.json` were entirely fictional.** They listed `query`, `list_indexes`, `get_index`. The real MCP server (`azure-ai-search-mcp`, and its current successor `@ignitionai/azure-ai-search-mcp`) exposes a completely different, hyphenated set: `search-documents`, `get-document`, `suggest`, `autocomplete`, `list-indexes`, `get-index-schema`, `get-index-statistics`, `upload-documents`, `merge-documents`, `delete-documents`, `vector-search`, `hybrid-search`, `semantic-search` — confirmed directly by running `npx -y @ignitionai/azure-ai-search-mcp` and calling `tools/list`. None of the three originally-documented names exist on the real server. It's unclear whether this was ever actually verified against the real package, or written from assumption.

**Fix:**
- Installed the plugin on this machine via the real `/api/plugins/install` endpoint (not hand-copied).
- Rewrote the `tools` arrays in `HRAgent_Main/marketplaces/integrations/azure-ai-search/plugin.json` and `HRAgent_Main/marketplaces/default.json` to the actual, verified tool names above.
- Updated `.mcp.json`'s `npx` package reference from the deprecated `azure-ai-search-mcp` to its actively-maintained successor `@ignitionai/azure-ai-search-mcp` (the old package's own install banner announces the move).
- Re-tested through the live chat UI: "Using the azure-ai-search tool, list the available indexes" now correctly calls `list-indexes` and returns the real index, `company-policies`.

## 9. Azure AI Search Index Name in `.env` Didn't Match the Real Index

**Symptom:** found while re-verifying bug #8 above — `.env`'s `AZURE_SEARCH_INDEX=hr-policies` doesn't match the Azure Search service's actual index, which is named `company-policies` (confirmed via `list-indexes` against the live service).

**Fix:** updated `.env` to `AZURE_SEARCH_INDEX=company-policies`.

**Separately found, not fixed — a real data-consistency question, not a code bug:** the `company-policies` search index's PTO policy document says *"Full-time employees accrue 15 days of PTO per year"*, while the PTO policy PDF in Azure Blob Storage (`closedaidevstg/onboarding-forms/policies/PTO_Policy.pdf`, see item 6 in `docs/project_audit.md`) says *"twenty (20) days."* Two different HR data sources disagree about a real policy number. Not resolved here — don't assume which is authoritative without asking.

## 10. Two Real Chat UI Bugs Found During Rigorous End-to-End Testing

Found while deliberately testing through the actual UI with screenshots at every step (not just reading final text), per explicit instruction to stop trusting "the implementation exists" as equivalent to "it works in the UI."

**10a. Recurring "Maximum update depth exceeded" / minified React error #185 (Fixed once before, NOT actually fully fixed).**
`docs/bug_fixes.md` #1 previously documented a React infinite-render fix (module-level `MARKDOWN_COMPONENTS` in `chat_interface/components/chat-conversation.tsx`). That fix is still in place and correct, but it was evidently not the only cause: this session reproduced the same class of error repeatedly — both in `next dev` and in a real **production build** (`next build && next start`, ruling out a dev-only Fast Refresh artifact) — when switching into a conversation with existing messages, and again right as a Side Canvas artifact populated. The app visibly self-recovers each time (React aborts the runaway loop and the UI ends up correct), so it isn't fully blocking, but it is a real, currently-unfixed bug, and a plausible source of exactly the kind of intermittent visible glitches described secondhand ("sometimes it opens up the side canvas a lot of times, sometimes it does this, it does that").
**Status: NOT FIXED.** Root-caused as far as this environment's tooling allows: the error arrives via the browser's low-level exception reporting (not a page-level `console.error` or `window.onerror` call our instrumentation could intercept — confirmed by installing both kinds of hooks immediately before triggering it and getting nothing back both times), and production source maps weren't available to decode the minified stack. Reviewed every component with `useEffect` in the conversation-switch and Side-Canvas render path (`chat-conversation.tsx`, `agent-activity-feed.tsx`, `agent-runtime.tsx`, `chat-composer.tsx`, `side-canvas.tsx`, `canvas-store.ts`, `agent-execution-panel.tsx`) and found no obviously-unguarded `setState` call — all the `useEffect` dependency arrays and zustand `set()` calls inspected look correctly guarded. Needs a real browser's DevTools (React DevTools Profiler + non-minified source maps) to pin down; this environment's automated browser tooling could not extract more than "it's real, it's reproducible, here's roughly when it fires."

**10b. Starting a New Chat does not close/reset the Side Canvas or Activity panel.**
Reproduced 3 times: after finishing a conversation that populated the Side Canvas and/or the right-hand Activity/execution panel, clicking "New Chat" leaves both panels open showing the *previous* conversation's stale data (e.g. a "Finished 0:25" execution summary from the last chat, visible in a brand-new, empty chat). The user has to manually close them. Also observed: clicking "New Chat" while already on an empty, message-less "New Chat" creates *another* empty chat instead of reusing the current one — the sidebar accumulated 5 duplicate "New Chat" entries during this testing session.
**Status: NOT FIXED** — noted here rather than fixed blind, since the correct behavior (auto-close canvas/activity on new chat? reuse an empty draft chat instead of duplicating?) is a product decision, not just a bug fix, and this session's time went to the higher-priority Azure AI Search fix (#8) instead.

## 11. Side Canvas Now Shows Marketplace MCP Tool Results (Cosmos DB, Document Editor, Azure AI Search)

**Symptom:** the Side Canvas is the user-visible "did this actually do something" view the user explicitly asked for, especially for the document-editor MCP. Before this fix, it only ever showed data from 6 hardcoded `hr-mcp` tool names (`employee_lookup`, `pto_balance`, `org_chart`, `benefits_lookup`, `policy_search`, `invoke_skill`) — every marketplace-installed MCP tool (all of Cosmos DB's, all of document-editor's, all of Azure AI Search's) silently never appeared there, even while actively running and returning real data. The panel would just say "Nothing to review yet" throughout an entire successful tool-using conversation.

**Root Cause:** `chat_interface/lib/chat-store.ts`'s `ingestCanvas()` gated Side Canvas population on `CANVAS_TOOLS = new Set(Object.keys(TOOL_LABELS))`, and `TOOL_LABELS` only ever listed the 6 hr-mcp tools. There was already a generic JSON fallback renderer (`JsonFallback` in `chat_interface/components/canvas-modules.tsx`) wired up and ready to use — it just never received any data for non-hr-mcp tools.

**Fix:** added `MCP_CANVAS_TOOL_LABELS`, listing every tool from the `cosmos-db`, `document-editor`, and `azure-ai-search` marketplace integrations, and included them in `CANVAS_TOOLS` so their results route through the existing JSON fallback. Also fixed `tryParseJsonObject()` to handle top-level JSON **arrays** (e.g. `office_list_pdf_fields`'s response), not just objects — the old bracket-extraction logic only looked for `{`/`}`.

**Verified live:** asking the chat to list an I-9's PDF form fields now opens a "Listing PDF form fields" Side Canvas panel showing the real field data, with a "Read-only view from office_list_pdf_fields" footer — exactly the visibility the user asked for. Plain-string tool results (e.g. `count_documents`, which returns a sentence like "Container 'policies' contains 5 documents" rather than JSON) still don't populate the canvas, since there's no structured data to show — this is an honest limitation of the generic-fallback approach, not a bug.
