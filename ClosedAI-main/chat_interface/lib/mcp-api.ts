/* Client for the HRAgents backend, reached exclusively through the Next.js
 * proxy routes (app/api/{mcp,plugins,settings}/[...path]) so the session API
 * key stays server-side. Every status the UI renders ("Connected", "Healthy",
 * tool lists, catalog availability) must come from these responses — never
 * from local fiction.
 *
 * Settings are fetched with X-Expose-Secrets: encrypted so secret env/auth
 * values round-trip as Fernet ciphertext; the backend MCP probe decrypts them
 * before connecting (see mcp_integration/config.py:with_decrypted_secrets).
 */

import type { McpConnection } from "@/components/pages/mcp/mcp-types"

/* ------------------------------------------------------------------ */
/*  Types (mirrors the backend request/response models)                */
/* ------------------------------------------------------------------ */

export interface McpServerConfig {
  transport?: "stdio" | "http" | "streamable-http" | "sse"
  url?: string
  command?: string
  args?: string[]
  env?: Record<string, string | null>
  cwd?: string
  description?: string
  icon?: string
  timeout?: number
  sse_read_timeout?: number
  keep_alive?: boolean
  headers?: Record<string, string | null>
  auth?: {
    strategy: string
    value?: string | null
    header_name?: string | null
    username?: string | null
    password?: string | null
    authentication?: unknown
    state?: unknown
  } | null
  // Per-tool permission overrides: tool_name -> "allow" | "deny" | "ask"
  tool_permissions?: Record<string, "allow" | "deny" | "ask">
}

export interface SettingsResponse {
  agent_settings: {
    mcp_config?: Record<string, McpServerConfig>
    [key: string]: unknown
  }
  conversation_settings?: Record<string, unknown>
  llm_api_key_is_set?: boolean
  active_profile?: string | null
  active_agent_profile_id?: string | null
  misc_settings?: Record<string, unknown>
}

export type McpTestServerSpec =
  | { type: "stdio"; command: string; args?: string[]; env?: Record<string, string>; cwd?: string; auth?: McpServerConfig["auth"] }
  | {
      type: "http" | "sse" | "streamable-http"
      url: string
      headers?: Record<string, string>
      api_key?: string
      auth?: McpServerConfig["auth"]
      timeout?: number
    }

export interface McpTestRequest {
  name?: string
  server: McpTestServerSpec
  timeout?: number
  tool_call?: { name: string; arguments?: Record<string, unknown> }
}

export type McpTestResponse =
  | {
      ok: true
      tools: { name: string; description?: string }[]
      tool_result?: { is_error: boolean; text: string }
      oauth_state?: Record<string, unknown> | null
    }
  | { ok: false; error: string; error_kind: "timeout" | "connection" | "unknown" }

export interface OAuthStartResponse {
  ok: boolean
  job_id?: string
  authorization_url?: string | null
  error?: string | null
  error_kind?: "timeout" | "connection" | "unknown" | null
}

export interface OAuthStatusResponse {
  ok: boolean
  status: "pending" | "authorizing" | "succeeded" | "failed"
  job_id: string
  authorization_url?: string | null
  callback_ready?: boolean
  tools?: { name: string; description?: string }[] | null
  oauth_state?: Record<string, unknown> | null
  error?: string | null
  error_kind?: "timeout" | "connection" | "unknown" | null
}

export interface InstalledPlugin {
  name: string
  version: string
  description: string
  enabled: boolean
  source: string
  resolved_ref?: string | null
  repo_path?: string | null
  installed_at: string
  install_path: string
  skills?: { name: string; description?: string | null }[] | null
  files?: string[] | null
}

export interface MarketplacePluginInfo {
  name: string
  description?: string | null
  source: string
  ref?: string | null
  repo_path?: string | null
  installed: boolean
  path?: string | null
  skills?: { name: string; description?: string | null }[] | null
  files?: string[] | null
  /** Integration metadata (bundled MCP marketplace). */
  category?: string | null
  authentication?: string | null
  tools?: string[]
  mcp?: boolean
  /** Dynamic setup schema (auth method + fields) for the integration UI form. */
  setup?: Record<string, unknown> | null
  /** The integration's .mcp.json "mcpServers" templates. */
  servers?: Record<string, unknown> | null
}

export interface SecretItem {
  name: string
  description?: string | null
}

/* ------------------------------------------------------------------ */
/*  Low-level fetch helpers                                            */
/* ------------------------------------------------------------------ */

const ENCRYPTED_EXPOSE = { "X-Expose-Secrets": "encrypted" } as const

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error((data as { error?: string } | null)?.error || `Request failed: ${res.status}`)
  }
  return data as T
}

function jsonInit(method: string, body: unknown, headers?: Record<string, string>): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

/* ------------------------------------------------------------------ */
/*  Settings + secrets                                                 */
/* ------------------------------------------------------------------ */

export async function getSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>("/api/settings", { headers: { ...ENCRYPTED_EXPOSE } })
}

export async function patchSettings(body: {
  agent_settings_diff?: { mcp_config?: Record<string, McpServerConfig | null> }
  misc_settings_diff?: Record<string, unknown>
}): Promise<SettingsResponse> {
  return request<SettingsResponse>("/api/settings", jsonInit("PATCH", body))
}

