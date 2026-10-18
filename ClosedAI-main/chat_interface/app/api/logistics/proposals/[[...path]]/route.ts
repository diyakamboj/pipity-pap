import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/backend-proxy'

/**
 * Read-Only Proxy for /api/logistics/proposals/* -> backend /api/logistics/proposals/*
 *
 * ARCHITECTURAL INVARIANTS:
 * 1. Read-Only Gateway Boundary:
 *    This route handler intentionally exports ONLY the GET method.
 *    In the Next.js App Router, omitting POST, PUT, PATCH, and DELETE ensures that
 *    the Next.js runtime automatically rejects mutation attempts with HTTP 405
 *    (Method Not Allowed) at the edge, before any request reaches the Python service.
 * 2. Secret Isolation:
 *    The browser only talks to this relative Next.js route. The server-to-server
 *    secret (HRAGENT_SESSION_API_KEY) is attached inside proxyToBackend on the
 *    Node.js server and is never exposed in browser bundles or responses.
 * 3. Freshness & Cache Invalidation:
 *    Proposal status, expiration, and baseline staleness change dynamically.
 *    Static caching and intermediate revalidation are strictly disabled.
 */

export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET(request: NextRequest) {
  const response = await proxyToBackend(request, 'logistics')

  // Enforce zero-caching so clients always see the authoritative EventStore state.
  response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate')
  response.headers.set('Pragma', 'no-cache')
  response.headers.set('Expires', '0')

  return response
}
