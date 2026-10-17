/* Shared helpers for the MCP management UI.
 *
 * Moved out of components/pages/mcp/mcp-data.ts (deleted) so no fictional
 * seed data lives next to real utilities. Anything the UI renders that is not
 * derived from the backend must come through here or mcp-types.ts.
 */

export function rel(minutesAgo: number): string {
  if (minutesAgo < 1) return "just now"
  if (minutesAgo < 60) return `${minutesAgo} min ago`
  const hours = Math.floor(minutesAgo / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.floor(hours / 24)
  return `${days} d ago`
}

export function timeAgo(ts: number): string {
  const diff = Math.max(0, Date.now() - ts)
  const mins = Math.floor(diff / 60_000)
  return rel(mins)
}

export function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID()
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}
