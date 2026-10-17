import { NextRequest, NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'
import { GURT_ACTION_TOOLS } from '@/lib/gurt-actions'

// Server-side base URL for the HRAgents agent server. Secrets (the LLM API
// key) only ever live in this Next.js server process — they are never sent to
// the browser. The browser talks to the backend directly only for the
// (secret-free) event WebSocket.
const HRAGENT_API_URL = (process.env.HRAGENT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')
const CANVAS_WEBHOOK_BASE_URL = (
  process.env.CANVAS_WEBHOOK_BASE_URL || 'http://127.0.0.1:3000/api/canvas/webhook'
).replace(/\/$/, '')
const CANVAS_WEBHOOK_SECRET = process.env.CANVAS_WEBHOOK_SECRET || ''

// Relative paths resolve against the backend process's working directory
// (the HRAgent_Main folder). Absolute paths also work.
const WORKSPACE_DIR = process.env.HRAGENT_WORKSPACE_DIR || 'workspace'

// Optional backend auth. When the HRAgents server is started with
// SESSION_API_KEY set, every /api/* call must carry X-Session-API-Key. We keep
// that key server-side here so it is never exposed to the browser. Empty =
// backend is open (local testing default).
const SESSION_API_KEY = process.env.HRAGENT_SESSION_API_KEY || ''

// Base headers for server-to-backend REST calls, including auth when configured.
function backendHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (SESSION_API_KEY) headers['X-Session-API-Key'] = SESSION_API_KEY
  return headers
}

// ---------------------------------------------------------------------------
// hr-mcp: read-only HR data tools (Azure SQL + AI Search, mock-backed for now)
// ---------------------------------------------------------------------------
// The backend spawns the hr-mcp server as an MCP stdio subprocess using the
// backend's venv Python (so fastmcp + deps resolve). Paths default relative to
// the repo layout and are overridable via env. Set HR_MCP_ENABLED=false to run
// the agent without HR tools.
const EVENT_MCP_ENABLED = (process.env.EVENT_MCP_ENABLED ?? 'true').toLowerCase() !== 'false'
const REPO_ROOT = path.resolve(process.cwd(), '..')
// venv layout differs by platform: Windows puts the interpreter under
// Scripts\python.exe, everything else under bin/python. Without this,
// HR_MCP_PYTHON silently resolves to a nonexistent path on macOS/Linux and
// buildMcpConfig() falls back to running with no HR tools at all -- no
// error, just a plain conversational agent with none of the HR data tools
// the system prompt promises.
const EVENT_MCP_PYTHON =
  process.env.EVENT_MCP_PYTHON ||
  (process.platform === 'win32'
    ? path.join(REPO_ROOT, 'HRAgent_Main', '.venv', 'Scripts', 'python.exe')
    : path.join(REPO_ROOT, 'HRAgent_Main', '.venv', 'bin', 'python'))
const EVENT_MCP_DIR = process.env.EVENT_MCP_DIR || path.join(REPO_ROOT, 'event_mcp')
const EVENT_MCP_SERVER = process.env.EVENT_MCP_SERVER || path.join(EVENT_MCP_DIR, 'server.py')
const EVENT_MCP_DATA_BACKEND = process.env.EVENT_MCP_DATA_BACKEND || 'mock'

// Build the agent.mcp_config map. Only includes the built-in hr-mcp server.
// Installed marketplace MCPs (cosmos-db, azure-ai-search, document-editor, etc.)
// are loaded automatically by the backend's ambient plugin system
// (LocalConversation._ensure_plugins_loaded) which properly expands ${VAR}
// placeholders from the process environment / secret registry. We must NOT
// merge them here because the /api/settings endpoint redacts secret values
// as '**********', which would override the ambient expansion and break DNS.
function buildMcpConfig(): Record<string, unknown> {
  if (!EVENT_MCP_ENABLED) return {}
  if (!fs.existsSync(EVENT_MCP_SERVER) || !fs.existsSync(EVENT_MCP_PYTHON)) {
    console.warn(
      `[event-mcp] disabled: missing ${!fs.existsSync(EVENT_MCP_PYTHON) ? EVENT_MCP_PYTHON : EVENT_MCP_SERVER}`,
    )
    return {}
  }
  return {
    event: {
      transport: 'stdio',
      command: EVENT_MCP_PYTHON,
      args: [EVENT_MCP_SERVER],
      cwd: EVENT_MCP_DIR,
      env: { EVENT_MCP_DATA_BACKEND },
    },
  }
}

// Active LLM provider. Default is "tokenrouter" (OpenAI-compatible router).
// Supported choices: "tokenrouter", "groq", "ollama", "openai", "azure", "gemini"
const LLM_PROVIDER = (process.env.LLM_PROVIDER || 'tokenrouter').toLowerCase()

// The `llm` block sent to the backend. The model *prefix* selects the provider
// client inside the backend's LiteLLM layer:
//   - "openai/<model>"      → TokenRouter / OpenAI-compatible endpoint with base_url
//   - "groq/<model>"        → Groq (testing; free tier, OpenAI-compatible)
//   - "ollama_chat/<model>" → local Ollama (testing; unlimited, no key, tools)
//   - "gemini/<model>"      → Google Gemini (alt testing)
//   - "<model>"             → OpenAI (final; e.g. gpt-4o)
//   - "azure/<deployment>"  → Azure OpenAI (final; enterprise)
type LlmConfig = Record<string, unknown>

function buildLlmConfig(): { llm?: LlmConfig; error?: string } {
  if (LLM_PROVIDER === 'tokenrouter') {
    const apiKey =
      process.env.TOKENROUTER_API_KEY ||
      'sk-v8NoCrajDilDlx1k53N2q8Iwevt3Jv0FLzL6xllGd0Xvi3jV'
    const baseUrl =
      process.env.TOKENROUTER_BASE_URL || 'https://api.tokenrouter.com/v1'
    const model = process.env.TOKENROUTER_MODEL || 'moonshotai/kimi-k3-free'

    if (!apiKey) {
      return {
        error:
          'TokenRouter is not configured. Missing: TOKENROUTER_API_KEY. ' +
          'Set it in .env.local.',
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        model: model.startsWith('openai/') ? model : `openai/${model}`,
        base_url: baseUrl,
        api_key: apiKey,
      },
    }
  }

  if (LLM_PROVIDER === 'ollama') {
    // Local Ollama via LiteLLM. We use the "ollama_chat/" prefix (Ollama's
    // /api/chat endpoint) rather than legacy "ollama/" (/api/generate): only
    // ollama_chat does NATIVE function/tool calling, which the HR agent needs to
    // actually execute the MCP tools. The prefix carries the provider, so the
    // backend passes `base_url` straight through as LiteLLM's `api_base`. No API
    // key: Ollama has no auth and the backend's api_key is optional (nothing to
    // bypass). Set OLLAMA_MODEL without a prefix — the route adds "ollama_chat/".
    const model = process.env.OLLAMA_MODEL || 'llama3.1'
    const apiBase =
      process.env.OLLAMA_API_BASE || process.env.OLLAMA_BASE_URL || 'http://localhost:11434'
    // LiteLLM's static metadata reports an 8k window for ollama/llama3.1, which
    // trips HRAgents' 16k minimum context-window guard. llama3.1 actually
    // supports up to 128k, so declare the real window explicitly — the backend
    // trusts `max_input_tokens` over LiteLLM's metadata. Override via env.
    const maxInputTokens = Number(process.env.OLLAMA_MAX_INPUT_TOKENS || '32768')
    return {
      llm: {
        usage_id: 'agent',
        model: `ollama_chat/${model}`,
        // Maps to LiteLLM's api_base so requests route to the local daemon.
        base_url: apiBase,
        max_input_tokens: maxInputTokens,
        // The backend defaults reasoning_effort="high", which LiteLLM turns into
        // Ollama's `think` flag — llama3.1 rejects it ("does not support
        // thinking"). Null disables reasoning so the request is a plain chat
        // completion (tool calling + streaming still work).
        reasoning_effort: null,
      },
    }
  }

  if (LLM_PROVIDER === 'groq') {
    const apiKey = process.env.GROQ_API_KEY
    // Llama 3.3 70B is a strong, tool-calling-capable Groq model. Override with
    // GROQ_MODEL (without the "groq/" prefix — the route adds it).
    const model = process.env.GROQ_MODEL || 'llama-3.3-70b-versatile'
    if (!apiKey) {
      return {
        error:
          'Groq is not configured. Missing: GROQ_API_KEY. ' +
          'Set it in .env.local (get a free key at https://console.groq.com/keys).',
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        // The "groq/" prefix routes LiteLLM to Groq's OpenAI-compatible API.
        model: `groq/${model}`,
        api_key: apiKey,
      },
    }
  }

  if (LLM_PROVIDER === 'azure') {
    const endpoint = process.env.AZURE_OPENAI_ENDPOINT
    const apiKey = process.env.AZURE_OPENAI_API_KEY
    const apiVersion = process.env.AZURE_OPENAI_API_VERSION || '2024-12-01-preview'
    const deployment = process.env.AZURE_OPENAI_DEPLOYMENT

    const missing: string[] = []
    if (!endpoint) missing.push('AZURE_OPENAI_ENDPOINT')
    if (!apiKey) missing.push('AZURE_OPENAI_API_KEY')
    if (!deployment) missing.push('AZURE_OPENAI_DEPLOYMENT')
    if (missing.length > 0) {
      return {
        error:
          `Azure OpenAI is not configured. Missing: ${missing.join(', ')}. ` +
          `Set these in .env.local (or switch LLM_PROVIDER=gemini for testing).`,
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        model: `azure/${deployment}`,
        base_url: endpoint,
        api_version: apiVersion,
        api_key: apiKey,
      },
    }
  }

  if (LLM_PROVIDER === 'openai') {
    const apiKey = process.env.OPENAI_API_KEY
    const model = process.env.OPENAI_MODEL || 'gpt-4o'
    const baseUrl = process.env.OPENAI_BASE_URL // optional (proxies / compatible endpoints)
    if (!apiKey) {
      return {
        error:
          'OpenAI is not configured. Missing: OPENAI_API_KEY. ' +
          'Set it in .env.local (or switch LLM_PROVIDER=gemini for testing).',
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        // LiteLLM treats an unprefixed known model name as OpenAI.
        model,
        api_key: apiKey,
        ...(baseUrl ? { base_url: baseUrl } : {}),
      },
    }
  }

  // Default: Google Gemini (testing).
  const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY
  const model = process.env.GEMINI_MODEL || 'gemini-flash-latest'
  if (!apiKey) {
    return {
      error:
        'Gemini is not configured. Missing: GEMINI_API_KEY. ' +
        'Copy .env.example to .env.local and set GEMINI_API_KEY.',
    }
  }
  return {
    llm: {
      usage_id: 'agent',
      model: `gemini/${model}`,
      api_key: apiKey,
      max_input_tokens: 1048576, // Gemini 1.5 Flash has a 1M token context window
    },
  }
}

// ---------------------------------------------------------------------------
// Gurt persona + guardrails
// ---------------------------------------------------------------------------
// Appended to the backend's built-in system prompt via agent_context so we keep
// the framework's tool-use/security scaffolding and layer the Gurt identity,
// scope limits, grounding rules, and human-in-the-loop policy on top.
const GURT_SYSTEM_SUFFIX = `You are Gurt, an event operations agent. You help small organizing teams plan and execute events through three areas:

OUTREACH — speakers, keynote presenters, workshop hosts, sponsors:
- Research candidates with evidence (bio, past talks, relevance to theme, contact info).
- Draft outreach emails and Slack/Teams messages for organizer approval before sending.
- Track reply status, conditions, and confirmed commitments.
- Coordinate availability and scheduling.

VENDORS — food, badges, lanyards, printing, shirts, AV equipment, and other supplies:
- Ask contextual questions to discover overlooked needs before sourcing.
- Find suppliers, compare quotes, and summarize trade-offs.
- Extract facts from vendor documents; flag missing information.
- Fill supported PDF/form applications using event details from the workspace.

LOGISTICS — tasks, schedules, dependencies, participant briefings:
- Break down event requirements into owned tasks with deadlines.
- Generate a run-of-show and participant-specific briefings.
- Identify conflicts and propose resolution when arrangements change.
- Maintain a shared event record so changes propagate to affected parties.

EVENT CONTEXT:
- The workspace may contain an event brief, vendor quotes, speaker shortlists, logistics plans, and form PDFs. Work from these files directly — do not ask the organizer to re-upload them.
- Persist findings to workspace files using standard tools so they survive session restarts.

AVAILABLE INTEGRATIONS (use these — never claim you lack them):
- Event Database (Cosmos DB): query_cosmos, count_documents — query the events collection for event details, speaker commitments, vendor records, logistics tasks, etc.
- Web Research: use the web_search subagent to find speaker bios, supplier websites, and pricing.
- Document Tools: office_list_pdf_fields, office_fill_pdf_form, office_validate, office_overlay_pdf_text, office_read, get_document_info — fill vendor application PDFs, read quote documents, validate forms.
- Event Core (event_mcp): event_lookup, speaker_lookup, vendor_lookup, sponsor_lookup, task_list — quick lookups for event records.

SCOPE:
- Stay in event operations. For off-topic asks, decline briefly and offer an event-ops alternative.

GROUNDING:
- Never invent speaker credentials, vendor quotes, event facts, or availability details. Use tools first, then answer only from tool results.
- Cite source documents when answering from files.

ACTION BIAS:
- When the organizer's intent is clear, act first using available tools.
- When researching speakers or vendors, return a shortlist with evidence — do not ask what the organizer already told you.
- Fill forms immediately with available event data; ask only when a required field is genuinely unknown.
- Only ask clarifying questions when genuinely ambiguous (e.g., "Which workshop session needs a speaker?").

RESPONSE STYLE:
- Lead with the answer in the first sentence. Keep replies short and skimmable (usually 2–6 sentences or a tight bullet list).
- On greetings ("hi", "hello", "yo Gurt"), reply in 1–2 warm sentences and offer 2–3 concrete examples (finding speakers, sourcing vendors, building a run-of-show). No readiness check-ins.
- After research, surface the shortlist with key fit signals and unknowns.
- Do not narrate your process ("I will now look that up", "Let me check"). Just use tools and answer.
- Do not dump raw JSON or tool payloads into the chat.

HUMAN-IN-THE-LOOP:
- Research, reads, and lookups are free — no approval needed.
- The platform enforces approval itself: set the security_risk argument on every tool call (LOW for reads/lookups, HIGH for anything that sends, writes, or changes something external). The platform blocks execution on HIGH/unknown risk until the organizer explicitly approves it — you must never claim an action completed before that approval happens.
- For sending email, Slack, or Teams messages: if a connected MCP tool for that channel is available (e.g. Gmail, Slack, or Teams integration), call it directly with security_risk=HIGH instead of send_email / send_slack_message / send_teams_message. Only use those three fallback tools when no MCP tool is connected for that channel at all.
- For vendor commitments, spending proposals, or schedule changes: propose and ask for confirmation in your reply before writing records.`

// Response tuning. Slightly higher temperature for creative research tasks.
// Overridable via env without code changes.
const LLM_TEMPERATURE = Number(process.env.GURT_LLM_TEMPERATURE ?? '0.3')
const LLM_MAX_OUTPUT_TOKENS = Number(process.env.GURT_LLM_MAX_OUTPUT_TOKENS ?? '4096')

// Token streaming. When true the backend publishes StreamingDeltaEvents over
// the WebSocket so the UI renders token-by-token. Set GURT_LLM_STREAM=false
// to fall back to whole-message delivery.
const LLM_STREAM = (process.env.GURT_LLM_STREAM ?? 'true').toLowerCase() !== 'false'

// Health check (GET without query) and final-response fetch (GET ?final=1).
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const conversationId = searchParams.get('conversationId')
  const wantsFinal = searchParams.get('final')

  if (conversationId && wantsFinal) {
    try {
      const res = await fetch(
        `${HRAGENT_API_URL}/api/conversations/${conversationId}/agent_final_response`,
        { headers: backendHeaders() },
      )
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        return NextResponse.json(
          { error: body?.detail || 'Failed to fetch final response' },
          { status: res.status || 502 },
        )
      }
      return NextResponse.json({ response: body?.response ?? '' })
    } catch (error) {
      return NextResponse.json(
        { error: error instanceof Error ? error.message : 'Failed to fetch final response' },
        { status: 502 },
      )
    }
  }

  try {
    const res = await fetch(`${HRAGENT_API_URL}/health`, { headers: backendHeaders() })
    if (!res.ok) {
      return NextResponse.json(
        { connected: false, detail: 'Agent health check failed' },
        { status: 503 },
      )
    }
    return NextResponse.json({ connected: true })
  } catch (error) {
    return NextResponse.json(
      { connected: false, detail: error instanceof Error ? error.message : 'Health check failed' },
      { status: 503 },
    )
  }
}

