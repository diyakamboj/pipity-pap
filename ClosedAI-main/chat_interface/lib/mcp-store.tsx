"use client"

import { createContext, useContext, useState, useMemo, useCallback, useEffect, type ReactNode } from "react"
import { toast } from "sonner"
import { uid, timeAgo } from "@/lib/mcp-util"
import {
  BarChart3,
  Boxes,
  Bug,
  Database,
  FileText,
  FolderOpen,
  GitBranch,
  Mail,
  MessageSquare,
  Plug,
  Search as SearchIcon,
  Terminal,
  Zap,
  type LucideIcon,
} from "lucide-react"
import * as mcpApi from "@/lib/mcp-api"
import type {
  EnvVar,
  Health,
  LibraryServer,
  LogStatus,
  McpConnection,
  McpTool,
  ServerType,
} from "@/components/pages/mcp/mcp-types"

/* ------------------------------------------------------------------ */
/*  Server-config -> McpConnection mapping (backend is source of truth) */
/* ------------------------------------------------------------------ */

const TRANSPORT_TO_TYPE: Record<string, ServerType> = {
  stdio: "Stdio",
  http: "HTTP",
  "streamable-http": "HTTP",
  sse: "SSE",
}

const AUTH_STRATEGY_LABEL: Record<string, string> = {
  none: "None",
  api_key: "API Key",
  bearer: "Bearer Token",
  basic: "Basic",
  header: "Header",
  oauth2: "OAuth 2.0",
}

function iconForName(name: string): LucideIcon {
  const n = name.toLowerCase()
  if (/(github|git)/.test(n)) return GitBranch
  if (/(postgres|sql|mysql|database|db)/.test(n)) return Database
  if (/(slack|chat|message|teams)/.test(n)) return MessageSquare
  if (/(notion|doc|wiki)/.test(n)) return FileText
  if (/(gmail|google|mail|outlook|email)/.test(n)) return Mail
  if (/(jira|atlassian|linear|ticket)/.test(n)) return Bug
  if (/(linear|box)/.test(n)) return Boxes
  if (/(drive|storage|folder|onedrive)/.test(n)) return FolderOpen
  if (/(search|web)/.test(n)) return SearchIcon
  if (/(sentry|error|monitor)/.test(n)) return Zap
  if (/(posthog|analytics|graph|chart)/.test(n)) return BarChart3
  if (/(fs|filesystem|shell|terminal)/.test(n)) return Terminal
  return Plug
}

/** Derive a masked auth preview for the UI. Never renders raw secret
 *  material — a `${VAR}` secret placeholder shows as a label, and real
 *  values are truncated to a head/tail preview like "abcd…wxyz". */
function authPreview(server: mcpApi.McpServerConfig): string {
  const auth = server.auth
  if (!auth) return ""
  const value = auth.value ?? ""
  if (auth.strategy === "oauth2") return auth.state ? "OAuth session" : "Not configured"
  if (auth.strategy === "basic") return auth.username ? `${auth.username}:••••` : ""
  if (!value) return ""
  if (value.startsWith("${") && value.endsWith("}")) return "Secret reference"
  if (value.length <= 8) return "••••••"
  return `${value.slice(0, 4)}…${value.slice(-4)}`
}

/** Collected values from a dynamic setup form, keyed by ${VAR} name. */
export interface McpSetupValues {
  /** Field name -> value (schema fields + token_field). */
  values: Record<string, string | boolean>
  /** Persisted OAuth session for method="oauth2" servers (from oauthStatus). */
  oauthState?: Record<string, unknown> | null
  /** True for OAuth integrations (stores client fields per-server in env). */
  isOAuth?: boolean
}

/** Substitute `${VAR}` placeholders in a server template with collected values.
 *  Unknown placeholders are left intact (they resolve from global secrets at
 *  conversation build time). */
export function substitutePlaceholders(obj: Record<string, unknown>, values: Record<string, string | boolean>): void {
  for (const key of Object.keys(obj)) {
    const val = obj[key]
    if (typeof val === "string") {
      obj[key] = val.replace(/\$\{([A-Z0-9_]+)\}/g, (match, name: string) =>
        typeof values[name] === "string" ? (values[name] as string) : match,
      )
    } else if (val && typeof val === "object") {
      substitutePlaceholders(val as Record<string, unknown>, values)
    }
  }
}


