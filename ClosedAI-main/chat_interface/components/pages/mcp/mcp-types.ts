import type { LucideIcon } from "lucide-react"

export type ServerType = "HTTP" | "SSE" | "Stdio" | "WebSocket"
export type Health = "healthy" | "degraded" | "unknown" | "error"
export type ToolPermission = "allow" | "deny" | "ask"
export type LogStatus = "default" | "success" | "warning" | "error"
/** Real setup state of an installed server: "needs-setup" when credentials or
 *  an OAuth session are still missing, "ready" when it is authenticated. */
export type McpSetupStatus = "needs-setup" | "ready"

export interface McpTool {
  name: string
  description: string
  enabled: boolean
  permission: ToolPermission
  calls24h: number
}

export interface EnvVar {
  key: string
  value: string
  secret: boolean
}

export interface EventLogItem {
  id: string
  title: string
  detail?: string
  time: string
  ts: number
  status: LogStatus
  iconName: string
}

export type HistoryKind = "connect" | "disconnect" | "reconnect" | "error" | "config" | "auth"

export interface HistoryEvent {
  id: string
  kind: HistoryKind
  title: string
  detail: string
  time: string
  ts: number
}

export interface McpConnection {
  id: string
  name: string
  description: string
  connected: boolean
  serverType: ServerType
  url: string
  auth: string
  authConfigured: boolean
  authTokenPreview?: string
  envVars: EnvVar[]
  tools: McpTool[]
  category: string
  latencyMs: number
  health: Health
  lastUsed: string
  created: string
  icon: LucideIcon
  uptimePercent: number
  lastHealthCheck: string
  errorCount24h: number
  latencyTrend: "up" | "down" | "stable"
  totalCalls: number
  calls24h: number
  serverVersion: string
  protocolVersion: string
  errorMessage?: string
  eventLog: EventLogItem[]
  history: HistoryEvent[]
  /** Raw backend server config (settings.mcp_config entry) — used to build
   *  probe requests. Never rendered. */
  config?: Record<string, unknown>
  /** True when the server still needs credentials/OAuth before it is usable:
   *  unresolved ${VAR} secrets from its marketplace template, or an OAuth2
   *  server without a persisted session. Drives the "Setup needed" state. */
  setupNeeded: boolean
  /** ${VAR} names referenced by this server's template that have no global
   *  secret stored yet. Empty for custom servers (not template-backed). */
  missingSecrets: string[]
  /** For OAuth2 servers whose marketplace template declares one (see
   *  SetupAuthConfig.verify_tool_call): a safe read-only tool call to force
   *  during Re-authorize, so providers that only gate individual tool calls
   *  (not tools/list) actually obtain a token instead of reporting success
   *  from an unauthenticated tools/list alone. Undefined for servers with no
   *  such requirement (most non-Google/Slack OAuth providers). */
  verifyToolCall?: { name: string; arguments?: Record<string, unknown> }
  /** True for system-provided built-in MCPs (e.g. hr-mcp) that cannot be uninstalled. */
  isBuiltin?: boolean
  origin?: "builtin" | "marketplace" | "custom"
}

/** Setup field types rendered by the dynamic setup form. */
export type SetupFieldType = "text" | "password" | "textarea" | "select" | "boolean"

/** A single field in an integration's dynamic setup schema. */
export interface SetupField {
  name: string
  label: string
  type: SetupFieldType
  secret?: boolean
  required?: boolean
  placeholder?: string
  hint?: string
  options?: string[]
}

/** Auth config of a dynamic setup schema — drives which auth UI renders.
 *
 *  OAuth app credentials (client ID/secret) and redirect URIs are backend
 *  deployment configuration, never end-user input — they live in the
 *  backend's OAuth provider config (see
 *  HRAgent_Main/mcp_integration/oauth_provider_config.py) and are never sent
 *  to or requested by the frontend. */
