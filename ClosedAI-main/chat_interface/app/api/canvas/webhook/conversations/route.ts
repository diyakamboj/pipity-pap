import { NextRequest, NextResponse } from 'next/server'

import { recordCanvasConversation } from '@/lib/canvas-server'

export async function POST(request: NextRequest) {
  const secret = process.env.CANVAS_WEBHOOK_SECRET
  if (secret && request.headers.get('x-canvas-webhook-secret') !== secret) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json().catch(() => null)
  if (body) await recordCanvasConversation(body)
  return NextResponse.json({ ok: true })
}
