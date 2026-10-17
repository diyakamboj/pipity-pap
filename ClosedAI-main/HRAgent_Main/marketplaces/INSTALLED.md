# Installed integrations (Phase 6 record)

Each install appends a row: install → discovery (probe) → auth → execution →
error-handling. This is the audit trail for the "install one by one" rule.

| Integration | Installed | Server name | Probe tools | Auth | Execution | Verified date |
|---|---|---|---|---|---|---|
| github | ✅ | github | ✅ 40+ (search_repositories etc.) | ✅ PAT resolves from secrets store → conversation registry → `${VAR}` | ✅ probe ran `search_repositories` (real data); agent run pending working LLM key | 2026-08-06 |
| gmail (pilot) | ✅ | gmail | ✅ 13 (create_draft, list_drafts, get_thread, etc.) | ⏳ needs GCP OAuth id/secret | ⏳ auth-pending; unauth error surfaced cleanly | 2026-08-06 (partial) |
| google-drive | ✅ | google-drive | ✅ 8 (list_recent_files, search_files, etc.) | ⏳ needs GCP OAuth id/secret | ⏳ | 2026-08-06 (partial) |
| slack | ✅ | slack | ❌ 404/401 | ⏳ needs Slack app + OAuth 2.1 | ⏳ | 2026-08-06 (partial) |
| jira | ✅ | jira | ✅ 3 tools (Teamwork Graph) — needs valid token | ⏳ needs OAuth/API token | ⏳ | 2026-08-06 (partial) |
| postgres | ✅ | postgres | ❌ Windows build fails (pglast native dep) | ⏳ needs DATABASE_URI + Linux/macOS host | ⏳ | 2026-08-06 (partial) |
| microsoft-365 | ✅ | microsoft-365 | ✅ 130+ tools (discovery works) | ⏳ needs Azure app + OAuth | ⏳ | 2026-08-06 (partial) |
| notion | ✅ | notion | ✅ 23 tools (discovery works) | ⏳ needs integration token (ntn_) | ⏳ | 2026-08-06 (partial) |
| linear | ✅ | linear | ❌ 401 (requires OAuth) | ⏳ needs OAuth client id/secret | ⏳ | 2026-08-06 (partial) |
| google-calendar | ✅ | google-calendar | ✅ 9 tools (discovery works) | ⏳ needs GCP OAuth id/secret | ⏳ | 2026-08-06 (partial) |
| google-chat | ✅ | google-chat | ✅ 4 tools (discovery works) | ⏳ needs GCP OAuth id/secret | ⏳ | 2026-08-06 (partial) |
| google-people | ✅ | google-people | ✅ 3 tools (discovery works) | ⏳ needs GCP OAuth id/secret | ⏳ | 2026-08-06 (partial) |

Legend: **Install** = `POST /api/plugins/install` succeeded; **Probe tools** =
`POST /api/mcp/test` returned a tools list; **Auth** = token/OAuth resolved;
**Execution** = a read tool ran end-to-end; **Verified date** = Phase-11 check
passed.
