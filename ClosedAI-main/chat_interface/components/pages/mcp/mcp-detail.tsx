"use client"

import { useMemo, useState } from "react"
import {
  Plug,
  Activity,
  Zap,
  RefreshCw,
  WifiOff,
  Copy,
  Eye,
  EyeOff,
  KeyRound,
  ShieldCheck,
  ShieldOff,
  Loader2,
  Pencil,
  MoreHorizontal,
  Trash2,
  ArrowUpRight,
  ArrowDownRight,
  Plus,
  X,
  Search as SearchIcon,
  CircleDot,
  Lock,
  Check,
  ExternalLink,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import * as mcpApi from "@/lib/mcp-api"
import { useMcp } from "@/lib/mcp-store"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { OptionMenu } from "@/components/option-menu"
import {
  CATEGORY_TONES,
  DrawerShell,
  PanelSection,
  DetailRow,
  Toolbar,
  StatusBadge,
  Pagination,
  ActivityLogEntry,
  Tag,
  StatusPill,
} from "@/components/management/shared"
import {
  HEALTH_META,
  PERMISSION_META,
  type EnvVar,
  type EventLogItem,
  type HistoryEvent,
  type LogStatus,
  type McpConnection,
  type McpTool,
  type ToolPermission,
} from "./mcp-types"

/* ------------------------------------------------------------------ */
/*  Icon helpers                                                       */
/* ------------------------------------------------------------------ */

function EventIcon({ name }: { name: string }) {
  const cls = "h-3.5 w-3.5"
  switch (name) {
    case "plug": return <Plug className={cls} />
    case "activity": return <Activity className={cls} />
    case "zap": return <Zap className={cls} />
    case "refresh": return <RefreshCw className={cls} />
    case "wifi-off": return <WifiOff className={cls} />
    default: return <Activity className={cls} />
  }
}

const HISTORY_META: Record<HistoryEvent["kind"], { icon: typeof Plug; className: string }> = {
  connect: { icon: Plug, className: "text-emerald-400" },
  disconnect: { icon: ShieldOff, className: "text-muted-foreground" },
  reconnect: { icon: RefreshCw, className: "text-sky-400" },
  error: { icon: WifiOff, className: "text-red-400" },
  config: { icon: Pencil, className: "text-amber-400" },
  auth: { icon: KeyRound, className: "text-violet-400" },
}

/* ------------------------------------------------------------------ */
/*  Detail panel                                                       */
/* ------------------------------------------------------------------ */

export interface McpDetailPanelProps {
  connection: McpConnection | null
  onOpenChange: (open: boolean) => void
  onTest: (id: string) => void
  onReconnect: (id: string) => void
  onSetup: (conn: McpConnection) => void
  onEdit: (conn: McpConnection) => void
  onDuplicate: (conn: McpConnection) => void
  onDelete: (conn: McpConnection) => void
  onUpdateTool: (connId: string, toolName: string, patch: Partial<Pick<McpTool, "enabled" | "permission">>) => void
  onSaveConfig: (connId: string, patch: Partial<Pick<McpConnection, "envVars" | "authConfigured" | "authTokenPreview">>) => void
  onSetApiKey: (id: string, key: string) => void
  onRotateAuth: (id: string) => void
  onRevokeAuth: (id: string) => void
  testing: boolean
  reconnecting: boolean
  rotating: boolean
}

export function McpDetailPanel({
  connection,
  onOpenChange,
  onTest,
  onReconnect,
  onSetup,
  onEdit,
  onDuplicate,
  onDelete,
  onUpdateTool,
  onSaveConfig,
  onSetApiKey,
  onRotateAuth,
  onRevokeAuth,
  testing,
  reconnecting,
  rotating,
}: McpDetailPanelProps) {
  const Icon = connection?.icon ?? null
  const health = connection ? HEALTH_META[connection.health] : null

  return (
    <DrawerShell
      open={connection !== null}
      onOpenChange={onOpenChange}
      eyebrow="MCP Server"
      icon={Icon ? <Icon className="h-5 w-5" /> : undefined}
      iconClassName={connection ? (CATEGORY_TONES[connection.category] ?? "border-border/60 bg-secondary/60 text-foreground") : undefined}
      title={connection?.name ?? ""}
      description={connection?.description}
      meta={
        connection ? (
          <>
            <StatusPill active={connection.connected} />
            {connection.isBuiltin && <StatusBadge status="neutral">Built-in</StatusBadge>}
            {connection.setupNeeded && (
              <StatusBadge status="warning">Setup needed</StatusBadge>
            )}
            {health && <StatusBadge status={health.tone}>{health.label}</StatusBadge>}
            <Tag>{connection.serverType}</Tag>
            <Tag>{connection.category}</Tag>
          </>
        ) : undefined
      }
      actions={
        connection && !connection.isBuiltin ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
                aria-label={`${connection.name} actions`}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={() => onEdit(connection)} className="gap-2 text-[13px]">
                <Pencil />
                Edit configuration
              </DropdownMenuItem>
              {connection.setupNeeded && (
                <DropdownMenuItem onClick={() => onSetup(connection)} className="gap-2 text-[13px]">
                  <KeyRound />
                  Set up credentials
                </DropdownMenuItem>
              )}
              {!connection.setupNeeded && connection.auth === "OAuth 2.0" && (
                <DropdownMenuItem onClick={() => onSetup(connection)} className="gap-2 text-[13px]">
                  <KeyRound />
                  Re-authenticate
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => onDuplicate(connection)} className="gap-2 text-[13px]">
                <Copy />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => onDelete(connection)}
                variant="destructive"
                className="gap-2 text-[13px]"
              >
                <Trash2 className="h-4 w-4" />
                Delete connection
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : undefined
      }
      alert={
        connection?.errorMessage ? (
          <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3.5 py-3">
            <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
            <div className="min-w-0">
              <p className="text-[13px] font-medium text-red-300">Connection degraded</p>
              <p className="mt-0.5 text-xs leading-relaxed text-red-300/80">{connection.errorMessage}</p>
            </div>
          </div>
        ) : undefined
      }
      footer={
        connection ? (
          <div className="flex items-center justify-between gap-3">
            {connection.isBuiltin ? (
              <span className="text-[12px] text-muted-foreground">
                Product-provided core server
              </span>
            ) : connection.setupNeeded ? (
              <Button
                onClick={() => onSetup(connection)}
                className="gap-2 border border-amber-500/25 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 hover:text-amber-200"
              >
                <KeyRound className="h-4 w-4" />
                Set up credentials
              </Button>
            ) : (
              <Button
                variant="ghost"
                onClick={() => onDelete(connection)}
                className="gap-2 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
                Uninstall
              </Button>
            )}
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => onReconnect(connection.id)} disabled={reconnecting} className="gap-2">
                {reconnecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Reconnect
              </Button>
              <Button onClick={() => onTest(connection.id)} disabled={testing} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                Test connection
              </Button>
            </div>
          </div>
        ) : undefined
      }
    >
      {connection && (
        <PanelTabs
          key={connection.id}
          conn={connection}
          onUpdateTool={onUpdateTool}
          onSaveConfig={onSaveConfig}
          onSetApiKey={onSetApiKey}
          onRotateAuth={onRotateAuth}
          onRevokeAuth={onRevokeAuth}
          onEdit={onEdit}
          rotating={rotating}
        />
      )}
    </DrawerShell>
  )
}

function PanelTabs({
  conn,
  onUpdateTool,
  onSaveConfig,
  onSetApiKey,
  onRotateAuth,
  onRevokeAuth,
  onEdit,
  rotating,
}: {
  conn: McpConnection
  onUpdateTool: (connId: string, toolName: string, patch: Partial<Pick<McpTool, "enabled" | "permission">>) => void
  onSaveConfig: (connId: string, patch: Partial<Pick<McpConnection, "envVars" | "authConfigured" | "authTokenPreview">>) => void
  onSetApiKey: (id: string, key: string) => void
  onRotateAuth: (id: string) => void
  onRevokeAuth: (id: string) => void
  onEdit: (conn: McpConnection) => void
  rotating: boolean
}) {
  return (
    <Tabs defaultValue="overview" className="flex flex-col">
      <div className="sticky top-0 z-10 border-b border-border/60 bg-card/95 px-6 pt-4 pb-2 backdrop-blur">
        <TabsList className="h-9 w-auto justify-start gap-0.5 self-start rounded-lg border border-border/60 bg-secondary/30 p-1">
          <TabTrigger value="overview">Overview</TabTrigger>
          <TabTrigger value="tools">Tools</TabTrigger>
          <TabTrigger value="configuration">Configuration</TabTrigger>
          <TabTrigger value="activity">Activity</TabTrigger>
          <TabTrigger value="history">History</TabTrigger>
        </TabsList>
      </div>

      <TabsContent value="overview" className="px-6 pt-3 pb-6">
        <OverviewTab conn={conn} />
      </TabsContent>
      <TabsContent value="tools" className="px-6 pt-3 pb-6">
        <ToolsTab conn={conn} onUpdateTool={onUpdateTool} />
      </TabsContent>
      <TabsContent value="configuration" className="px-6 pt-3 pb-6">
        <ConfigTab
          key={`config-${conn.id}`}
          conn={conn}
          onSaveConfig={onSaveConfig}
          onSetApiKey={onSetApiKey}
          onRotateAuth={onRotateAuth}
          onRevokeAuth={onRevokeAuth}
          onEdit={onEdit}
          rotating={rotating}
        />
      </TabsContent>
      <TabsContent value="activity" className="px-6 pt-3 pb-6">
        <ActivityTab events={conn.eventLog} />
      </TabsContent>
      <TabsContent value="history" className="px-6 pt-3 pb-6">
        <HistoryTab history={conn.history} />
      </TabsContent>
    </Tabs>
  )
}

function TabTrigger({ value, children }: { value: string; children: React.ReactNode }) {
  return (
    <TabsTrigger
      value={value}
      className="h-7 rounded-md px-3 text-[13px] data-[state=active]:bg-secondary data-[state=active]:text-foreground"
    >
      {children}
    </TabsTrigger>
  )
}

/* ------------------------------------------------------------------ */
/*  Overview                                                           */
/* ------------------------------------------------------------------ */

function OverviewTab({ conn }: { conn: McpConnection }) {
  const health = HEALTH_META[conn.health]
  const enabledTools = conn.tools.filter((t) => t.enabled).length

  return (
    <div className="flex flex-col gap-5">
      {/* Only real, probe-backed values are shown here — never fabricated
          uptime/error/call counters. latencyMs & health come from the last
          POST /api/mcp/test. */}
      <div className="grid grid-cols-3 gap-3">
        <StatCell label="Last check" value={conn.lastHealthCheck} className="text-foreground" />
        <StatCell
          label="Latency"
          value={conn.latencyMs > 0 ? `${conn.latencyMs} ms` : "—"}
          className="text-foreground"
        />
        <StatCell label="Tools" value={String(enabledTools)} className="text-foreground" />
      </div>

      <PanelSection title="Endpoint">
        <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-secondary/40 px-3 py-2">
          <code className="flex-1 truncate font-mono text-[13px] text-foreground">{conn.url}</code>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(conn.url)
              toast.success("Endpoint copied")
            }}
            className="text-muted-foreground transition-colors hover:text-foreground"
            aria-label="Copy endpoint"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        </div>
      </PanelSection>

      <PanelSection title="Server metadata">
        <div className="divide-y divide-border/50">
          <DetailRow label="Type" value={<Tag>{conn.serverType}</Tag>} />
          <DetailRow label="Authentication" value={conn.auth} />
          <DetailRow label="Category" value={conn.category} />
          <DetailRow label="Created" value={conn.created} />
        </div>
      </PanelSection>

      <PanelSection title="Environment variables">
        {conn.envVars.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">No environment variables configured.</p>
        ) : (
          <div className="flex flex-col divide-y divide-border/50">
            {conn.envVars.map((v) => (
              <div key={v.key} className="flex items-center justify-between gap-3 py-1.5 text-[13px]">
                <code className="font-mono text-foreground">{v.key}</code>
                <div className="flex items-center gap-2">
                  {v.secret && <Tag className="border-violet-500/20 bg-violet-500/10 text-violet-400">secret</Tag>}
                  <span className="font-mono text-xs text-muted-foreground">{v.secret ? "••••••••" : v.value}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Exposed tools">
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-muted-foreground">
            {enabledTools} of {conn.tools.length} tools enabled
          </span>
          <span className={health.className}>Health: {health.label}</span>
        </div>
      </PanelSection>
    </div>
  )
}

function StatCell({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground/70">{label}</p>
      <p className={cn("mt-1 text-[15px] font-semibold", className)}>{value}</p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Tools                                                              */
/* ------------------------------------------------------------------ */

function ToolsTab({
  conn,
  onUpdateTool,
}: {
  conn: McpConnection
  onUpdateTool: (connId: string, toolName: string, patch: Partial<Pick<McpTool, "enabled" | "permission">>) => void
}) {
  const [query, setQuery] = useState("")
  const [permFilter, setPermFilter] = useState("All")

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return conn.tools.filter((t) => {
      const matchesQuery = !q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
      const matchesPerm = permFilter === "All" || PERMISSION_META[t.permission].label === permFilter
      return matchesQuery && matchesPerm
    })
  }, [conn.tools, query, permFilter])

  const enabledCount = conn.tools.filter((t) => t.enabled).length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[13px] text-muted-foreground">
          {enabledCount} of {conn.tools.length} tools enabled. The agent can only call enabled tools.
        </p>
      </div>

      <Toolbar>
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tools..."
            className="h-9 bg-secondary/40 pl-8 text-[13px]"
          />
        </div>
        <OptionMenu
          label="Permission"
          options={["All", "Allowed", "Denied", "Ask"]}
          value={permFilter}
          onChange={setPermFilter}
          align="end"
          trigger={
            <button className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-border/60 bg-card/40 px-3 text-[13px] text-foreground transition-colors hover:border-border">
              {permFilter}
            </button>
          }
        />
      </Toolbar>

      <div className="flex flex-col gap-2">
        {filtered.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border/60 px-4 py-8 text-center text-[13px] text-muted-foreground">
            No tools match your filters.
          </p>
        ) : (
          filtered.map((tool) => (
            <div
              key={tool.name}
              className={cn(
                "flex items-start justify-between gap-3 rounded-lg border border-border/60 bg-secondary/30 px-4 py-3",
                !tool.enabled && "opacity-70",
              )}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <code className="font-mono text-[13px] font-medium text-foreground">{tool.name}</code>
                  <StatusBadge status={PERMISSION_META[tool.permission].tone}>{PERMISSION_META[tool.permission].label}</StatusBadge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{tool.description}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <PermissionMenu
                  value={tool.permission}
                  onChange={(p) => onUpdateTool(conn.id, tool.name, { permission: p })}
                />
                <Switch
                  checked={tool.enabled}
                  onCheckedChange={(v) => onUpdateTool(conn.id, tool.name, { enabled: v })}
                  aria-label={`Toggle ${tool.name}`}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function PermissionMenu({ value, onChange }: { value: ToolPermission; onChange: (p: ToolPermission) => void }) {
  const meta = PERMISSION_META[value]
  return (
    <OptionMenu
      label="Permission"
      options={["Allowed", "Denied", "Ask"]}
      value={meta.label}
      onChange={(lbl) => onChange(lbl === "Allowed" ? "allow" : lbl === "Denied" ? "deny" : "ask")}
      align="end"
      trigger={
        <button
          className={cn(
            "flex h-8 items-center gap-1 rounded-md border px-2.5 text-[12px] font-medium transition-colors",
            "border-border/60 bg-card/40 hover:border-border",
            meta.className,
          )}
        >
          {meta.label}
        </button>
      }
    />
  )
}

/* ------------------------------------------------------------------ */
/*  Configuration                                                      */
/* ------------------------------------------------------------------ */

function ConfigTab({
  conn,
  onSaveConfig,
  onSetApiKey,
  onRotateAuth,
  onRevokeAuth,
  onEdit,
  rotating,
}: {
  conn: McpConnection
  onSaveConfig: (connId: string, patch: Partial<Pick<McpConnection, "envVars" | "authConfigured" | "authTokenPreview">>) => void
  onSetApiKey: (id: string, key: string) => void
  onRotateAuth: (id: string) => void
  onRevokeAuth: (id: string) => void
  onEdit: (conn: McpConnection) => void
  rotating: boolean
}) {
  return (
    <div className="flex flex-col gap-5">
      <PanelSection
        title="Server"
        description="Connection endpoint and transport protocol."
        action={
          <Button variant="ghost" size="sm" onClick={() => onEdit(conn)} className="gap-1.5 text-muted-foreground hover:text-foreground">
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
        }
      >
        <DetailRow label="Type" value={<Tag>{conn.serverType}</Tag>} />
        <div className="flex items-center justify-between gap-4 py-1.5 text-[13px]">
          <span className="text-muted-foreground">URL</span>
          <code className="max-w-[60%] truncate text-right font-mono text-[12px] text-foreground">{conn.url}</code>
        </div>
      </PanelSection>

      <AuthSection
        conn={conn}
        onSetApiKey={onSetApiKey}
        onRotateAuth={onRotateAuth}
        onRevokeAuth={onRevokeAuth}
        rotating={rotating}
      />

      <EnvVarsManager conn={conn} onSaveConfig={onSaveConfig} />
    </div>
  )
}

function AuthSection({
  conn,
  onSetApiKey,
  onRotateAuth,
  onRevokeAuth,
  rotating,
}: {
  conn: McpConnection
  onSetApiKey: (id: string, key: string) => void
  onRotateAuth: (id: string) => void
  onRevokeAuth: (id: string) => void
  rotating: boolean
}) {
  const { startOAuth, completeOAuth, persistOAuthState } = useMcp()
  const [settingKey, setSettingKey] = useState(false)
  const [newKey, setNewKey] = useState("")
  const [showNewKey, setShowNewKey] = useState(false)
  const [oauthBusy, setOauthBusy] = useState(false)

  const savedAuth = conn.config?.auth as Record<string, unknown> | undefined
  const isOAuth = savedAuth?.strategy === "oauth2"
  const oauthConfigured = Boolean(savedAuth?.state)
  const noAuth = conn.auth === "None" || savedAuth?.strategy === "none"
  // Only the real masked preview from the backend config is shown — secrets
  // never round-trip to the browser, so there is nothing to "reveal" or copy.
  const token = conn.authTokenPreview ?? "••••••••••••"

  const handleSaveKey = () => {
    if (!newKey.trim()) {
      toast.error("Enter an API key or token")
      return
    }
    onSetApiKey(conn.id, newKey.trim())
    setSettingKey(false)
    setNewKey("")
  }

  /* OAuth servers rotate by re-running the browser flow, not by pasting a
     token. The saved session is persisted back under auth.state after the
     browser-coordinated job completes. */
  const handleConnect = async () => {
    if (oauthBusy) return
    const spec = mcpApi.buildTestServerSpec(conn)
    if (!spec) {
      toast.error("Cannot build an OAuth probe from this configuration")
      return
    }
    setOauthBusy(true)
    try {
      // Force a real tool call when the template requires one (e.g. Gmail) --
      // otherwise a provider that only gates individual tool calls, not
      // tools/list, reports the job "succeeded" without ever obtaining a
      // token. See SetupAuthConfig.verify_tool_call / mcp-setup-dialog.tsx,
      // which already does this for first-time setup; Re-authorize on an
      // already-installed server was missing the same call.
      const jobId = await startOAuth(spec, { verifyToolCall: conn.verifyToolCall })
      if (jobId) await completeOAuth(jobId, (state) => persistOAuthState(conn.id, state))
    } finally {
      setOauthBusy(false)
    }
  }

  return (
    <PanelSection
      title="Authentication"
      description="Credential used when the agent connects to this server."
      action={
        noAuth ? (
          <StatusBadge status="neutral">No auth required</StatusBadge>
        ) : isOAuth ? (
          oauthConfigured ? (
            <StatusBadge status="success">
              <ShieldCheck className="h-3 w-3" />
              Connected
            </StatusBadge>
          ) : (
            <StatusBadge status="warning">
              <ShieldOff className="h-3 w-3" />
              Not authorized
            </StatusBadge>
          )
        ) : conn.authConfigured ? (
          <StatusBadge status="success">
            <ShieldCheck className="h-3 w-3" />
            Configured
          </StatusBadge>
        ) : (
          <StatusBadge status="warning">
            <ShieldOff className="h-3 w-3" />
            Not configured
          </StatusBadge>
        )
      }
    >
      {noAuth ? (
        <p className="text-[13px] text-muted-foreground">This server does not require any credentials.</p>
      ) : isOAuth ? (
        <div className="flex flex-col gap-3">
          <DetailRow label="Method" value="OAuth 2.0" />
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
            <div className="min-w-0">
              <p className="text-[13px] font-medium text-foreground">OAuth session</p>
              <p className="truncate text-xs text-muted-foreground">
                {oauthConfigured
                  ? "A token session is stored for this server."
                  : "Not authorized yet. Open the provider to grant access."}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleConnect}
              disabled={oauthBusy}
              className="gap-1.5 border border-border/60 bg-secondary/60 text-[12px] hover:bg-secondary"
            >
              {oauthBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
              {oauthConfigured ? "Re-authorize" : "Connect"}
            </Button>
          </div>
          {oauthConfigured && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRevokeAuth(conn.id)}
              className="w-fit gap-1.5 text-[12px] text-red-400 hover:bg-red-500/10 hover:text-red-300"
            >
              <ShieldOff className="h-3.5 w-3.5" />
              Revoke session
            </Button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <DetailRow label="Method" value={conn.auth} />

          {conn.authConfigured ? (
            <>
              <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-secondary/40 px-3 py-2">
                <Lock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <code className="flex-1 truncate font-mono text-[13px] text-foreground">{token}</code>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onRotateAuth(conn.id)}
                  disabled={rotating}
                  className="gap-1.5 border border-border/60 bg-secondary/40 text-[12px] hover:bg-secondary"
                >
                  {rotating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Rotate token
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRevokeAuth(conn.id)}
                  className="gap-1.5 text-[12px] text-red-400 hover:bg-red-500/10 hover:text-red-300"
                >
                  <ShieldOff className="h-3.5 w-3.5" />
                  Revoke
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground/70">
                Rotating issues a new credential immediately and invalidates the old one.
              </p>
            </>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-[13px] text-muted-foreground">
                No credential is stored for this server. The agent will not be able to authenticate until one is set.
              </p>
              {settingKey ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-secondary/40 px-3 py-2">
                    <KeyRound className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <Input
                      autoFocus
                      type={showNewKey ? "text" : "password"}
                      value={newKey}
                      onChange={(e) => setNewKey(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleSaveKey()}
                      placeholder="Paste API key or token"
                      className="h-8 border-0 bg-transparent px-0 font-mono text-[13px] shadow-none focus-visible:ring-0"
                    />
                    <button
                      onClick={() => setShowNewKey((v) => !v)}
                      className="text-muted-foreground transition-colors hover:text-foreground"
                      aria-label="Toggle key visibility"
                    >
                      {showNewKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleSaveKey} className="gap-1.5 bg-primary text-primary-foreground text-[12px] hover:opacity-90">
                      <Check className="h-3.5 w-3.5" />
                      Save credential
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setSettingKey(false)} className="text-[12px]">
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setSettingKey(true)}
                  className="w-fit gap-1.5 border border-border/60 bg-secondary/40 text-[12px] hover:bg-secondary"
                >
                  <KeyRound className="h-3.5 w-3.5" />
                  Set API key / token
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </PanelSection>
  )
}

function EnvVarsManager({
  conn,
  onSaveConfig,
}: {
  conn: McpConnection
  onSaveConfig: (connId: string, patch: Partial<Pick<McpConnection, "envVars">>) => void
}) {
  const [rows, setRows] = useState<EnvVar[]>(conn.envVars)
  const [saving, setSaving] = useState(false)

  const dirty = JSON.stringify(rows) !== JSON.stringify(conn.envVars)

  const updateRow = (i: number, patch: Partial<EnvVar>) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  const handleSave = () => {
    const cleaned = rows.filter((r) => r.key.trim() !== "")
    setSaving(true)
    // Fire the backend PATCH immediately — the spinner covers the real latency.
    onSaveConfig(conn.id, { envVars: cleaned })
    setSaving(false)
    toast.success("Environment variables saved")
  }

  return (
    <PanelSection
      title="Environment variables"
      description="Variables injected into the server process at startup."
      action={
        dirty ? (
          <div className="flex items-center gap-1.5">
            <span className="flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400">
              <CircleDot className="h-3 w-3" />
              Unsaved changes
            </span>
            <Button variant="ghost" size="sm" onClick={() => setRows(conn.envVars)} className="h-7 text-[12px]">
              Discard
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="h-7 gap-1.5 bg-primary text-primary-foreground text-[12px] hover:opacity-90">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              Save
            </Button>
          </div>
        ) : undefined
      }
    >
      {rows.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">No environment variables configured.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((row, i) => (
            <div key={`${row.key}-${i}`} className="flex items-center gap-2">
              <Input
                value={row.key}
                onChange={(e) => updateRow(i, { key: e.target.value })}
                placeholder="KEY"
                className="h-8 w-40 bg-secondary/40 font-mono text-[12px]"
              />
              <Input
                value={row.value}
                onChange={(e) => updateRow(i, { value: e.target.value })}
                placeholder="value"
                className="h-8 flex-1 bg-secondary/40 font-mono text-[12px]"
              />
              <button
                onClick={() => updateRow(i, { secret: !row.secret })}
                className={cn(
                  "flex h-8 shrink-0 items-center gap-1 rounded-md border px-2 text-[11px] font-medium transition-colors",
                  row.secret
                    ? "border-violet-500/30 bg-violet-500/10 text-violet-400"
                    : "border-border/60 bg-card/40 text-muted-foreground hover:border-border",
                )}
                aria-label="Toggle secret"
              >
                <Lock className="h-3 w-3" />
                {row.secret ? "Secret" : "Plain"}
              </button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
                aria-label={`Remove ${row.key}`}
                className="h-8 w-8 shrink-0 text-muted-foreground hover:text-red-400"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setRows((prev) => [...prev, { key: "", value: "", secret: true }])}
        className="mt-3 gap-1.5 text-muted-foreground hover:text-foreground"
      >
        <Plus className="h-3.5 w-3.5" />
        Add variable
      </Button>
    </PanelSection>
  )
}

/* ------------------------------------------------------------------ */
/*  Activity / History                                                 */
/* ------------------------------------------------------------------ */

function ActivityTab({ events }: { events: EventLogItem[] }) {
  const [filter, setFilter] = useState<"all" | "success" | "warning" | "error" | "default">("all")
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(1)
  const pageSize = 6

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return [...events]
      .sort((a, b) => b.ts - a.ts)
      .filter((e) => {
        const matchesStatus = filter === "all" || e.status === filter
        const matchesQuery = !q || e.title.toLowerCase().includes(q) || (e.detail ?? "").toLowerCase().includes(q)
        return matchesStatus && matchesQuery
      })
  }, [events, filter, query])

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount)
  const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize)

  const pills: { id: "all" | "success" | "warning" | "error" | "default"; label: string }[] = [
    { id: "all", label: "All" },
    { id: "success", label: "Success" },
    { id: "warning", label: "Warnings" },
    { id: "error", label: "Errors" },
    { id: "default", label: "Info" },
  ]

  return (
    <div className="flex flex-col gap-4">
      <Toolbar>
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setPage(1)
            }}
            placeholder="Search activity..."
            className="h-9 bg-secondary/40 pl-8 text-[13px]"
          />
        </div>
      </Toolbar>

      <div className="flex flex-wrap items-center gap-1.5">
        {pills.map((p) => (
          <button
            key={p.id}
            onClick={() => {
              setFilter(p.id)
              setPage(1)
            }}
            className={cn(
              "rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
              filter === p.id
                ? "border-white/20 bg-white/[0.08] text-foreground"
                : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground",
            )}
          >
            {p.label}
          </button>
        ))}
        <span className="ml-auto text-[12px] tabular-nums text-muted-foreground">{filtered.length} events</span>
      </div>

      <div className="rounded-lg border border-border/60 bg-secondary/20 px-4 py-1">
        {visible.length === 0 ? (
          <p className="py-8 text-center text-[13px] text-muted-foreground">No activity matches your filters.</p>
        ) : (
          visible.map((event, i) => (
            <div key={event.id}>
              <ActivityLogEntry
                icon={<EventIcon name={event.iconName} />}
                title={event.title}
                detail={event.detail}
                time={event.time}
                status={event.status}
              />
              {i < visible.length - 1 && <div className="h-px bg-border/40" />}
            </div>
          ))
        )}
      </div>

      <Pagination page={safePage} pageSize={pageSize} total={filtered.length} onPageChange={setPage} />
    </div>
  )
}

function HistoryTab({ history }: { history: HistoryEvent[] }) {
  const sorted = [...history].sort((a, b) => b.ts - a.ts)

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-muted-foreground">
        Connection lifecycle events including connects, disconnects, reconnects, and configuration changes.
      </p>

      {sorted.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border/60 px-4 py-10 text-center text-[13px] text-muted-foreground">
          No connection history recorded yet.
        </p>
      ) : (
        <div className="relative flex flex-col gap-0 pl-1">
          <div className="absolute bottom-2 top-2 left-[15px] w-px bg-border/60" />
          {sorted.map((h) => {
            const meta = HISTORY_META[h.kind]
            const HI = meta.icon
            return (
              <div key={h.id} className="relative flex items-start gap-3.5 py-2.5">
                <span
                  className={cn(
                    "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/60 bg-card",
                    meta.className,
                  )}
                >
                  <HI className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-[13px] font-medium text-foreground">{h.title}</p>
                    <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground/70">{h.time}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{h.detail}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
