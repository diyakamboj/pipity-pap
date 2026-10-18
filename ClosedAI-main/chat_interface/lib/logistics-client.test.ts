import assert from 'node:assert/strict'
import test from 'node:test'

import * as logisticsClient from './logistics-client'
import {
  fetchLogisticsProposal,
  fetchLogisticsProposals,
  LogisticsApiError,
  type LogisticsProposal,
  type ProposalListResponse,
} from './logistics-client'
import * as proxyRoute from '../app/api/logistics/proposals/[[...path]]/route'

const SAMPLE_PROPOSAL: LogisticsProposal = {
  id: 'prop-20261018-001',
  event_id: 'evt-001',
  target_schedule_id: 'sch-002',
  title: 'Reschedule Opening Keynote',
  description: 'Shift start time by 30 mins to avoid stage setup collision.',
  status: 'pending',
  persisted_status: 'pending',
  effective_status: 'pending',
  is_expired: false,
  is_stale: false,
  proposed_changes: [
    {
      record_id: 'sch-002',
      field: 'start_time',
      before: '10:00',
      after: '10:30',
      reason: 'Stage setup buffer',
    },
    {
      record_id: 'sch-002',
      field: 'end_time',
      before: '11:00',
      after: '11:30',
    },
  ],
  impact: {
    conflicts_resolved: ['conf-main-stage-overlap'],
    conflicts_created: [],
    affected_sessions: ['sch-002', 'sch-qa-01'],
    briefings_invalidated: ['Lead Organizer', 'Stage Manager'],
    risk_level: 'low',
  },
  required_confirmations: ['lead_organizer'],
  created_at: '2026-10-18T00:00:00Z',
  expires_at: '2026-10-18T02:00:00Z',
  baseline_version: 1,
  baseline_fingerprint: 'fp-sha256-abcdef123456',
}

test('fetchLogisticsProposals queries default endpoint and parses response', async () => {
  let capturedUrl = ''
  let capturedInit: RequestInit | undefined

  const mockFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    capturedUrl = String(input)
    capturedInit = init
    const payload: ProposalListResponse = {
      event_id: 'evt-001',
      total: 1,
      proposals: [SAMPLE_PROPOSAL],
    }
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  const result = await fetchLogisticsProposals({}, mockFetch)

  assert.equal(capturedUrl, '/api/logistics/proposals')
  assert.equal(capturedInit?.method, 'GET')
  assert.equal(capturedInit?.cache, 'no-store')
  assert.equal(result.total, 1)
  assert.equal(result.proposals[0].id, 'prop-20261018-001')
  assert.equal(result.proposals[0].proposed_changes.length, 2)
  assert.equal(result.proposals[0].is_expired, false)
})

test('fetchLogisticsProposals preserves query parameters', async () => {
  let capturedUrl = ''

  const mockFetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input)
    return new Response(JSON.stringify({ event_id: 'evt-002', total: 0, proposals: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  await fetchLogisticsProposals({ event_id: 'evt-002', status: 'pending' }, mockFetch)

  assert.equal(capturedUrl, '/api/logistics/proposals?event_id=evt-002&status=pending')
})

test('fetchLogisticsProposals throws LogisticsApiError on server 502/500', async () => {
  const mockFetch = (async () => {
    return new Response(JSON.stringify({ error: 'Backend logistics service unreachable' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  await assert.rejects(
    async () => {
      await fetchLogisticsProposals({}, mockFetch)
    },
    (err: unknown) => {
      assert(err instanceof LogisticsApiError)
      assert.equal(err.status, 502)
      assert.match(err.message, /Backend logistics service unreachable/)
      return true
    },
  )
})

test('fetchLogisticsProposals handles network disconnection', async () => {
  const mockFetch = (async () => {
    throw new Error('ECONNREFUSED')
  }) as typeof fetch

  await assert.rejects(
    async () => {
      await fetchLogisticsProposals({}, mockFetch)
    },
    (err: unknown) => {
      assert(err instanceof LogisticsApiError)
      assert.equal(err.status, 503)
      assert.match(err.message, /ECONNREFUSED/)
      return true
    },
  )
})

test('fetchLogisticsProposal fetches single proposal by ID', async () => {
  let capturedUrl = ''

  const mockFetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input)
    return new Response(JSON.stringify(SAMPLE_PROPOSAL), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  const prop = await fetchLogisticsProposal('prop-20261018-001', mockFetch)
  assert.equal(capturedUrl, '/api/logistics/proposals/prop-20261018-001')
  assert.equal(prop.id, 'prop-20261018-001')
  assert.equal(prop.target_schedule_id, 'sch-002')
})

test('fetchLogisticsProposal rejects empty proposal ID', async () => {
  await assert.rejects(
    async () => {
      await fetchLogisticsProposal('   ')
    },
    (err: unknown) => {
      assert(err instanceof LogisticsApiError)
      assert.equal(err.status, 400)
      assert.match(err.message, /Proposal ID is required/)
      return true
    },
  )
})

test('fetchLogisticsProposal handles 404 not found', async () => {
  const mockFetch = (async () => {
    return new Response(JSON.stringify({ detail: 'Proposal prop-999 not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  await assert.rejects(
    async () => {
      await fetchLogisticsProposal('prop-999', mockFetch)
    },
    (err: unknown) => {
      assert(err instanceof LogisticsApiError)
      assert.equal(err.status, 404)
      return true
    },
  )
})

test('INVARIANT: logistics-client exports NO mutation methods', () => {
  const exportedKeys = Object.keys(logisticsClient)
  for (const key of exportedKeys) {
    const lower = key.toLowerCase()
    assert.equal(
      lower.includes('approve') || lower.includes('reject') || lower.includes('post') || lower.includes('mutate'),
      false,
      `Unsafe mutation export detected in read-only logistics-client: '${key}'`,
    )
  }
})

test('INVARIANT: Next.js route proxy exports exclusively GET and disables caching', () => {
  const routeExports = proxyRoute as Record<string, unknown>

  assert.equal(typeof routeExports.GET, 'function', 'Route must export GET handler')
  assert.equal(routeExports.POST, undefined, 'Route must NOT export POST handler')
  assert.equal(routeExports.PUT, undefined, 'Route must NOT export PUT handler')
  assert.equal(routeExports.PATCH, undefined, 'Route must NOT export PATCH handler')
  assert.equal(routeExports.DELETE, undefined, 'Route must NOT export DELETE handler')

  assert.equal(routeExports.dynamic, 'force-dynamic', 'Route must force dynamic execution')
  assert.equal(routeExports.revalidate, 0, 'Route revalidate must be 0')
})
