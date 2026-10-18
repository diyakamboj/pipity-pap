# Provider Status and Activity Logging Implementation

## Scope

This note describes the Gurt backend reliability and operational activity changes. The implementation preserves the existing chat response fields and reuses the SQLite `audit_logs` table for activity rather than introducing a new persistence model or migration.

The main areas are:

- `gurt/orchestrator.py`: explicit provider/execution metadata and tool outcome classification.
- `gurt/api/server.py`: run lifecycle logging, safe Activity API projection, and `run_id` on chat responses.
- `gurt/tools/outreach_tools.py`: activity for approved-action execution outcomes.
- `test_suite.py`: provider, persistence, outcome, privacy, and event-isolation regressions using temporary storage.
- `README.md`: endpoint contract for the frontend integration.

## Provider Execution Metadata

`run_orchestrator()` annotates all of its return paths with `provider_status` and `execution_mode`. Existing fields (`text`, `tool_calls`, and `model_used`) are retained; the chat API continues to add `conversation_id` and now also adds `run_id`.

The orchestrator distinguishes these outcomes:

| Path | `provider_status` | `execution_mode` |
| --- | --- | --- |
| Gemini response accepted and parsed | `provider_success` | `gemini` |
| Grok response accepted and parsed | `provider_success` | `grok` |
| Requested provider fails or has unusable credentials, then local fallback responds | `provider_failure` | `semantic_fallback` |
| Local semantic engine explicitly selected | `not_used` | `semantic_fallback` |

A local fallback response is never labeled provider success. Gemini tries its configured model and supported alternatives, then returns semantic fallback if no usable response is obtained. A requested Grok call does not silently switch to Gemini: missing credentials, a failed request, or a malformed response returns the local fallback with provider failure metadata.

Tool calls are normalized before being returned. Explicit `error` or `exception` fields map to `failure`; recognized pending, execution, failure, and simulation statuses are retained; recognized creation/update statuses map to `success`; an `action_id` maps to `pending_approval`; and explicit simulation flags map to `simulated`. If none of those rules applies, unrecognized status strings and outputs without an explicit outcome map to `unknown`, rather than being presumed successful. Known adapter outcomes such as `no_quotes_found`, `switched`, `updated_shortlist`, and `commitment_recorded` are explicitly classified as successful tool execution. A successful tool invocation is not evidence that an external message was delivered.

## Persistence Reuse

The existing `audit_logs` table is defined in `gurt/db.py` and stores:

- `id`
- `event_id`
- `actor_id`
- `action`
- `target_type`
- `target_id`
- `details_json`
- `created_at`

`log_audit_event()` writes each entry and `get_audit_logs()` selects rows for one exact `event_id`, ordered by `created_at DESC`. Activity records place run/status/summary/affected IDs in `details_json`; no schema change is required. Existing logistics writers continue using the same table and the legacy audit endpoint is unchanged.

## Chat Run Lifecycle

The `/api/chat` route creates a `run_id` after saving the incoming user message and before calling `run_orchestrator()`.

1. It writes an `agent_run` activity record with status `starting`.
2. If the orchestrator raises, it writes a `failed` record and re-raises the exception so the HTTP error behavior remains intact.
3. On a returned response, it records each structured tool call separately.
4. It writes an `agent_run` record with status `succeeded`, including the execution mode and provider status in the internal audit details.
5. It saves and returns the assistant message using the existing message persistence path.

The failure summary is fixed text. The exception message, prompt, request headers, and credentials are not copied into the activity summary. The internal failure details contain only the exception type; the public Activity response does not expose internal details JSON.

## Tool and Approval Outcomes

For chat-dispatched tools, the API records one activity entry per returned tool call. The action is the sanitized tool name. The status is inferred from the structured tool result, not from the generated assistant text. A discovered `action_id` is included among `affected_record_ids` and the activity status remains `pending_approval` until a separate approval action occurs.

`execute_approved_action()` logs direct approval results after updating the action proposal:

- Sandbox or outbox results (`recorded_delivery`, `delivered_to_outbox`) become `simulated` with a summary stating delivery is unverified.
- A provider result of `sent` becomes `succeeded`, but the summary still says provider acceptance does not verify delivery.
- A non-success Resend response or request exception currently falls back to `recorded_delivery` or `delivered_to_outbox` and is therefore logged as `simulated`, rather than as a failed delivery.
- Unrecognized outcomes become `unknown`.
- An approval attempt rejected because the action is no longer pending is recorded as `failed`.

Activity summaries deliberately avoid including recipients, draft text, subjects, or raw provider responses. Existing approval API response fields remain unchanged.

## Activity Endpoint Contract

`GET /api/activity?event_id=evt-dubhacks-2026&limit=50`

- `event_id` defaults to `evt-dubhacks-2026`.
- `limit` defaults to 50 and is constrained to 1 through 200.
- Results are newest first and contain entries for the selected event only.
- The endpoint returns a normalized projection rather than the raw audit row or `details_json`.

Each item has this shape:

```json
{
  "id": "aud-123abc",
  "event_id": "evt-dubhacks-2026",
  "run_id": "run-123abc456def",
  "timestamp": "2026-10-18T12:00:00",
  "action": "agent_run",
  "status": "succeeded",
  "summary": "Agent run completed using gemini; provider status: provider_success.",
  "affected_record_ids": []
}
```

Known public statuses are `starting`, `succeeded`, `failed`, `pending_approval`, `simulated`, and `unknown`. At the API normalization boundary, `success`, `succeeded`, and `executed` become `succeeded`; `failure`, `failed`, and `error` become `failed`; `starting`, `pending_approval`, `simulated`, and `unknown` are preserved; other values become `unknown`. Tool actions use the tool name; run lifecycle entries use `agent_run`. Legacy audit entries without activity metadata are projected with `unknown` status and a generic summary.

## Test Isolation and Coverage

The existing `test_suite.py` now creates temporary directories for both SQLite and generated PDF output before importing the API server. This is necessary because the server initializes the database during import and PDF tests otherwise write a fixed path under the repository. The suite seeds its synthetic 80-person benchmark event in that temporary database when needed.

The provider regression uses a mocked Gemini response and asserts provider success, execution mode, model identifier, and persisted user/assistant messages for the returned conversation. It then simulates a provider exception and verifies the fallback is not provider success.

The activity API regression verifies:

- starting and succeeded run entries;
- a persisted outreach proposal labeled `pending_approval`;
- approval with the sandbox dispatcher logged as `simulated`;
- an orchestrator exception logged without its secret-like message;
- separate event queries returning only their own activity;
- unrecognized status strings and status-less tool outputs remaining `unknown` in both the chat response and activity feed.

The full existing suite also runs the activity tests. During implementation verification, compilation, focused tests, and all ten full-suite checks passed. A local Uvicorn HTTP check against the real FastAPI app object confirmed the route, response fields, ordering, pending/simulated labels, event filtering, and absence of credential/private-prompt markers. The local server used a temporary database and temporary PDF output path.

No real Gemini or Grok provider call was made. Their live network behavior remains unverified.

## Integration and Security Limitations

- The backend endpoint is ready, but no frontend consumer of `/api/activity` was found in the inspected Gurt frontend. Activity-page rendering and event-switch behavior therefore remain integration work.
- Event filtering is not authorization. The endpoint scopes a query by the caller-supplied `event_id`, but the application has no per-event authentication/authorization boundary. Do not expose it publicly until that is addressed.
- `succeeded` records completion/acceptance of a step, not proof that an external recipient received a message. The UI should preserve the distinction between succeeded, pending approval, simulated, and unknown.
- The tracked generated PDF was changed by an earlier test run before PDF output isolation was added. It was intentionally not restored or overwritten because its prior contents were not captured. Untracked Python bytecode cache artifacts were also inspected as generated caches and left in place rather than deleted.
