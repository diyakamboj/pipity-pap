# Integration verification checklist (Phase 5)

Before any integration is installed, it must pass the checks below. The goal is
to install integrations one by one with evidence, "instead of blindly adding
dependencies" (implementation plan, Phase 5).

## Repo health check (one command)

GitHub-API check for `pushed_at` / `archived` / `stars` so re-verification is a
single command:

```bash
# PowerShell
$repos = @(
  "github/github-mcp-server",           # github (official hosted remote)
  "taylorwilsdon/google_workspace_mcp", # community alternative (now using official Google endpoints)
  "softeria/ms-365-mcp-server",         # microsoft-365
  "korotovsky/slack-mcp-server",        # slack (community - official uses hosted endpoint)
  "sooperset/mcp-atlassian",            # jira (community - official uses hosted endpoint)
  "notionhq/notion-mcp-server",         # notion (official)
  "crystaldba/postgres-mcp",            # postgres (community - no official)
  "linear/linear-mcp-server",           # linear (official hosted endpoint - check org)
)
foreach ($r in $repos) {
  $j = Invoke-RestMethod -Headers @{ "User-Agent" = "hr-agent-verify" } "https://api.github.com/repos/$r"
  [pscustomobject]@{ repo=$r; pushed=$j.pushed_at; archived=$j.archived; stars=$j.stargazers_count } | Format-List
}
```

Acceptance: `pushed_at` within ~6 months, `archived` = `false`. Dead candidates
are removed from the catalog, not installed.

## Official MCP Server Endpoints (verified 2026-08-06)

| Integration | Official Hosted Endpoint | Transport | Auth |
|---|---|---|---|
| **GitHub** | `https://api.githubcopilot.com/mcp/` | streamable-http | PAT (Bearer token) |
| **Gmail** | `https://gmailmcp.googleapis.com/mcp/v1` | streamable-http | OAuth2 |
| **Google Drive** | `https://drivemcp.googleapis.com/mcp/v1` | streamable-http | OAuth2 |
| **Google Calendar** | `https://calendarmcp.googleapis.com/mcp/v1` | streamable-http | OAuth2 |
| **Google Chat** | `https://chatmcp.googleapis.com/mcp/v1` | streamable-http | OAuth2 |
| **Google People** | `https://people.googleapis.com/mcp/v1` | streamable-http | OAuth2 |
| **Slack** | `https://mcp.slack.com/mcp` | streamable-http | OAuth 2.1 |
| **Jira** | `https://mcp.atlassian.com/v1/mcp/authv2` | streamable-http | OAuth2 / API Token |
| **Notion** | `npx -y @notionhq/notion-mcp-server` | stdio | Integration Token (ntn_) |
| **Linear** | `https://mcp.linear.app/mcp` | SSE | OAuth2 |
| **Microsoft 365** | `npx -y @softeria/ms-365-mcp-server` | stdio | MSAL OAuth (Entra ID) |
| **PostgreSQL** | `uvx postgres-mcp --restricted` | stdio | DATABASE_URI |

**Note on Google Workspace**: Google provides 5 separate official hosted MCP endpoints (not a single package):
- Gmail: `https://gmailmcp.googleapis.com/mcp/v1`
- Google Drive: `https://drivemcp.googleapis.com/mcp/v1`
- Google Calendar: `https://calendarmcp.googleapis.com/mcp/v1`
- Google Chat: `https://chatmcp.googleapis.com/mcp/v1`
- Google People: `https://people.googleapis.com/mcp/v1`

All use OAuth2 with Google's token persistence (disk-backed encrypted cache).

## Per-integration checklist

| Check | Requirement |
|---|---|
| Repo active | `pushed_at` < ~6 months, not archived |
| Maintenance | README current, issues triaged, no abandoned notice |
| Security posture | Read-only default or least-privilege scope; writes opt-in |
| Auth support | OAuth (reuse `/api/mcp/oauth/*`) and/or env token (secrets API) |
| Runtime present | Command verified on the host (`uvx`, `npx`, Go binary) |
| Production readiness | Not "experimental"; pinned/known-good version where possible |
| Useful tools | Tools actually exercised by HR workflows |

## Per-server verification to run at install time

1. **Install:** `POST /api/plugins/install` (source = resolved marketplace path).
   Plugin downloads, `.mcp.json` loads (`coerce_mcp_config`), no malformed config.
2. **Discovery:** `POST /api/mcp/test` with the server spec → tools list returned.
3. **Auth:** token/OAuth resolves via `${VAR}` / OAuth job.
4. **Execution:** read tool runs; write tool surfaces via HITL/approval.
5. **Error handling:** invalid token, expired OAuth, server offline — each returns
   a clean surfaced error, no crash.

## Gmail pilot — Google OAuth provisioning (guided)

1. Create a GCP project (console.cloud.google.com).
2. Enable the **Gmail API** (APIs & Services → Library).
3. Configure the OAuth consent screen (External → add test users as needed).
4. Create OAuth client ID, application type **Desktop** → client id + secret.
5. Paste client id/secret as secrets (settings secrets API), then start the
   existing browser-coordinated OAuth flow (`POST /api/mcp/oauth/start`).
