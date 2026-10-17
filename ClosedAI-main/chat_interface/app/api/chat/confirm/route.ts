import { NextRequest, NextResponse } from 'next/server'

const HRAGENT_API_URL = (process.env.HRAGENT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')
const SESSION_API_KEY = process.env.HRAGENT_SESSION_API_KEY || ''

function backendHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (SESSION_API_KEY) headers['X-Session-API-Key'] = SESSION_API_KEY
  return headers
}

export async function POST(request: NextRequest) {
  let body: any
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  const { conversationId, accept, reason } = body

  if (!conversationId) {
    return NextResponse.json({ error: 'conversationId is required' }, { status: 400 })
  }

  try {
    const res = await fetch(`${HRAGENT_API_URL}/api/conversations/${conversationId}/events/respond_to_confirmation`, {
      method: 'POST',
      headers: backendHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ accept, reason: reason || 'User rejected the action.' }),
    })

    if (!res.ok) {
      const errorBody = await res.json().catch(() => null)
      console.error('Confirmation response failed:', errorBody)
      return NextResponse.json(
        { error: errorBody?.detail || 'Failed to submit confirmation' },
        { status: res.status || 502 },
      )
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Confirmation API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}
