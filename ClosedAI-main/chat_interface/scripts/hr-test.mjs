// Dev harness: create a conversation via the Next.js proxy, send one prompt over
// the WebSocket, print agent output + the intermediate event kinds. Usage:
//   node scripts/hr-test.mjs "your prompt here"
const APP = process.env.APP_URL || 'http://localhost:3000'
const WS_BASE = process.env.NEXT_PUBLIC_HRAGENT_WS_URL || 'ws://127.0.0.1:8001'
const PROMPT = process.argv[2] || 'hello there!'

// Slow-model tolerance: the free-tier TokenRouter/Groq reasoning models can take
// 2-3+ minutes per LLM call, so the default wait is generous and overridable via
// HR_TEST_TIMEOUT_MS. The old 110s default silently "passed" only with fast
// providers (local Ollama) and timed out mid-run with cloud reasoning models.
const TIMEOUT_MS = Number(process.env.HR_TEST_TIMEOUT_MS || '600000')

function log(...a) { console.log(new Date().toISOString().slice(11, 19), ...a) }

const res = await fetch(`${APP}/api/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: '{}',
})
const body = await res.json()
if (!res.ok) { log('CREATE FAILED', res.status, body); process.exit(1) }
const id = body.conversationId
log('conversation:', id)

const ws = new WebSocket(`${WS_BASE}/sockets/events/${id}`)
let done = false
const finish = (code) => { if (!done) { done = true; try { ws.close() } catch {} process.exit(code) } }
const kinds = {}

ws.addEventListener('open', () => {
  log('sending:', JSON.stringify(PROMPT))
  ws.send(JSON.stringify({ role: 'user', content: [{ type: 'text', text: PROMPT }] }))
})
ws.addEventListener('message', (e) => {
  let evt
  try { evt = JSON.parse(e.data) } catch { return }
  const kind = evt.kind
  kinds[kind] = (kinds[kind] || 0) + 1
  if (kind === 'MessageEvent' && evt.source === 'agent') {
    const c = evt.llm_message?.content
    const text = typeof c === 'string' ? c : Array.isArray(c) ? c.filter(x => x?.type === 'text').map(x => x.text).join('\n') : ''
    if (text) log('AGENT:', text)
  } else if (kind === 'ActionEvent') {
    const args = evt.action ? Object.fromEntries(Object.entries(evt.action).filter(([k]) => k !== 'kind')) : {}
    log('ACTION →', evt.tool_name, evt.summary ? `(${evt.summary})` : '', JSON.stringify(args))
  } else if (kind === 'ObservationEvent') {
    log('OBSERVATION ←', evt.tool_name, 'is_error=' + !!evt.observation?.is_error)
    if (process.env.DUMP_OBS) log('  OBS RAW:', JSON.stringify(evt.observation).slice(0, 900))
  } else if (kind === 'StreamingDeltaEvent') {
    // Count only; contents are noisy. First delta confirms streaming is live.
    if (kinds.StreamingDeltaEvent === 1) log('STREAMING: first token delta received')
  } else if (kind === 'ConversationStateUpdateEvent') {
    const v = evt.value
    const status = evt.key === 'execution_status' ? (typeof v === 'string' ? v : v?.execution_status) : v?.execution_status
    if (status) log('status:', status)
    if (status && ['finished', 'error', 'stuck'].includes(status)) {
      setTimeout(async () => {
        try {
          const r = await fetch(`${APP}/api/chat?conversationId=${encodeURIComponent(id)}&final=1`)
          if (r.ok) { const d = await r.json(); if (d.response) log('FINAL:', d.response) }
        } catch {}
        log('event kinds:', JSON.stringify(kinds))
        finish(0)
      }, 400)
    }
  } else if (kind === 'AgentErrorEvent' || kind === 'ServerErrorEvent' || kind === 'ConversationErrorEvent') {
    log('ERROR EVENT:', kind, JSON.stringify(evt).slice(0, 400))
    setTimeout(() => finish(1), 200)
  }
})
ws.addEventListener('error', () => { log('ws error'); finish(1) })
setTimeout(() => { log('TIMEOUT; kinds:', JSON.stringify(kinds)); finish(1) }, TIMEOUT_MS)
