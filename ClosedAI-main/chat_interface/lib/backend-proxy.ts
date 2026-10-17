import { NextRequest, NextResponse } from "next/server"

/* Server-side proxy to the HRAgents backend API.
 *
 * Mirrors app/api/skills/[...path]/route.ts: the session API key stays on the
 * server; the browser only ever talks to these /api/* proxies, never to the
 * backend directly. Prefixes are used verbatim, e.g. proxyToBackend(req, "mcp")
 * forwards /api/mcp/test to <backend>/api/mcp/test.
 */

const HRAGENT_API_URL = (process.env.HRAGENT_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "")
const SESSION_API_KEY = process.env.HRAGENT_SESSION_API_KEY || ""

function backendHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (SESSION_API_KEY) headers["X-Session-API-Key"] = SESSION_API_KEY
  return headers
}

export async function proxyToBackend(request: NextRequest, prefix: string): Promise<NextResponse> {
  const url = new URL(request.url)
  // Strip the Next.js route prefix (/api/<prefix>) to recover the backend path.
  const path = url.pathname.replace(`/api/${prefix}`, "") || ""
  const search = url.search || ""
  const method = request.method

  const headers: Record<string, string> = {}
  const contentType = request.headers.get("content-type")
  if (contentType) headers["Content-Type"] = contentType
  const accept = request.headers.get("accept")
  if (accept) headers["Accept"] = accept
  // Forward the settings client's encryption preference so secret fields
  // round-trip as Fernet ciphertext (never as plaintext) through the proxy.
  // Only "encrypted" is honored: the backend treats "plaintext" as
  // backend-to-backend-only, so the browser-facing proxy must never forward it.
  if (request.headers.get("x-expose-secrets") === "encrypted") {
    headers["X-Expose-Secrets"] = "encrypted"
  }

  let body: string | undefined
  if (method !== "GET" && method !== "HEAD") {
    body = await request.text()
  }

  try {
    const res = await fetch(`${HRAGENT_API_URL}/api/${prefix}${path}${search}`, {
      method,
      headers: backendHeaders(headers),
      body,
    })

    const data = await res.json().catch(() => null)
    if (!res.ok) {
      return NextResponse.json(
        { error: data?.detail || `Failed to ${method} ${prefix}` },
        { status: res.status || 502 },
      )
    }
    return NextResponse.json(data)
  } catch (error) {
    console.error(`${prefix} proxy error:`, error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 },
    )
  }
}
