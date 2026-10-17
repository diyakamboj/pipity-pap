import { NextRequest, NextResponse } from 'next/server'

import { readCanvasState } from '@/lib/canvas-server'

export async function GET(request: NextRequest) {
  const conversationId = request.nextUrl.searchParams.get('conversationId')?.trim()
  if (!conversationId) {
    return NextResponse.json({ error: 'conversationId is required' }, { status: 400 })
  }
  return NextResponse.json(readCanvasState(conversationId))
}
