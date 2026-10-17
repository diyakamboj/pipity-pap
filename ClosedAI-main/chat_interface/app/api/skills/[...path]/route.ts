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

  try {
    const res = await fetch(`${HRAGENT_API_URL}/api/skills`, {
      method: 'POST',
      headers: backendHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    })

    const data = await res.json().catch(() => null)
    if (!res.ok) {
      return NextResponse.json(
        { error: data?.detail || 'Failed to fetch skills' },
        { status: res.status || 502 },
      )
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('Skills API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}

export async function GET(request: NextRequest) {
  // If hitting /api/skills/installed, we proxy to backend's /api/skills/installed
  const url = new URL(request.url)
  const path = url.pathname.replace('/api/skills', '') || ''

  try {
    const res = await fetch(`${HRAGENT_API_URL}/api/skills${path}`, {
      method: 'GET',
      headers: backendHeaders(),
    })

    const data = await res.json().catch(() => null)
    if (!res.ok) {
      return NextResponse.json(
        { error: data?.detail || 'Failed to fetch skills' },
        { status: res.status || 502 },
      )
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('Skills API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}