6. Record results below and in `marketplaces/INSTALLED.md`.

## Verification results

**Gmail — server changed 2026-08-06.** Original candidate `GongRzhe/Gmail-MCP-Server`
is **archived** (`archived=true`, last push 2025-08-06) → fails the acceptance
rule and was removed from the pilot. Replaced with official Google hosted endpoint
`https://gmailmcp.googleapis.com/mcp/v1`.

**All Google Workspace integrations — switched to official hosted endpoints 2026-08-06.**
Each Google product now has its own official MCP endpoint (see table above).
The community `taylorwilsdon/google_workspace_mcp` is kept as reference but no longer used.

Verified (2026-08-06, backend port 8001):

| Integration | Install | Discovery (probe) | Auth path | Execution | Notes |
|-------------|---------|-------------------|-----------|-----------|-------|
| **github** | ✅ | ✅ 40+ tools | ✅ PAT via `${VAR}` | ✅ `search_repositories` returns real data | Uses official hosted endpoint `https://api.githubcopilot.com/mcp/` |
| **gmail** | ✅ | ✅ 13 tools (create_draft, list_drafts, get_thread, etc.) | ⏳ needs GCP OAuth id/secret | ⏳ | Official endpoint `https://gmailmcp.googleapis.com/mcp/v1` |
| **google-drive** | ✅ | ✅ 8 tools (list_recent_files, search_files, etc.) | ⏳ needs GCP OAuth id/secret | ⏳ | Official endpoint `https://drivemcp.googleapis.com/mcp/v1` |
| **google-calendar** | ✅ | ✅ 9 tools (list_events, get_event, list_calendars, suggest_time, create_event, update_event, delete_event, respond_to_event, search_events) | ⏳ needs GCP OAuth id/secret | ⏳ | Official endpoint `https://calendarmcp.googleapis.com/mcp/v1` |
| **google-chat** | ✅ | ✅ 4 tools (list_messages, search_messages, search_conversations, send_message) | ⏳ needs GCP OAuth id/secret | ⏳ | Official endpoint `https://chatmcp.googleapis.com/mcp/v1` |
| **google-people** | ✅ | ✅ 3 tools (search_directory_people, search_contacts, get_user_profile) | ⏳ needs GCP OAuth id/secret | ⏳ | Official endpoint `https://people.googleapis.com/mcp/v1` |
| **microsoft-365** | ✅ | ✅ 130+ tools (Outlook, OneDrive, Calendar, Teams, Planner) | ⏳ needs Azure app registration | ⏳ | Uses `npx -y @softeria/ms-365-mcp-server` (stdio) |
| **notion** | ✅ | ✅ 23 tools (API-post-search, API-retrieve-a-page, etc.) | ⏳ needs integration token | ⏳ | Uses `npx -y @notionhq/notion-mcp-server` (stdio) |
| **jira** | ✅ | ✅ 3 tools (Teamwork Graph API) | ⏳ needs OAuth/API token | ⏳ | Endpoint `https://mcp.atlassian.com/v1/mcp/authv2` — returns Teamwork Graph tools (getTeamworkGraphContext, getTeamworkGraphObject, addTeamworkGraphContext), not traditional Jira issue ops |
| **slack** | ✅ | ❌ 401 (requires OAuth) | ⏳ needs Slack app + OAuth 2.1 | ⏳ | Endpoint `https://mcp.slack.com/mcp` returns 401 without valid token |
| **linear** | ✅ | ❌ 401 (requires OAuth) | ⏳ needs OAuth client id/secret | ⏳ | Endpoint `https://mcp.linear.app/mcp` — SSE with auth required for probe |
| **postgres** | ✅ | ❌ Windows build fails (pglast native dep) | ⏳ needs `DATABASE_URI` + Linux/macOS host | ⏳ | Uses `uvx postgres-mcp --restricted` — requires running Postgres instance |

**Summary of working (verified) integrations:**
- **GitHub** — Fully working with PAT (Bearer token). Read/write tools available.
- **Gmail/Drive/Calendar/Chat/People** — Discovery works unauthenticated; full auth+execution requires GCP OAuth client id/secret.
- **Microsoft 365** — Discovery works unauthenticated (130+ tools); auth requires Azure app.
- **Notion** — Discovery works unauthenticated (23 tools); auth needs integration token.
- **Jira** — Discovery works but returns Teamwork Graph tools, not traditional Jira issue operations. Requires valid Atlassian API token for probe.
- **Slack** — Returns 401 without valid token; needs valid OAuth 2.1 flow with Slack app.
- **Linear** — SSE endpoint requires auth for probe; returns 401 without valid token.

**Integrations needing investigation:**
- **PostgreSQL** — Requires running database; restricted mode works but needs `DATABASE_URI`. Native dependency (pglast) fails to build on Windows.