function buildConnection(name: string, server: mcpApi.McpServerConfig, existing?: McpConnection): McpConnection {
  const auth = server.auth
  const authStrategy = auth?.strategy ?? "none"
  const authConfigured = Boolean(
    auth && (typeof auth.value === "string" ? auth.value.length > 0 : Boolean(auth.password || auth.state)),
  )
  // An OAuth2 server that never completed a browser flow has no usable session
  // (auth.state) — it genuinely needs setup regardless of any ciphertext value.
  const oauthUnconfigured = authStrategy === "oauth2" && Boolean(auth) && !auth?.state && !auth?.value
  const transport = server.transport
  const serverType = (transport ? TRANSPORT_TO_TYPE[transport] : undefined) ?? "HTTP"
  const url = server.url ?? (serverType === "Stdio" && server.command ? `stdio://${server.command}` : "")

  const envVars: EnvVar[] = server.env
    ? Object.entries(server.env).map(([key, value]) => ({
        key,
        value: typeof value === "string" ? value : "",
        // Every entry in settings.env is a SecretStr; ciphertext or ${VAR}
        // placeholders are never shown as plaintext.
        secret: true,
      }))
    : []

  // Preserve per-session probe results for servers that already existed.
  const prev = existing?.id === name ? existing : undefined

  // Merge tool permissions from server config into tool list
  const toolsWithPermissions = (prev?.tools ?? []).map((tool) => {
    const permissionOverride = server.tool_permissions?.[tool.name]
    return {
      ...tool,
      permission: permissionOverride ?? tool.permission ?? "allow",
    }
  })

  return {
    id: name,
    name,
    description: server.description ?? `${name} MCP server`,
    // Never faked: a server is "connected" only when it does not need setup.
    // Reachability (whether it actually responds) is tracked separately by
    // `health` from probe results — see applySetupContext for the ${VAR}-ref pass.
    // Must not fall back to `existing?.connected`: a connection that just
    // finished setup (oauthUnconfigured flips true -> false) would otherwise
    // inherit its own stale pre-setup `connected: false` from `existing`,
    // since `false ?? true` is `false`, not `true` — leaving it stuck looking
    // disconnected until something else forces a re-render.
    connected: !oauthUnconfigured,
    setupNeeded: oauthUnconfigured,
    missingSecrets: [],
    serverType,
    url,
    auth: AUTH_STRATEGY_LABEL[authStrategy] ?? "None",
    authConfigured,
    authTokenPreview: authPreview(server),
    envVars,
    tools: toolsWithPermissions,
    category: "Custom",
    latencyMs: prev?.latencyMs ?? 0,
    health: prev?.health ?? "unknown",
    lastUsed: prev?.lastUsed ?? "never",
    created: prev?.created ?? "",
    icon: prev?.icon ?? iconForName(name),
    uptimePercent: 0,
    lastHealthCheck: prev?.lastHealthCheck ?? "never",
    errorCount24h: 0,
    latencyTrend: "stable",
    totalCalls: 0,
    calls24h: 0,
    serverVersion: prev?.serverVersion ?? "",
    protocolVersion: prev?.protocolVersion ?? "",
    errorMessage: prev?.errorMessage,
    eventLog: prev?.eventLog ?? [],
    history: prev?.history ?? [],
    config: server as unknown as Record<string, unknown>,
  }
}