export interface SetupAuthConfig {
  /** "oauth2" → Connect-with-… flow; "token" → one secret field; "env" → fields only; "none". */
  method: "oauth2" | "token" | "env" | "none"
  label?: string
  /** For method="token": the ${VAR} name the value substitutes into. */
  token_field?: string
  hint?: string
  /** For method="oauth2": the backend OAuth provider (e.g. "google",
   *  "slack") this integration's app credentials come from. Absent when the
   *  provider needs no pre-registered app (dynamic client registration,
   *  e.g. Linear/Jira) — those are always ready to connect. */
  provider?: string
  /** For method="oauth2" with `provider` set: whether an administrator has
   *  configured that provider's app credentials on the backend. False means
   *  Connect must be blocked with a clear "needs backend configuration"
   *  message instead of attempting (and failing) dynamic client
   *  registration against a provider that doesn't support it. */
  provider_configured?: boolean
  /** For method="oauth2": a safe read-only tool to invoke once tools are
   *  listed, so servers that only gate individual tool calls (not
   *  tools/list) still trigger a real auth challenge during setup instead
   *  of reporting "connected" without ever obtaining a token. */
  verify_tool_call?: { name: string; arguments?: Record<string, unknown> }
}

/** Backend-served dynamic setup schema for an MCP integration. */
export interface McpSetupSchema {
  auth?: SetupAuthConfig
  fields?: SetupField[]
  instructions?: string
}

export interface LibraryServer {
  id: string
  name: string
  description: string
  serverType: ServerType
  category: string
  url: string
  auth: string
  tools: string[]
  icon: LucideIcon
  docUrl?: string
  /** Install coordinates from the backend marketplace catalog. */
  source?: string
  ref?: string | null
  repo_path?: string | null
  /** True when the catalog entry is an MCP integration (Phase 3-4). */
  mcp?: boolean
  /** Auth method label exposed by the catalog, e.g. "OAuth 2.0". */
  authentication?: string
  /** True when the plugin is installed (backend catalog truth). */
  installed?: boolean
  /** Dynamic setup schema for the integration (from the backend catalog). */
  setup?: McpSetupSchema
  /** The integration's .mcp.json "mcpServers" templates (from the catalog). */
  servers?: Record<string, unknown>
}

export const SERVER_TYPES: ServerType[] = ["HTTP", "SSE", "Stdio", "WebSocket"]
export const AUTH_METHODS = ["None", "API Key", "Bearer Token", "OAuth 2.0"]
export const TYPE_FILTERS = ["All types", ...SERVER_TYPES]
export const CATEGORY_FILTERS = [
  "All categories",
  "Engineering",
  "Data",
  "Research",
  "System",
  "Communication",
  "Productivity",
  "Custom",
]
export const STATUS_FILTERS = ["All", "Connected", "Disconnected", "Degraded", "Error"]
export const SORT_OPTIONS = ["Name", "Latency", "Last used", "Errors (24h)", "Tools"]

export const HEALTH_META: Record<Health, { label: string; className: string; tone: "success" | "warning" | "error" | "neutral" }> = {
  healthy: { label: "Healthy", className: "text-emerald-400", tone: "success" },
  degraded: { label: "Degraded", className: "text-amber-400", tone: "warning" },
  unknown: { label: "Unknown", className: "text-muted-foreground", tone: "neutral" },
  error: { label: "Error", className: "text-red-400", tone: "error" },
}

export const PERMISSION_META: Record<ToolPermission, { label: string; className: string; tone: "success" | "error" | "warning" }> = {
  allow: { label: "Allowed", className: "text-emerald-400", tone: "success" },
  deny: { label: "Denied", className: "text-muted-foreground", tone: "error" },
  ask: { label: "Ask", className: "text-amber-400", tone: "warning" },
}

export function toolPermissionLabel(p: ToolPermission): string {
  return PERMISSION_META[p].label
}
