import { NextRequest, NextResponse } from 'next/server'

import { recordCanvasEvents } from '@/lib/canvas-server'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  const secret = process.env.CANVAS_WEBHOOK_SECRET
  if (secret && request.headers.get('x-canvas-webhook-secret') !== secret) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { conversationId } = await params
  const body = await request.json().catch(() => null)
  const events = Array.isArray(body) ? body : body ? [body] : []
  await recordCanvasEvents(conversationId, events)
  return NextResponse.json({ ok: true, received: events.length })
}
