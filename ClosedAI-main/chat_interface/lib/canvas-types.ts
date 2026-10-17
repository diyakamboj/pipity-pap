export interface CanvasBlock {
  type: string
  version: string | number
  props: Record<string, unknown>
}

export interface CanvasStatePayload {
  conversationId: string
  turnId: string | null
  status: 'empty' | 'evaluating' | 'ready' | 'skipped' | 'error'
  blocks: CanvasBlock[]
  error?: string
  updatedAt: string
}
