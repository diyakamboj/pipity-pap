import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseEvaluatorResult,
  readCanvasState,
  recordCanvasEvents,
  shouldEvaluateCanvas,
  validateCanvasBlocks,
} from './canvas-server'

function action(tool_name: string, tool_call_id: string, args: Record<string, unknown> = {}) {
  return { kind: 'ActionEvent', tool_name, tool_call_id, action: { name: tool_name, args } }
}

function observation(tool_name: string, tool_call_id: string, content: unknown = undefined, is_error = false) {
  return { kind: 'ObservationEvent', tool_name, tool_call_id, observation: { is_error, content } }
}

function terminal(id: string) {
  return { kind: 'MessageEvent', source: 'agent', id, llm_message: { role: 'assistant', content: 'Done.' } }
}

function waitForPipeline() {
  return new Promise((resolve) => setTimeout(resolve, 450))
}

test('pre-filter skips simple prose with no execution evidence', () => {
  const result = shouldEvaluateCanvas({ intent: 'conversation' }, [])
  assert.equal(result.candidate, false)
})

test('pre-filter sends arbitrary structured outcomes to evaluator', () => {
  const result = shouldEvaluateCanvas(
    { intent: 'show compiled result bundle' },
    [
      action('compile_result_bundle', '1'),
      observation('compile_result_bundle', '1', {
        title: 'Quarterly planning bundle',
        owner: 'Operations',
        rows: [
          { item: 'Budget', status: 'ready', value: '$120k' },
          { item: 'Hiring plan', status: 'needs review', value: '4 roles' },
        ],
      }),
    ],
  )
  assert.equal(result.candidate, true)
  assert.equal(result.reason.structuredOutcome, true)
})

test('pre-filter can consider generic multi-step work without assigning a Canvas type', () => {
  const result = shouldEvaluateCanvas(
    { intent: 'review dependent workflow results' },
    [
      action('collect_inputs', '1'),
      observation('collect_inputs', '1', { ok: true }),
      action('prepare_drafts', '2'),
      observation('prepare_drafts', '2', { count: 2 }),
      action('summarize_status', '3'),
      observation('summarize_status', '3', { pending: 1 }),
    ],
  )
  assert.equal(result.candidate, true)
  assert.equal(result.reason.batchOrMultiStep, true)
})

test('evaluator parsing rejects malformed responses safely', () => {
  assert.throws(() => parseEvaluatorResult('not json'), /No JSON found/)
  assert.throws(() => parseEvaluatorResult(null), /no JSON object/i)
})

test('evaluator parsing normalizes missing optional fields', () => {
  const result = parseEvaluatorResult('{"workflow_detected":true,"canvas_worthy":true}')
  assert.deepEqual(result, {
    workflow_detected: true,
    canvas_worthy: true,
    workflow_type: null,
    reason: '',
  })
})

test('generator validation accepts only supported generic block payloads', () => {
  const blocks = validateCanvasBlocks({
    blocks: [
      { type: 'summary-card', version: 1, props: { title: 'Result', body: 'Ready for review.' } },
      { type: 'made-up-block', version: 1, props: {} },
    ],
  }, new Set(['summary-card']))
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].type, 'summary-card')
})

test('generator validation rejects empty or unsupported output', () => {
  assert.throws(() => validateCanvasBlocks({ blocks: [] }), /no supported/i)
  assert.throws(() => validateCanvasBlocks({ type: 'unknown', version: 1, props: {} }, new Set(['table'])), /no supported/i)
})

test('generator validation removes approval controls from Canvas blocks', () => {
  const blocks = validateCanvasBlocks({
    blocks: [
      { type: 'approval-card', version: 1, props: { title: 'Send email' } },
      { type: 'email-preview', version: 1, props: { subject: 'Welcome', actions: ['send', 'discard'] } },
    ],
  }, new Set(['approval-card', 'email-preview']))
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].type, 'email-preview')
  assert.equal('actions' in blocks[0].props, false)
})

test('new turn does not reuse prior scalar lookup evidence', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `turn-scope-${Date.now()}`
    await recordCanvasEvents(conversationId, [
      action('lookup_scalar_value', '1'),
      observation('lookup_scalar_value', '1', { remaining: 12 }),
      terminal('lookup-turn'),
    ])
    await waitForPipeline()
    assert.equal(readCanvasState(conversationId).status, 'skipped')

    await recordCanvasEvents(conversationId, [
      action('compile_result_bundle', '1', { title: 'Planning packet' }),
      observation('compile_result_bundle', '1', {
        title: 'Planning packet',
        sections: [
          { label: 'Budget', status: 'ready' },
          { label: 'Risks', status: 'review' },
        ],
        draft: {
          subject: 'Planning update',
          body: 'Here is the structured planning update for review.',
        },
      }),
      terminal('structured-turn'),
    ])
    await waitForPipeline()

    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'skipped')
    assert.deepEqual(state.blocks, [])
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('simple scalar lookup still stays out of Canvas', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `scalar-${Date.now()}`
    await recordCanvasEvents(conversationId, [
      action('lookup_scalar_value', '1', { key: 'remaining_days' }),
      observation('lookup_scalar_value', '1', { remaining_days: 12 }),
      terminal('scalar-turn'),
    ])
    await waitForPipeline()

    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'skipped')
    assert.deepEqual(state.blocks, [])
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})
