/**
 * logistics-client.ts: Typed client for the Gurt Logistics HITL Proposal Service.
 *
 * Consumes the Next.js read-only proxy (/api/logistics/proposals) which forwards
 * requests server-to-server to the Python FastAPI backend.
 *
 * INVARIANTS:
 * 1. Read-Only Boundary: Exposes only query functions (fetchLogisticsProposals,
 *    fetchLogisticsProposal). Never exports mutation methods.
 * 2. Strict Type Fidelity: Fields match actual FastAPI Pydantic response models
 *    (ProposalSummaryResponse, ProposalListResponse) in logistics_router.py.
 * 3. No Inferred Authorization: Does not infer approval, confirmation, or identity
 *    from missing or ambiguous fields.
 * 4. Error Handling: Normalizes HTTP and network errors into structured LogisticsApiError
 *    instances without leaking server secrets.
 */

export type ProposalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export interface ProposedChange {
  record_id?: string
  record_type?: string
  field: string
  before?: unknown
  after?: unknown
  reason?: string
  [key: string]: unknown
}

export interface ProposalImpact {
  conflicts_resolved?: Array<string | { id?: string; title?: string; [key: string]: unknown }>
  conflicts_created?: Array<string | { id?: string; title?: string; [key: string]: unknown }>
  affected_sessions?: Array<string | { id?: string; title?: string; [key: string]: unknown }>
  briefings_invalidated?: Array<string | { role?: string; reason?: string; [key: string]: unknown }>
  risk_level?: string
  notes?: string
  [key: string]: unknown
}

export interface LogisticsProposal {
  id: string
  event_id: string
  target_schedule_id: string
  title: string
  description: string
  status: string
  persisted_status: string
  effective_status: string
  is_expired: boolean
  is_stale: boolean
  proposed_changes: ProposedChange[]
  impact: ProposalImpact
  required_confirmations: string[]
  created_at: string
  expires_at: string
  baseline_version: number
  baseline_fingerprint: string
  rejection_reason?: string | null
  executed_at?: string | null
  audit_event_id?: string | null
  proposal_hash?: string | null
  created_by?: string | null
}

export interface ProposalListResponse {
  event_id: string
  total: number
  proposals: LogisticsProposal[]
}

export interface ListProposalsQuery {
  event_id?: string
  status?: string
}

export class LogisticsApiError extends Error {
  readonly status: number
  readonly detail?: string

  constructor(message: string, status = 500, detail?: string) {
    super(message)
    this.name = 'LogisticsApiError'
    this.status = status
    this.detail = detail
  }
}

/**
 * Fetch a list of schedule change proposals from the read-only logistics API.
 */
export async function fetchLogisticsProposals(
  query: ListProposalsQuery = {},
  customFetch: typeof fetch = fetch,
): Promise<ProposalListResponse> {
  const params = new URLSearchParams()
  if (query.event_id?.trim()) params.set('event_id', query.event_id.trim())
  if (query.status?.trim()) params.set('status', query.status.trim())

  const queryString = params.toString()
  const endpoint = `/api/logistics/proposals${queryString ? `?${queryString}` : ''}`

  let res: Response
  try {
    res = await customFetch(endpoint, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
  } catch (err) {
    throw new LogisticsApiError(
      `Network error connecting to logistics service: ${err instanceof Error ? err.message : String(err)}`,
      503,
    )
  }

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.error || data?.detail || `HTTP ${res.status}`
    throw new LogisticsApiError(
      `Failed to list logistics proposals: ${detail}`,
      res.status,
      typeof detail === 'string' ? detail : undefined,
    )
  }

  if (!data || typeof data !== 'object' || !Array.isArray(data.proposals)) {
    throw new LogisticsApiError('Invalid response payload from logistics service', 502)
  }

  return data as ProposalListResponse
}

/**
 * Fetch a single schedule change proposal by its unique ID.
 */
export async function fetchLogisticsProposal(
  proposalId: string,
  customFetch: typeof fetch = fetch,
): Promise<LogisticsProposal> {
  const trimmedId = proposalId?.trim()
  if (!trimmedId) {
    throw new LogisticsApiError('Proposal ID is required', 400)
  }

  const endpoint = `/api/logistics/proposals/${encodeURIComponent(trimmedId)}`

  let res: Response
  try {
    res = await customFetch(endpoint, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
  } catch (err) {
    throw new LogisticsApiError(
      `Network error connecting to logistics service: ${err instanceof Error ? err.message : String(err)}`,
      503,
    )
  }

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.error || data?.detail || `HTTP ${res.status}`
    throw new LogisticsApiError(
      `Failed to fetch logistics proposal '${trimmedId}': ${detail}`,
      res.status,
      typeof detail === 'string' ? detail : undefined,
    )
  }

  if (!data || typeof data !== 'object' || !data.id) {
    throw new LogisticsApiError('Invalid proposal detail payload from logistics service', 502)
  }

  return data as LogisticsProposal
}