export async function listSecrets(): Promise<{ secrets: SecretItem[] }> {
  return request<{ secrets: SecretItem[] }>("/api/settings/secrets")
}

export async function setSecret(name: string, value: string, description?: string): Promise<SecretItem> {
  return request<SecretItem>("/api/settings/secrets", jsonInit("PUT", { name, value, description }))
}

export async function deleteSecret(name: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/api/settings/secrets/${encodeURIComponent(name)}`, { method: "DELETE" })
}

/* ------------------------------------------------------------------ */
/*  MCP probe + OAuth                                                  */
/* ------------------------------------------------------------------ */

export async function testServer(requestBody: McpTestRequest): Promise<McpTestResponse> {
  return request<McpTestResponse>("/api/mcp/test", jsonInit("POST", requestBody))
}

export async function oauthStart(requestBody: McpTestRequest): Promise<OAuthStartResponse> {
  return request<OAuthStartResponse>("/api/mcp/oauth/start", jsonInit("POST", requestBody))
}

export async function oauthStatus(jobId: string): Promise<OAuthStatusResponse> {
  return request<OAuthStatusResponse>(`/api/mcp/oauth/status/${encodeURIComponent(jobId)}`)
}

/* ------------------------------------------------------------------ */
/*  Plugins                                                            */
/* ------------------------------------------------------------------ */

export async function installedPlugins(): Promise<{ plugins: InstalledPlugin[] }> {
  return request<{ plugins: InstalledPlugin[] }>("/api/plugins/installed")
}

export async function installPlugin(
  source: string,
  ref?: string,
  repo_path?: string,
  force = false,
): Promise<InstalledPlugin> {
  return request<InstalledPlugin>("/api/plugins/install", jsonInit("POST", { source, ref, repo_path, force }))
}

export async function uninstallPlugin(name: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/plugins/installed/${encodeURIComponent(name)}`, { method: "DELETE" })
}

export async function togglePlugin(name: string, enabled: boolean): Promise<{ name: string; enabled: boolean }> {
  return request<{ name: string; enabled: boolean }>(
    `/api/plugins/installed/${encodeURIComponent(name)}`,
    jsonInit("PATCH", { enabled }),
  )
}

export async function refreshPlugin(name: string): Promise<{ message: string; plugin: InstalledPlugin }> {
  return request<{ message: string; plugin: InstalledPlugin }>(
    `/api/plugins/installed/${encodeURIComponent(name)}/refresh`,
    { method: "POST" },
  )
}

export async function marketplaceCatalog(): Promise<{ plugins: MarketplacePluginInfo[] }> {
  return request<{ plugins: MarketplacePluginInfo[] }>("/api/plugins/marketplace")
}

export async function searchRegistry(q: string): Promise<any> {
  return request<any>(`/api/mcp/registry/search?q=${encodeURIComponent(q)}`)
}

/* ------------------------------------------------------------------ */
/*  Server-spec construction (shared by the store and dialogs)         */
/* ------------------------------------------------------------------ */

/** Build the POST /api/mcp/test `server` payload from a connection. */
export function buildTestServerSpec(conn: McpConnection): McpTestServerSpec | null {
  const env = envVarMap(conn.envVars)
  if (conn.serverType === "Stdio" || (conn.config && "command" in conn.config)) {
    const configCommand = conn.config?.command
    const command =
      typeof configCommand === "string" && configCommand ? configCommand : conn.url.replace(/^stdio:\/\//, "")
    if (!command) return null
    return {
      type: "stdio",
      command,
      args: (conn.config?.args as string[] | undefined) ?? [],
      ...(env ? { env } : {}),
    }
  }

  // Remote transports: streamable-http -> http (normalized by the backend).
  const type = conn.serverType === "SSE" ? "sse" : "http"
  if (!conn.url) return null
  const remote: Record<string, unknown> = { type, url: conn.url }
  const headers = conn.config?.headers
  if (headers && typeof headers === "object" && Object.keys(headers).length > 0) {
    remote.headers = Object.fromEntries(Object.entries(headers).filter(([, v]) => v != null))
  }
  const apiKey = conn.auth === "API Key" ? authValue(conn) : undefined
  if (apiKey) remote.api_key = apiKey
  // Carry the saved auth (bearer/basic/oauth2 state) into the probe so OAuth
  // servers can be tested with their persisted session.
  const savedAuth = conn.config?.auth
  if (savedAuth && typeof savedAuth === "object" && Object.keys(savedAuth).length > 0) {
    remote.auth = savedAuth
  }
  return remote as McpTestServerSpec
}

function authValue(conn: McpConnection): string | undefined {
  const auth = conn.config?.auth
  const v = auth && typeof auth === "object" ? (auth as { value?: unknown }).value : undefined
  return typeof v === "string" && v.length > 0 ? v : undefined
}

function envVarMap(envVars: { key: string; value: string }[]): Record<string, string> | undefined {
  const entries = envVars.filter((e) => e.key.trim() !== "" && e.value !== "")
  if (entries.length === 0) return undefined
  return Object.fromEntries(entries.map((e) => [e.key.trim(), e.value]))
}