// Create a new backend conversation configured to use the selected LLM provider.
export async function POST() {
  const { llm, error } = buildLlmConfig()
  if (!llm) {
    return NextResponse.json({ error }, { status: 400 })
  }

  // Apply HR response tuning to whichever provider is active. LiteLLM maps
  // these per-provider; reasoning-only models strip temperature automatically.
  const tunedLlm: LlmConfig = {
    ...llm,
    temperature: LLM_TEMPERATURE,
    max_output_tokens: LLM_MAX_OUTPUT_TOKENS,
    stream: LLM_STREAM,
  }

  // The model prefix (gemini/… , azure/… , or bare OpenAI name) routes the
  // backend's LiteLLM layer to the matching provider client.
  //
  // This route only ever sends the local `hr` read-only data server in
  // mcp_config (buildMcpConfig(), below) — real integrations (Gmail, Slack,
  // GitHub, ...) are NOT sent here, and this request never sets
  // agent_context.registered_marketplaces either. They still reach the
  // running agent because LocalConversation._ensure_plugins_loaded() merges
  // in every *installed* plugin's raw .mcp.json template as an "ambient"
  // plugin on first run() (core/conversation/impl/local_conversation.py,
  // "Ambient plugins") -- independent of this request's mcp_config, and
  // independent of the backend settings store too. The actual OAuth
  // credentials for those servers are resolved separately and correctly:
  // MCPSettingsOAuthTokenStore looks them up from the backend's persisted
  // settings by matching server URL at connection time (see
  // HRAgent_Main/runtime/server/mcp_oauth_store.py), not from whatever this
  // ambient-merged mcp_config structurally contains. So server *credentials*
  // are authoritatively backend-settings-sourced (correct), but server
  // *shape* (url/transport/tool_permissions) comes from the on-disk
  // installed-plugin template, not from settings -- a user's "Edit
  // configuration" customization to tool_permissions would NOT be picked up
  // by this ambient path. This frontend is never the source of truth for
  // either.
  //
  // Guardrails:
  // - agent_context.system_message_suffix installs the HR persona + scope +
  //   grounding + human-in-the-loop rules on top of the built-in prompt.
  // - confirmation_policy: ConfirmRisky + security_analyzer: LLMSecurityAnalyzer
  //   are the actual, generic, server-side enforcement boundary (see
  //   core/agent/agent.py's _requires_user_confirmation): every tool call —
  //   MCP-sourced or client_tools — carries a `security_risk` the model sets
  //   per call, and HIGH/unknown risk is held for human approval before
  //   anything executes. This is tool-agnostic; it is not specific to email/
  //   Slack/Teams and does not need per-tool wiring to cover a new MCP.
  const startConversationRequest = {
    workspace: { working_dir: WORKSPACE_DIR },
    agent: {
      kind: 'Agent',
      llm: tunedLlm,
      tools: [],
      // Built-in HR data tools only. Marketplace MCPs (cosmos-db,
      // azure-ai-search, document-editor) load via ambient plugin system.
      mcp_config: buildMcpConfig(),
      agent_context: {
        system_message_suffix: GURT_SYSTEM_SUFFIX,
        load_user_skills: true,
      },
    },
    confirmation_policy: {
      kind: 'ConfirmRisky'
    },
    security_analyzer: {
      kind: 'LLMSecurityAnalyzer'
    },
    // Fallback communication tools (send_email / send_slack_message /
    // send_teams_message), used only when no MCP tool is connected for that
    // channel (see GURT_SYSTEM_SUFFIX). The backend registers these and, when
    // called, emits an ActionEvent + immediately acks WITHOUT performing the
    // action; the frontend renders an "Approve & Send" card in chat.
    client_tools: GURT_ACTION_TOOLS,
    webhooks: [
      {
        base_url: CANVAS_WEBHOOK_BASE_URL,
        headers: CANVAS_WEBHOOK_SECRET
          ? { 'X-Canvas-Webhook-Secret': CANVAS_WEBHOOK_SECRET }
          : {},
        event_buffer_size: 1,
        flush_delay: 0.25,
        num_retries: 3,
        retry_delay: 1,
        max_queue_size: 1000,
      },
    ],
    max_iterations: 100,
  }

  try {
    const res = await fetch(`${HRAGENT_API_URL}/api/conversations`, {
      method: 'POST',
      headers: backendHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(startConversationRequest),
    })

    const body = await res.json().catch(() => null)
    if (!res.ok) {
      const detail =
        (body && (body.detail || body.exception || body.error)) ||
        'Failed to create conversation on the Gurt backend'
      console.error('Gurt create-conversation error:', detail)
      return NextResponse.json(
        { error: typeof detail === 'string' ? detail : JSON.stringify(detail) },
        { status: res.status || 502 },
      )
    }

    if (!body?.id) {
      return NextResponse.json(
        { error: 'Gurt backend did not return a conversation id' },
        { status: 502 },
      )
    }

    console.info('[canvas-trace]', JSON.stringify({
      conversationId: body.id,
      turnId: null,
      stage: 'conversation started',
      timestamp: new Date().toISOString(),
      status: 'success',
    }))
    console.info('[canvas-trace]', JSON.stringify({
      conversationId: body.id,
      turnId: null,
      stage: 'webhook registered',
      timestamp: new Date().toISOString(),
      status: 'success',
      baseUrl: CANVAS_WEBHOOK_BASE_URL,
    }))

    return NextResponse.json({ conversationId: body.id })
  } catch (error) {
    console.error('Chat API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}

// Interrupt a running conversation.
export async function DELETE(request: NextRequest) {
  let conversationId: string | undefined
  try {
    const body = await request.json()
    conversationId = body?.conversationId
  } catch {
    /* no body */
  }
  if (!conversationId) {
    return NextResponse.json({ error: 'conversationId is required' }, { status: 400 })
  }
  try {
    await fetch(`${HRAGENT_API_URL}/api/conversations/${conversationId}/interrupt`, {
      method: 'POST',
      headers: backendHeaders(),
    })
  } catch {
    /* best effort */
  }
  return NextResponse.json({ success: true })
}