/** Convert an McpConnection back into a settings.mcp_config server entry. */
function connectionToConfig(conn: McpConnection): mcpApi.McpServerConfig {
  const config: mcpApi.McpServerConfig = {
    description: conn.description,
  }
  if (conn.serverType === "Stdio") {
    config.transport = "stdio"
    const command = typeof conn.config?.command === "string" ? conn.config.command : conn.url.replace(/^stdio:\/\//, "")
    if (command) config.command = command
    const args = conn.config?.args
    if (Array.isArray(args)) config.args = args as string[]
  } else {
    config.transport = conn.serverType === "SSE" ? "sse" : "http"
    config.url = conn.url
    const headers = conn.config?.headers
    if (headers && typeof headers === "object") {
      config.headers = headers as Record<string, string | null>
    }
  }
  const env: Record<string, string | null> = {}
  for (const e of conn.envVars) {
    if (e.key.trim()) env[e.key.trim()] = e.value || null
  }
  if (Object.keys(env).length > 0) config.env = env

  const strategy = authStrategyFor(conn.auth)
  // Preserve the full saved auth (value, oauth2 state, basic username/password,
  // api_key header_name, …) so saving a connection never drops what the OAuth
  // flow or auth UI persisted. Only the strategy is re-derived from the label.
  const prevAuth = conn.config?.auth as Record<string, unknown> | null | undefined
  config.auth = { strategy, ...(prevAuth ?? {}) }

  // Include per-tool permissions if they differ from defaults
  const toolPermissions: Record<string, "allow" | "deny" | "ask"> = {}
  for (const tool of conn.tools) {
    if (tool.permission && tool.permission !== "allow") {
      toolPermissions[tool.name] = tool.permission
    }
  }
  if (Object.keys(toolPermissions).length > 0) {
    config.tool_permissions = toolPermissions
  }

  return config
}

function authStrategyFor(authLabel: string): string {
  switch (authLabel) {
    case "API Key":
      return "api_key"
    case "Bearer Token":
      return "bearer"
    case "Basic":
      return "basic"
    case "Header":
      return "header"
    case "OAuth 2.0":
      return "oauth2"
    default:
      return "none"
  }
}

export const BUILTIN_CONNECTIONS: McpConnection[] = [
  {
    id: "hr",
    name: "HR Core Data",
    description: "Built-in HR data services — employee profiles, PTO balances, org charts, compensation, and policy search.",
    connected: true,
    setupNeeded: false,
    missingSecrets: [],
    serverType: "Stdio",
    url: "stdio://hr_mcp/server.py",
    auth: "None",
    authConfigured: true,
    envVars: [],
    tools: [
      { name: "employee_lookup", description: "Look up employee details by name or ID", enabled: true, permission: "allow", calls24h: 0 },
      { name: "pto_balance", description: "Retrieve employee PTO balance and accrual info", enabled: true, permission: "allow", calls24h: 0 },
      { name: "org_chart", description: "Fetch org hierarchy (manager, reports, peers)", enabled: true, permission: "allow", calls24h: 0 },
      { name: "benefits_lookup", description: "Look up health, retirement, and insurance benefits", enabled: true, permission: "allow", calls24h: 0 },
      { name: "policy_search", description: "Search company handbook and HR policy documents", enabled: true, permission: "allow", calls24h: 0 },
    ],
    category: "Core HR",
    latencyMs: 8,
    health: "healthy",
    lastUsed: "active",
    created: "System",
    icon: Database,
    uptimePercent: 100,
    lastHealthCheck: "live",
    errorCount24h: 0,
    latencyTrend: "stable",
    totalCalls: 0,
    calls24h: 0,
    serverVersion: "1.0.0",
    protocolVersion: "2024-11-05",
    eventLog: [],
    history: [],
    isBuiltin: true,
    origin: "builtin",
  },
]

/* ------------------------------------------------------------------ */
/*  Setup status (which servers genuinely need credentials)            */
/* ------------------------------------------------------------------ */

/** Collect every `${VAR}` reference from a raw .mcp.json server template.
 *  Works on the catalog's unencrypted template (never on settings, whose
 *  values are SecretStr-ciphertext on the wire). */
function refsFromTemplate(template: Record<string, unknown>): string[] {
  const refs = new Set<string>()
  const scan = (obj: unknown) => {
    if (typeof obj === "string") {
      for (const m of obj.matchAll(/\$\{([A-Z0-9_]+)\}/g)) refs.add(m[1])
    } else if (obj && typeof obj === "object") {
      for (const v of Object.values(obj as Record<string, unknown>)) scan(v)
    }
  }
  if (template.env) scan(template.env)
  if (template.headers) scan(template.headers)
  if (template.auth && typeof template.auth === "object") scan((template.auth as Record<string, unknown>).value)
  return [...refs]
}

/** Refine each connection's setup status using the marketplace template for
 *  that server (raw ${VAR} refs) plus the stored global-secret names. A server
 *  needs setup when any referenced secret is missing, or when its OAuth2 flow
 *  never completed. Custom (non-template) servers only fail the OAuth check —
 *  their credentials live in auth.* which buildConnection already validates. */
function applySetupContext(
  conns: McpConnection[],
  catalog: LibraryServer[],
  secrets: Set<string>,
): McpConnection[] {
  const libByServer = new Map<string, LibraryServer>()
  for (const lib of catalog) {
    for (const serverName of Object.keys(lib.servers ?? {})) libByServer.set(serverName, lib)
  }
  return conns.map((c) => {
    const lib = libByServer.get(c.id)
    const template = lib?.servers?.[c.id] as Record<string, unknown> | undefined
    // A ${VAR} ref only blocks setup if its schema field doesn't explicitly
    // mark itself optional (required: false) -- e.g. microsoft-365's fields
    // all fall back to server-side defaults when left blank, so referencing
    // them in the .mcp.json template alone shouldn't force the user to fill
    // them in before Save & configure will do anything.
    const optionalVars = new Set(
      (lib?.setup?.fields ?? []).filter((f) => f.required === false).map((f) => f.name),
    )
    const missing = template
      ? refsFromTemplate(template).filter((n) => !secrets.has(n) && !optionalVars.has(n))
      : []
    const setupNeeded = missing.length > 0 || c.setupNeeded
    return {
      ...c,
      setupNeeded,
      missingSecrets: missing,
      connected: !setupNeeded && c.connected,
      verifyToolCall: lib?.setup?.auth?.verify_tool_call,
    }
  })
}

/* ------------------------------------------------------------------ */
/*  Probe helpers                                                      */
/* ------------------------------------------------------------------ */

function toolsFromProbe(discovered: { name: string; description?: string }[] | undefined, prev?: McpTool[]): McpTool[] {
  if (!discovered) return []
  return discovered.map((t) => {
    const prior = prev?.find((p) => p.name === t.name)
    return {
      name: t.name,
      description: t.description || prior?.description || "Exposed by the MCP server",
      enabled: prior?.enabled ?? true,
      permission: prior?.permission ?? "allow",
      calls24h: 0,
    }
  })
}

function addEvent(
  c: McpConnection,
  title: string,
  detail: string,
  status: LogStatus,
  iconName: string,
): McpConnection["eventLog"] {
  return [{ id: `e-${uid()}`, title, detail, time: timeAgo(Date.now()), ts: Date.now(), status, iconName }, ...c.eventLog]
}

/* ------------------------------------------------------------------ */
/*  Context                                                            */
/* ------------------------------------------------------------------ */

/** "error" is distinct from "empty": a failed fetch must never be presented
 *  as "you have zero MCP servers" — that's how installed servers appear to
 *  "disappear" on a flaky cold load. Only a genuinely successful fetch that
 *  returned zero configured servers reaches "empty". */
export type DataSource = "loading" | "empty" | "backend" | "error"

interface McpContextValue {
  connections: McpConnection[]
  dataSource: DataSource
  catalog: LibraryServer[]
  catalogLoading: boolean
  /** True when the last catalog refetch failed. `catalog` still holds the
   *  last successfully-loaded entries — never wiped to an empty array. */
  catalogError: boolean
  testingId: string | null
  reconnectingId: string | null
  rotatingId: string | null
  load: () => Promise<void>
  loadCatalog: () => Promise<void>
  toggleConnection: (id: string) => Promise<void>
  testConnection: (id: string) => Promise<void>
  testAllConnections: () => Promise<void>
  reconnectConnection: (id: string) => Promise<void>
  disconnectAll: () => Promise<void>
  deleteConnection: (id: string) => Promise<void>
  duplicateConnection: (conn: McpConnection) => Promise<void>
  upsertConnection: (conn: McpConnection) => Promise<void>
  /** Install a marketplace integration and provision its servers into mcp_config.
   *  Resolves with the provisioned per-server configs (merged), or null on failure. */
  installAndProvision: (lib: LibraryServer, setup: McpSetupValues) => Promise<Record<string, mcpApi.McpServerConfig> | null>
  /** Start a browser-coordinated OAuth flow against a probe spec; returns
   *  job_id. Never takes client id/secret — those are backend deployment
   *  config (see oauth_provider_config.py), resolved server-side. */
  startOAuth: (
    spec: mcpApi.McpTestServerSpec,
    opts?: {
      verifyToolCall?: { name: string; arguments?: Record<string, unknown> }
    },
  ) => Promise<string | null>
  /** Poll an OAuth job until it completes, invoking onSuccess with the session state. */
  completeOAuth: (
    jobId: string,
    onSuccess?: (oauthState: Record<string, unknown>) => void,
  ) => Promise<"ok" | "failed">
  /** Save an OAuth session into an existing connection's server config. */
  persistOAuthState: (connId: string, oauthState: Record<string, unknown>) => Promise<void>
  /** Save an OAuth session into a freshly-provisioned server config (install flow). */
  saveServerAuth: (serverName: string, serverConfig: mcpApi.McpServerConfig, oauthState: Record<string, unknown>) => Promise<void>
  updateTool: (connId: string, toolName: string, patch: Partial<Pick<McpTool, "enabled" | "permission">>) => void
  saveConfig: (connId: string, patch: Partial<Pick<McpConnection, "envVars" | "authConfigured" | "authTokenPreview">>) => Promise<void>
  setApiKey: (id: string, key: string) => Promise<void>
  /** Persist a global secret by name (setup flow). */
  saveSecret: (name: string, value: string) => Promise<void>
  /** Merge a partial patch into a server's settings.mcp_config entry. */
  patchServerConfig: (connId: string, patch: Partial<mcpApi.McpServerConfig>) => Promise<void>
  rotateAuth: (id: string) => Promise<void>
  revokeAuth: (id: string) => Promise<void>
}

const McpContext = createContext<McpContextValue | null>(null)

export function McpProvider({ children }: { children: ReactNode }) {
  const [connections, setConnections] = useState<McpConnection[]>([])
  const [dataSource, setDataSource] = useState<DataSource>("loading")
  const [catalog, setCatalog] = useState<LibraryServer[]>([])
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError, setCatalogError] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [reconnectingId, setReconnectingId] = useState<string | null>(null)
  const [rotatingId, setRotatingId] = useState<string | null>(null)
  // Names of stored global secrets — the source of truth for whether a
  // template's ${VAR} references are resolvable.
  const [secretNames, setSecretNames] = useState<Set<string>>(new Set())

  /* ---------------- settings -> connections ---------------- */

  const load = useCallback(async () => {
    try {
      const [settings, secretsRes] = await Promise.all([
        mcpApi.getSettings(),
        mcpApi.listSecrets().catch(() => ({ secrets: [] })),
      ])
      const config = settings.agent_settings.mcp_config ?? {}
      const secretSet = new Set(secretsRes.secrets.map((s) => s.name))
      setSecretNames(secretSet)
      setConnections((prev) => {
        const prevById = new Map(prev.map((c) => [c.id, c]))
        const base = Object.entries(config).map(([name, server]) => buildConnection(name, server, prevById.get(name)))
        const installed = applySetupContext(base, catalog, secretSet)
        // Ensure built-in MCPs are appended with live status
        const builtin = BUILTIN_CONNECTIONS.map((b) => {
          const prior = prevById.get(b.id)
          return prior ? { ...b, latencyMs: prior.latencyMs, health: prior.health, lastUsed: prior.lastUsed } : b
        })
        return [...installed, ...builtin]
      })
      setDataSource(Object.keys(config).length > 0 || BUILTIN_CONNECTIONS.length > 0 ? "backend" : "empty")
    } catch (error) {
      console.error("Failed to load MCP connections:", error)
      // A fetch failure must never masquerade as "zero servers configured":
      // if a prior load already populated `connections`, keep showing them
      // (this call's catch never touched `connections`) and just surface the
      // failure. Only a cold-start failure — nothing successfully loaded yet
      // — moves to the distinct "error" state instead of "empty".
      setDataSource((prev) => (prev === "backend" ? prev : "error"))
      toast.error(error instanceof Error ? error.message : "Failed to load MCP servers")
    }
  }, [catalog])

  useEffect(() => {
    void load()
  }, [load])

  /* ---------------- catalog (marketplace) ---------------- */

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true)
    try {
      const { plugins } = await mcpApi.marketplaceCatalog()
      setCatalog(
        plugins.map((p) => ({
          id: p.name,
          name: p.name,
          description: p.description ?? "",
          serverType: "HTTP",
          // Real category from the backend catalog (Communication, Development,
          // Databases, Storage, Productivity) — never local fiction.
          category: p.category ?? "Custom",
          url: p.source,
          // Real auth label advertised by the catalog, e.g. "Google OAuth 2.0".
          auth: p.authentication ?? "None",
          tools: p.tools ?? [],
          icon: iconForName(p.name),
          source: p.source,
          ref: p.ref,
          repo_path: p.repo_path,
          mcp: p.mcp ?? true,
          // Backend truth: plugin-installed state + dynamic setup schema +
          // .mcp.json server templates for the integration.
          installed: p.installed,
          setup: (p.setup as LibraryServer["setup"]) ?? undefined,
          servers: (p.servers as LibraryServer["servers"]) ?? undefined,
        })),
      )
      setCatalogError(false)
    } catch (error) {
      console.error("Failed to load marketplace catalog:", error)
      // Never wipe a previously-good catalog on a transient refetch failure
      // (e.g. right after install, while the backend is still busy) — that's
      // how the marketplace appears to drop to "0 servers". Keep whatever
      // was last successfully loaded and surface the failure instead.
      setCatalogError(true)
      toast.error(error instanceof Error ? error.message : "Failed to load MCP marketplace")
    } finally {
      setCatalogLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  /* ---------------- settings writes ---------------- */

  const patchConfig = useCallback(
    async (diff: Record<string, mcpApi.McpServerConfig | null>) => {
      await mcpApi.patchSettings({ agent_settings_diff: { mcp_config: diff } })
      await load()
    },
    [load],
  )

  const toggleConnection = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      if (conn.isBuiltin) {
        toast.info(`${conn.name} is a built-in server and cannot be disabled`)
        return
      }
      try {
        if (conn.connected) {
          await patchConfig({ [id]: null })
          setConnections((prev) => prev.map((c) => (c.id === id ? { ...c, connected: false, health: "unknown" as Health } : c)))
          toast.success(`${conn.name} disconnected`)
        } else {
          await patchConfig({ [id]: connectionToConfig(conn) })
          setConnections((prev) => prev.map((c) => (c.id === id ? { ...c, connected: true } : c)))
          toast.success(`${conn.name} reconnected`)
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to update connection")
      }
    },
    [connections, patchConfig],
  )

  const deleteConnection = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (conn?.isBuiltin) {
        toast.error(`${conn.name} is a built-in server and cannot be uninstalled`)
        return
      }
      try {
        await patchConfig({ [id]: null })
        setConnections((prev) => prev.filter((c) => c.id !== id))
        toast.success("Connection removed")
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to remove connection")
      }
    },
    [connections, patchConfig],
  )

  const disconnectAll = useCallback(async () => {
    const toRemove = connections.filter((c) => c.connected).map((c) => c.id)
    if (toRemove.length === 0) return
    try {
      const diff: Record<string, mcpApi.McpServerConfig | null> = {}
      for (const id of toRemove) diff[id] = null
      await patchConfig(diff)
      setConnections((prev) => prev.map((c) => (c.connected ? { ...c, connected: false, health: "unknown" as Health } : c)))
      toast.success("All servers disconnected")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to disconnect servers")
    }
  }, [connections, patchConfig])

  const duplicateConnection = useCallback(
    async (conn: McpConnection) => {
      try {
        const copy = { ...conn, name: `${conn.name} (Copy)` }
        await patchConfig({ [copy.name]: connectionToConfig(copy) })
        toast.success(`Duplicated "${conn.name}"`)
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to duplicate connection")
      }
    },
    [patchConfig],
  )

  const upsertConnection = useCallback(
    async (conn: McpConnection) => {
      const name = conn.name.trim()
      if (!name) {
        toast.error("Server name is required")
        return
      }
      try {
        await patchConfig({ [name]: connectionToConfig(conn) })
        toast.success(conn.connected ? `${name} connected` : `${name} saved`)
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save connection")
      }
    },
    [patchConfig],
  )

  /* ---------------- install ---------------- */

  const installAndProvision = useCallback(
    async (lib: LibraryServer, setup: McpSetupValues): Promise<Record<string, mcpApi.McpServerConfig> | null> => {
      const servers = lib.servers
      try {
        // 1) Install the plugin unless it is already installed. A stale catalog
        //    flag or a concurrent install surfaces the backend's "already
        //    installed" FileExistsError as a 409 — fall back to refreshing the
        //    existing copy instead of erroring out.
        if (!lib.installed && lib.source) {
          try {
            await mcpApi.installPlugin(lib.source, lib.ref ?? undefined, lib.repo_path ?? undefined)
          } catch (error) {
            if (!/already installed/i.test(error instanceof Error ? error.message : "")) throw error
            try {
              await mcpApi.refreshPlugin(lib.name)
            } catch {
              /* best-effort refresh */
            }
          }
        }

        // 2) Persist every provided value as a global secret so ${VAR}
        //    placeholders in the plugin's ambient .mcp.json resolve at
        //    conversation build time.
        for (const [name, value] of Object.entries(setup.values)) {
          if (typeof value === "string" && value.trim()) {
            try {
              await mcpApi.setSecret(name, value.trim())
            } catch (error) {
              console.warn(`Failed to store secret ${name}:`, error)
            }
          }
        }

        // No server templates — plugin-only install. The integration is added
        // to the catalog as installed; the user configures credentials from the
        // MCP page. Return {} (truthy) so the dialog closes cleanly.
        if (!servers || Object.keys(servers).length === 0) {
          await loadCatalog()
          toast.success(`${lib.name} installed`, {
            description: "Configure credentials from the MCP page",
          })
          return {}
        }

        // 3) Provision each template into settings.mcp_config, substituting
        //    collected values into ${VAR} placeholders (per-server copy) and
        //    merging with any saved config so auth state / permissions survive
        //    a re-install.
        const diff: Record<string, mcpApi.McpServerConfig> = {}
        for (const [serverName, template] of Object.entries(servers)) {
          const server = JSON.parse(JSON.stringify(template)) as mcpApi.McpServerConfig
          substitutePlaceholders(server as unknown as Record<string, unknown>, setup.values)

          // Persist a completed OAuth session into the server's auth.state.
          if (setup.oauthState) {
            server.auth = { strategy: "oauth2", state: setup.oauthState }
          }

          // Merge with the saved config so unrelated per-server settings are kept.
          const existing = connections.find((c) => c.id === serverName)?.config as
            | mcpApi.McpServerConfig
            | undefined
          const merged: mcpApi.McpServerConfig = { ...(existing ?? {}), ...server }
          if (existing?.env || server.env) merged.env = { ...(existing?.env ?? {}), ...(server.env ?? {}) }
          if (existing?.headers || server.headers) {
            merged.headers = { ...(existing?.headers ?? {}), ...(server.headers ?? {}) }
          }
          diff[serverName] = merged
        }

        await patchConfig(diff)
        await loadCatalog()
        toast.success(`${lib.name} installed`, {
          description:
            Object.keys(setup.values).length > 0
              ? "Server configured — test it to discover tools"
              : "Added to MCP servers — set up credentials from the MCP page",
        })
        return diff
      } catch (error) {
        toast.error(error instanceof Error ? error.message : `Failed to install ${lib.name}`)
        return null
      }
    },
    [connections, loadCatalog, patchConfig],
  )

  /* ---------------- OAuth ---------------- */

  const startOAuth = useCallback(
    async (
      spec: mcpApi.McpTestServerSpec,
      opts?: {
        verifyToolCall?: { name: string; arguments?: Record<string, unknown> }
      },
    ) => {
      // Preserve the template's existing `authentication` (notably
      // `provider`, e.g. "google" -- how the backend resolves which
      // deployment-configured OAuth app to use, see
      // oauth_provider_config.py) rather than replacing it outright. The
      // frontend never supplies client_id/secret itself.
      const existingAuth = (spec.auth ?? {}) as Record<string, unknown>
      const existingAuthentication = (existingAuth.authentication ?? {}) as Record<string, unknown>
      spec.auth = {
        strategy: "oauth2",
        authentication: { ...existingAuthentication, type: "oauth" },
      } as NonNullable<mcpApi.McpServerConfig["auth"]>
      try {
        const res = await mcpApi.oauthStart({
          server: spec,
          // Some MCP servers only gate individual tool calls, not
          // tools/list -- without forcing a real call, the job can report
          // "succeeded" without ever obtaining a token. See mcp_router.py's
          // _run_oauth_job for the backend half of this.
          ...(opts?.verifyToolCall ? { tool_call: opts.verifyToolCall } : {}),
        })
        if (res.ok && res.job_id) {
          if (res.authorization_url) window.open(res.authorization_url, "_blank", "noopener,noreferrer")
          return res.job_id
        }
        toast.error(res.error ?? "Failed to start OAuth")
        return null
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to start OAuth")
        return null
      }
    },
    [],
  )

  /** Persist a completed OAuth session into an existing connection's config. */
  const persistOAuthState = useCallback(
    async (connId: string, oauthState: Record<string, unknown>) => {
      const conn = connections.find((c) => c.id === connId)
      if (!conn) return
      const server: mcpApi.McpServerConfig = {
        ...(conn.config as mcpApi.McpServerConfig | undefined),
        auth: { strategy: "oauth2", state: oauthState },
      }
      try {
        await patchConfig({ [connId]: server })
        toast.success(`${conn.name} authenticated`, { description: "OAuth session saved to this server" })
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save OAuth session")
      }
    },
    [connections, patchConfig],
  )

  /** Persist a completed OAuth session into a freshly-provisioned server config. */
  const saveServerAuth = useCallback(
    async (serverName: string, serverConfig: mcpApi.McpServerConfig, oauthState: Record<string, unknown>) => {
      try {
        await patchConfig({ [serverName]: { ...serverConfig, auth: { strategy: "oauth2", state: oauthState } } })
        toast.success(`${serverName} authenticated`, { description: "OAuth session saved to this server" })
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save OAuth session")
      }
    },
    [patchConfig],
  )

  const completeOAuth = useCallback(
    async (jobId: string, onSuccess?: (oauthState: Record<string, unknown>) => void): Promise<"ok" | "failed"> => {
      let authOpened = false
      const poll = async (): Promise<"ok" | "failed"> => {
        let res: mcpApi.OAuthStatusResponse
        try {
          res = await mcpApi.oauthStatus(jobId)
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "OAuth status check failed")
          return "failed"
        }
        if (res.ok && res.status === "succeeded") {
          if (res.oauth_state) onSuccess?.(res.oauth_state)
          return "ok"
        }
        if (res.status === "failed") {
          toast.error(res.error ?? "OAuth failed")
          return "failed"
        }
        // If the backend's OAuth callback server is ready and there's an auth URL
        // that wasn't opened yet (e.g., the initial open failed), retry opening it.
        if (res.callback_ready && res.authorization_url && !authOpened) {
          window.open(res.authorization_url, "_blank", "noopener,noreferrer")
          authOpened = true
        }
        return new Promise<"ok" | "failed">((resolve) => setTimeout(() => void poll().then(resolve), 1500))
      }
      return poll()
    },
    [],
  )

  /* ---------------- probe / test ---------------- */

  const applyProbe = useCallback((conn: McpConnection, spec: mcpApi.McpTestServerSpec, id: string) => {
    setTestingId(id)
    const toastId = `test-${id}`
    toast.loading(`Testing ${conn.name}...`, { id: toastId })
    mcpApi
      .testServer({ name: conn.name, server: spec })
      .then((result) => {
        setConnections((prev) =>
          prev.map((c) =>
            c.id === id
              ? result.ok
                ? {
                    ...c,
                    health: "healthy" as Health,
                    lastHealthCheck: "just now",
                    errorMessage: undefined,
                    tools: toolsFromProbe(result.tools, c.tools),
                    eventLog: addEvent(c, "Connection test passed", `Discovered ${result.tools.length} tool(s)`, "success", "activity"),
                    history: [
                      { id: `h-${uid()}`, kind: "connect" as const, title: "Connected", detail: "Probe succeeded", time: "just now", ts: Date.now() },
                      ...c.history,
                    ],
                  }
                : {
                    ...c,
                    health: "error" as Health,
                    lastHealthCheck: "just now",
                    errorMessage: result.error,
                    eventLog: addEvent(c, "Connection test failed", result.error, "error", "wifi-off"),
                  }
              : c,
          ),
        )
        if (result.ok) toast.success(`${conn.name} responded — ${result.tools.length} tools`, { id: toastId })
        else toast.error(`${conn.name} failed: ${result.error}`, { id: toastId })
      })
      .catch((error) => {
        toast.error(error instanceof Error ? error.message : "Connection test failed", { id: toastId })
      })
      .finally(() => setTestingId(null))
  }, [])

  const testConnection = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      const spec = mcpApi.buildTestServerSpec(conn)
      if (!spec) {
        toast.error("Cannot build a probe from this configuration")
        return
      }
      applyProbe(conn, spec, id)
    },
    [connections],
  )

  const testAllConnections = useCallback(async () => {
    const connected = connections.filter((c) => c.connected && c.url)
    if (connected.length === 0) {
      toast.error("No connected servers to test")
      return
    }
    toast.loading(`Testing ${connected.length} servers...`, { id: "test-all" })
    for (const conn of connected) {
      const spec = mcpApi.buildTestServerSpec(conn)
      if (spec) {
        const result = await mcpApi.testServer({ name: conn.name, server: spec })
        setConnections((prev) =>
          prev.map((c) =>
            c.id === conn.id
              ? result.ok
                ? {
                    ...c,
                    health: "healthy" as Health,
                    lastHealthCheck: "just now",
                    errorMessage: undefined,
                    tools: toolsFromProbe(result.tools, c.tools),
                  }
                : { ...c, health: "error" as Health, lastHealthCheck: "just now", errorMessage: result.error }
              : c,
          ),
        )
      }
    }
    toast.success(`All ${connected.length} servers tested`, { id: "test-all" })
  }, [connections])

  const reconnectConnection = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      const spec = mcpApi.buildTestServerSpec(conn)
      if (!spec) {
        toast.error("Cannot build a probe from this configuration")
        return
      }
      setReconnectingId(id)
      const toastId = `reconnect-${id}`
      toast.loading(`Reconnecting ${conn.name}...`, { id: toastId })
      try {
        const result = await mcpApi.testServer({ name: conn.name, server: spec })
        if (result.ok) {
          // Reconnect = probe + ensure the server is present in the persisted config.
          if (!conn.connected) await patchConfig({ [id]: connectionToConfig(conn) })
          setConnections((prev) =>
            prev.map((c) =>
              c.id === id
                ? {
                    ...c,
                    connected: true,
                    health: "healthy" as Health,
                    lastHealthCheck: "just now",
                    errorMessage: undefined,
                    tools: toolsFromProbe(result.tools, c.tools),
                    eventLog: addEvent(c, "Connection re-established", `Discovered ${result.tools.length} tool(s)`, "success", "plug"),
                  }
                : c,
            ),
          )
          toast.success(`${conn.name} reconnected`, { id: toastId })
        } else {
          setConnections((prev) =>
            prev.map((c) =>
              c.id === id
                ? { ...c, health: "error" as Health, lastHealthCheck: "just now", errorMessage: result.error }
                : c,
            ),
          )
          toast.error(`${conn.name} failed: ${result.error}`, { id: toastId })
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Reconnect failed", { id: toastId })
      } finally {
        setReconnectingId(null)
      }
    },
    [connections, patchConfig],
  )

  /* ---------------- config / auth ---------------- */

  const saveConfig = useCallback(
    async (connId: string, patch: Partial<Pick<McpConnection, "envVars" | "authConfigured" | "authTokenPreview">>) => {
      const conn = connections.find((c) => c.id === connId)
      if (!conn) return
      const env: Record<string, string | null> = {}
      for (const e of patch.envVars ?? conn.envVars) {
        if (e.key.trim()) env[e.key.trim()] = e.value || null
      }
      const server: mcpApi.McpServerConfig = {
        ...(conn.config as mcpApi.McpServerConfig | undefined),
        env: Object.keys(env).length > 0 ? env : undefined,
      }
      if (patch.authConfigured !== undefined && server.auth) {
        server.auth = { ...server.auth, value: patch.authConfigured ? server.auth.value ?? null : null }
      }
      try {
        await patchConfig({ [connId]: server })
        toast.success(`${conn.name} configuration saved`)
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save configuration")
      }
    },
    [connections, patchConfig],
  )

  const setApiKey = useCallback(
    async (id: string, key: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      const strategy = authStrategyFor(conn.auth)
      try {
        await patchConfig({ [id]: { ...(conn.config as mcpApi.McpServerConfig), auth: { strategy, value: key } } })
        toast.success("Credential saved")
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save credential")
      }
    },
    [connections, patchConfig],
  )

  /** Clear the stored credential (value + oauth2 state) while keeping any
   *  structural auth fields (header_name, username, …). Shared by rotate and
   *  revoke; OAuth servers re-run the Connect flow to rotate. */
  const clearAuth = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      const strategy = authStrategyFor(conn.auth)
      const saved = conn.config?.auth as Record<string, unknown> | undefined
      const base = saved && typeof saved === "object" ? { ...saved } : {}
      const cleared: Record<string, unknown> = { ...base, strategy, value: null }
      delete cleared.state
      const server: mcpApi.McpServerConfig = {
        ...(conn.config as mcpApi.McpServerConfig),
        auth: cleared as mcpApi.McpServerConfig["auth"],
      }
      return patchConfig({ [id]: server })
    },
    [connections, patchConfig],
  )

  const rotateAuth = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      setRotatingId(id)
      try {
        await clearAuth(id)
        toast.success("Credential cleared — enter a new value to rotate", {
          description: "For OAuth servers use the OAuth flow to re-authorize.",
        })
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to rotate credential")
      } finally {
        setRotatingId(null)
      }
    },
    [clearAuth, connections],
  )

  const revokeAuth = useCallback(
    async (id: string) => {
      const conn = connections.find((c) => c.id === id)
      if (!conn) return
      try {
        await clearAuth(id)
        toast.success("Credential revoked")
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to revoke credential")
      }
    },
    [clearAuth, connections],
  )

  /* ---------------- secrets + server patch (setup flow) ---------------- */

  /** Persist a global secret so ${VAR} references in a server template
   *  resolve at conversation build time. Used by the Setup dialog. */
  const saveSecret = useCallback(async (name: string, value: string) => {
    await mcpApi.setSecret(name, value)
  }, [])

  /** Merge a partial patch into a server's settings.mcp_config entry (env
   *  merged, everything else shallow-merged). Used to persist OAuth client
   *  fields and completed sessions without touching unrelated settings. */
  const patchServerConfig = useCallback(
    async (connId: string, patch: Partial<mcpApi.McpServerConfig>) => {
      const conn = connections.find((c) => c.id === connId)
      if (!conn) return
      const base = conn.config as mcpApi.McpServerConfig | undefined
      const merged: mcpApi.McpServerConfig = { ...(base ?? {}), ...patch }
      if (base?.env || patch.env) merged.env = { ...(base?.env ?? {}), ...(patch.env ?? {}) }
      // auth.authentication (notably `provider`, see oauth_provider_config.py)
      // must survive a patch that only sets `state` -- a shallow `...patch`
      // overwrite would otherwise drop it, and the backend needs `provider`
      // again for any future token refresh against the saved session.
      const baseAuth = base?.auth as Record<string, unknown> | undefined
      const patchAuth = patch.auth as Record<string, unknown> | undefined
      if (baseAuth?.authentication && patchAuth && !patchAuth.authentication) {
        merged.auth = { ...baseAuth, ...patchAuth, authentication: baseAuth.authentication } as typeof merged.auth
      }
      await patchConfig({ [connId]: merged })
    },
    [connections, patchConfig],
  )

  /* ---------------- tools ---------------- */

  const updateTool = useCallback(
    async (connId: string, toolName: string, patch: Partial<Pick<McpTool, "enabled" | "permission">>) => {
      // Optimistically update local state
      setConnections((prev) =>
        prev.map((c) =>
          c.id === connId
            ? { ...c, tools: c.tools.map((t) => (t.name === toolName ? { ...t, ...patch } : t)) }
            : c,
        ),
      )

      // Persist to backend settings
      const conn = connections.find((c) => c.id === connId)
      if (!conn) return

      // Build the full tool_permissions map for this connection
      const toolPermissions: Record<string, "allow" | "deny" | "ask"> = {}
      for (const tool of conn.tools) {
        const permission = tool.name === toolName ? patch.permission ?? tool.permission : tool.permission
        if (permission && permission !== "allow") {
          toolPermissions[tool.name] = permission
        }
      }

      const server: mcpApi.McpServerConfig = {
        ...(conn.config as mcpApi.McpServerConfig | undefined),
        tool_permissions: Object.keys(toolPermissions).length > 0 ? toolPermissions : undefined,
      }

      try {
        await patchConfig({ [connId]: server })
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save tool permission")
        // Revert on error - reload from backend
        await load()
      }
    },
    [connections, patchConfig, load],
  )

  const value = useMemo<McpContextValue>(
    () => ({
      connections,
      dataSource,
      catalog,
      catalogLoading,
      catalogError,
      testingId,
      reconnectingId,
      rotatingId,
      load,
      loadCatalog,
      toggleConnection,
      testConnection,
      testAllConnections,
      reconnectConnection,
      disconnectAll,
      deleteConnection,
      duplicateConnection,
      upsertConnection,
      installAndProvision,
      startOAuth,
      completeOAuth,
      persistOAuthState,
      saveServerAuth,
      updateTool,
      saveConfig,
      setApiKey,
      saveSecret,
      patchServerConfig,
      rotateAuth,
      revokeAuth,
    }),
    [
      connections,
      dataSource,
      catalog,
      catalogLoading,
      catalogError,
      testingId,
      reconnectingId,
      rotatingId,
      load,
      loadCatalog,
      toggleConnection,
      testConnection,
      testAllConnections,
      reconnectConnection,
      disconnectAll,
      deleteConnection,
      duplicateConnection,
      upsertConnection,
      installAndProvision,
      startOAuth,
      completeOAuth,
      persistOAuthState,
      saveServerAuth,
      updateTool,
      saveConfig,
      setApiKey,
      saveSecret,
      patchServerConfig,
      rotateAuth,
      revokeAuth,
    ],
  )

  return <McpContext.Provider value={value}>{children}</McpContext.Provider>
}

export function useMcp() {
  const ctx = useContext(McpContext)
  if (!ctx) throw new Error("useMcp must be used within a McpProvider")
  return ctx
}
