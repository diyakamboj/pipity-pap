"use client"

import { useEffect, useState } from "react"
import {
  CheckCircle2,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Plus,
  Server,
  ShieldCheck,
  X,
  Zap,
} from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { OptionMenu } from "@/components/option-menu"
import { DrawerShell } from "@/components/management/shared"
import * as mcpApi from "@/lib/mcp-api"
import { useMcp } from "@/lib/mcp-store"
import {
  AUTH_METHODS,
  SERVER_TYPES,
  type EnvVar,
  type McpConnection,
  type ServerType,
} from "./mcp-types"

/* UI auth label -> settings mcp_config auth strategy. */
const AUTH_LABEL_TO_STRATEGY: Record<string, string> = {
  "API Key": "api_key",
  "Bearer Token": "bearer",
  Basic: "basic",
  Header: "header",
  "OAuth 2.0": "oauth2",
}

/* ------------------------------------------------------------------ */
/*  Shared form pieces                                                 */
/* ------------------------------------------------------------------ */

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <Label className="text-[13px] font-medium text-foreground">{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function PasswordInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="flex items-center gap-2 rounded-md border border-border/60 bg-secondary/40 px-3 focus-within:border-border">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full bg-transparent font-mono text-[13px] text-foreground outline-none placeholder:text-muted-foreground/70"
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
        aria-label={show ? "Hide value" : "Show value"}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}

function EnvVarsField({
  value,
  onChange,
}: {
  value: EnvVar[]
  onChange: (rows: EnvVar[]) => void
}) {
  const updateRow = (i: number, patch: Partial<EnvVar>) =>
    onChange(value.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  return (
    <div className="flex flex-col gap-2">
      {value.map((row, i) => (
        <div key={`${row.key}-${i}`} className="flex items-center gap-2">
          <Input
            value={row.key}
            onChange={(e) => updateRow(i, { key: e.target.value })}
            placeholder="KEY"
            className="h-9 w-36 bg-secondary/40 font-mono text-[12px]"
          />
          <Input
            value={row.value}
            onChange={(e) => updateRow(i, { value: e.target.value })}
            placeholder="value"
            className="h-9 flex-1 bg-secondary/40 font-mono text-[12px]"
          />
          <button
            type="button"
            onClick={() => updateRow(i, { secret: !row.secret })}
            className={
              row.secret
                ? "flex h-9 shrink-0 items-center gap-1 rounded-md border border-violet-500/30 bg-violet-500/10 px-2 text-[11px] font-medium text-violet-400"
                : "flex h-9 shrink-0 items-center gap-1 rounded-md border border-border/60 bg-card/40 px-2 text-[11px] font-medium text-muted-foreground transition-colors hover:border-border"
            }
            aria-label="Toggle secret"
          >
            <Lock className="h-3 w-3" />
            {row.secret ? "Secret" : "Plain"}
          </button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => onChange(value.filter((_, idx) => idx !== i))}
            aria-label={`Remove ${row.key}`}
            className="h-9 w-9 shrink-0 text-muted-foreground hover:text-red-400"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onChange([...value, { key: "", value: "", secret: true }])}
        className="w-fit gap-1.5 text-muted-foreground hover:text-foreground"
      >
        <Plus className="h-3.5 w-3.5" />
        Add variable
      </Button>
    </div>
  )
}

function TestConnectionButton({
  testing,
  onTest,
}: {
  testing: boolean
  onTest: () => Promise<{ ok: boolean; detail: string }>
}) {
  const [busy, setBusy] = useState(false)
  const handleTest = async () => {
    if (busy) return
    setBusy(true)
    try {
      const result = await onTest()
      if (result.ok) toast.success(result.detail)
      else toast.error(result.detail)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Connection test failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Button
      type="button"
      variant="secondary"
      onClick={handleTest}
      disabled={busy || testing}
      className="gap-2 border border-border/60 bg-secondary/60 hover:bg-secondary"
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
      Test
    </Button>
  )
}

/* ------------------------------------------------------------------ */
/*  Template + spec helpers                                            */
/* ------------------------------------------------------------------ */

function rowsToMap(rows: EnvVar[]): Record<string, string> {
  return Object.fromEntries(
    rows.filter((r) => r.key.trim() !== "").map((r) => [r.key.trim(), r.value]),
  )
}

function parseArgs(raw: string): string[] {
  return raw
    .trim()
    .split(/\s+/)
    .filter((a) => a.length > 0)
}

/* ------------------------------------------------------------------ */
/*  Create / Edit connection                                           */
/*  Transport-aware (stdio → command/args) and auth-aware (per-method   */
/*  fields incl. OAuth connect).                                       */
/* ------------------------------------------------------------------ */

export function McpConnectionDialog({
  open,
  connection,
  onOpenChange,
  onSave,
}: {
  open: boolean
  connection: McpConnection | null
  onOpenChange: (open: boolean) => void
  onSave: (conn: McpConnection) => void
}) {
  const { startOAuth, completeOAuth } = useMcp()
  const isEditing = connection !== null
  const config = connection?.config as mcpApi.McpServerConfig | undefined
  const savedAuth = config?.auth as Record<string, unknown> | undefined

  const [name, setName] = useState(connection?.name ?? "")
  const [description, setDescription] = useState(connection?.description ?? "")
  const [url, setUrl] = useState(connection?.url ?? "")
  const [serverType, setServerType] = useState<ServerType>(connection?.serverType ?? "HTTP")
  const [command, setCommand] = useState(typeof config?.command === "string" ? config.command : "")
  const [args, setArgs] = useState(Array.isArray(config?.args) ? (config.args as string[]).join(" ") : "")
  const [headers, setHeaders] = useState<EnvVar[]>(
    config?.headers
      ? Object.entries(config.headers).map(([k, v]) => ({ key: k, value: v ?? "", secret: true }))
      : [],
  )
  const [authMethod, setAuthMethod] = useState(connection?.auth ?? AUTH_METHODS[1])
  const [apiKey, setApiKey] = useState("")
  const [authHeaderName, setAuthHeaderName] = useState(
    typeof savedAuth?.header_name === "string" ? savedAuth.header_name : "",
  )
  const [basicUsername, setBasicUsername] = useState(
    typeof savedAuth?.username === "string" ? savedAuth.username : "",
  )
  const [basicPassword, setBasicPassword] = useState("")
  const [headerRows, setHeaderRows] = useState<EnvVar[]>(
    savedAuth?.strategy === "header" && savedAuth.headers
      ? Object.entries(savedAuth.headers as Record<string, unknown>).map(([k, v]) => ({
          key: k,
          value: (v as string) ?? "",
          secret: true,
        }))
      : [],
  )
  const [clientId, setClientId] = useState("")
  const [clientSecret, setClientSecret] = useState("")
  const [oauthState, setOauthState] = useState<Record<string, unknown> | null>(null)
  const [oauthBusy, setOauthBusy] = useState(false)
  const [envVars, setEnvVars] = useState<EnvVar[]>(connection?.envVars ?? [])
  const [connectAfterSave, setConnectAfterSave] = useState(connection?.connected ?? true)
  const [testState, setTestState] = useState<{ state: "idle" | "testing" | "ok" | "fail"; detail?: string }>({
    state: "idle",
  })

  const oauthConnected = oauthState !== null || (savedAuth?.strategy === "oauth2" && Boolean(savedAuth.state))

  /* Build a probe spec from the current form state — never from fiction. */
  const buildSpec = (): mcpApi.McpTestServerSpec | null => {
    const env = rowsToMap(envVars)
    if (serverType === "Stdio") {
      if (!command.trim()) return null
      return { type: "stdio", command: command.trim(), args: parseArgs(args), ...(env ? { env } : {}) }
    }
    if (!url.trim()) return null
    const remote: Record<string, unknown> = {
      type: serverType === "SSE" ? "sse" : "http",
      url: url.trim(),
    }
    const h = rowsToMap(headers)
    if (Object.keys(h).length > 0) remote.headers = h
    if (authMethod === "API Key" && apiKey.trim()) remote.api_key = apiKey.trim()
    if (authMethod === "Bearer Token" && apiKey.trim()) {
      remote.auth = { strategy: "bearer", value: apiKey.trim() }
    }
    if (authMethod === "Basic") {
      remote.auth = { strategy: "basic", username: basicUsername.trim(), password: basicPassword.trim() || undefined }
    }
    if (authMethod === "Header") {
      const hdrs = rowsToMap(headerRows)
      if (Object.keys(hdrs).length > 0) remote.auth = { strategy: "header", headers: hdrs }
    }
    if (authMethod === "OAuth 2.0" && oauthState) {
      remote.auth = { strategy: "oauth2", state: oauthState }
    }
    return remote as mcpApi.McpTestServerSpec
  }

  const handleTestResult = (ok: boolean, detail: string) =>
    setTestState(ok ? { state: "ok", detail } : { state: "fail", detail })

  const handleTest = async () => {
    const spec = buildSpec()
    if (!spec) return { ok: false, detail: "Fill in the required fields for this transport first" }
    const result = await mcpApi.testServer({ server: spec, timeout: 15 })
    return result.ok
      ? { ok: true, detail: `Connection successful. ${result.tools.length} tools discovered` }
      : { ok: false, detail: result.error }
  }

  const handleOAuth = async () => {
    if (oauthBusy || oauthConnected) return
    const spec = buildSpec()
    if (!spec) return
    // Custom servers have no marketplace catalog entry (and so no backend
    // provider config to resolve against) -- this manual client id/secret
    // is the one place the app still accepts OAuth app credentials directly,
    // since there's no other way to authorize an arbitrary unlisted server.
    if (clientId.trim()) {
      spec.auth = {
        strategy: "oauth2",
        authentication: {
          type: "oauth",
          client_id: clientId.trim(),
          client_secret: clientSecret.trim() || undefined,
        },
      } as NonNullable<mcpApi.McpServerConfig["auth"]>
    }
    setOauthBusy(true)
    try {
      const jobId = await startOAuth(spec)
      if (!jobId) return
      await completeOAuth(jobId, (state) => setOauthState(state))
    } finally {
      setOauthBusy(false)
    }
  }

  const handleSave = () => {
    if (!name.trim()) {
      toast.error("Server name is required")
      return
    }
    if (serverType === "Stdio") {
      if (!command.trim()) {
        toast.error("Enter the command to launch the stdio server")
        return
      }
    } else if (!url.trim()) {
      toast.error("Enter the server URL")
      return
    }
    if (
      (authMethod === "API Key" || authMethod === "Bearer Token") &&
      apiKey.trim() === "" &&
      !connection?.authConfigured
    ) {
      toast.error("Enter the API key or token")
      return
    }
    if (authMethod === "Basic" && basicUsername.trim() === "" && !connection?.authConfigured) {
      toast.error("Enter the username for Basic auth")
      return
    }

    const configOut: Record<string, unknown> = { ...(connection?.config ?? {}) }
    if (serverType === "Stdio") {
      configOut.transport = "stdio"
      configOut.command = command.trim()
      configOut.args = parseArgs(args)
      delete configOut.url
    } else {
      configOut.transport = serverType === "SSE" ? "sse" : "http"
      configOut.url = url.trim()
      const h = rowsToMap(headers)
      if (Object.keys(h).length > 0) configOut.headers = h
      else delete configOut.headers
    }
    const env = rowsToMap(envVars)
    if (Object.keys(env).length > 0) configOut.env = env
    else delete configOut.env

    if (authMethod !== "None") {
      const strategy = AUTH_LABEL_TO_STRATEGY[authMethod] ?? "bearer"
      switch (authMethod) {
        case "API Key":
          configOut.auth = {
            strategy,
            value: apiKey.trim() || (savedAuth?.value as string | undefined) || null,
            header_name: authHeaderName.trim() || undefined,
          }
          break
        case "Bearer Token":
          configOut.auth = { strategy, value: apiKey.trim() || (savedAuth?.value as string | undefined) || null }
          break
        case "Basic":
          configOut.auth = {
            strategy,
            username: basicUsername.trim(),
            password: basicPassword.trim() || undefined,
          }
          break
        case "Header": {
          const hdrs = rowsToMap(headerRows)
          configOut.auth = { strategy, headers: hdrs }
          break
        }
        case "OAuth 2.0":
          configOut.auth = oauthState ? { strategy, state: oauthState } : { strategy, value: null }
          break
      }
    } else {
      configOut.auth = { strategy: "none" }
    }

    onSave({
      id: connection?.id ?? name.trim(),
      name: name.trim(),
      description: description.trim() || "Custom MCP connection.",
      connected: connectAfterSave,
      serverType,
      url: serverType === "Stdio" ? `stdio://${command.trim()}` : url.trim(),
      auth: authMethod,
      authConfigured:
        authMethod === "None"
          ? false
          : authMethod === "OAuth 2.0"
            ? oauthConnected
            : Boolean(apiKey || basicPassword || connection?.authConfigured),
      authTokenPreview: apiKey ? `••••••••••••••••••${apiKey.slice(-4)}` : connection?.authTokenPreview,
      envVars: envVars.filter((v) => v.key.trim() !== ""),
      tools: connection?.tools ?? [],
      category: connection?.category ?? "Custom",
      latencyMs: connection?.latencyMs ?? 0,
      health: "unknown",
      lastUsed: connection?.lastUsed ?? "never",
      created: connection?.created ?? "",
      icon: connection?.icon ?? Server,
      uptimePercent: 0,
      lastHealthCheck: "never",
      errorCount24h: 0,
      latencyTrend: "stable",
      totalCalls: 0,
      calls24h: 0,
      serverVersion: "",
      protocolVersion: "",
      eventLog: connection?.eventLog ?? [],
      history: connection?.history ?? [],
      config: configOut,
      setupNeeded: (() => {
        const a = configOut.auth as { strategy?: string; state?: unknown; value?: unknown } | undefined
        return a?.strategy === "oauth2" && !a.state && !a.value
      })(),
      missingSecrets: [],
    })
    toast.success(isEditing ? `${name.trim()} updated` : `${name.trim()} saved`)
    onOpenChange(false)
  }

  return (
    <DrawerShell
      open={open}
      onOpenChange={onOpenChange}
      eyebrow="MCP Server"
      icon={<Server className="h-5 w-5" />}
      title={isEditing ? "Edit MCP Configuration" : "Add Custom MCP Server"}
      description="Point the agent at any MCP-compatible server and expose its tools."
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
            {isEditing ? "Save changes" : "Add Server"}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-6 py-6">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Server type">
            <OptionMenu
              label="Server type"
              options={SERVER_TYPES}
              value={serverType}
              onChange={(v) => setServerType(v as ServerType)}
              trigger={
                <button className="flex h-9 w-full items-center justify-between rounded-md border border-border/60 bg-secondary/40 px-3 text-sm text-foreground">
                  {serverType}
                  <span className="text-muted-foreground">▾</span>
                </button>
              }
            />
          </Field>
          <Field label="Authentication">
            <OptionMenu
              label="Auth method"
              options={AUTH_METHODS}
              value={authMethod}
              onChange={setAuthMethod}
              trigger={
                <button className="flex h-9 w-full items-center justify-between rounded-md border border-border/60 bg-secondary/40 px-3 text-sm text-foreground">
                  {authMethod}
                  <span className="text-muted-foreground">▾</span>
                </button>
              }
            />
          </Field>
        </div>

        <Field label="Server name">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Internal Wiki"
            className="bg-secondary/40"
          />
        </Field>

        <Field label="Description">
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What does this server give the agent access to?"
            className="min-h-[64px] resize-none bg-secondary/40"
          />
        </Field>

        {serverType === "Stdio" ? (
          <>
            <Field label="Launch command" hint="Executed to start the server process (e.g. `npx -y @some/mcp-server`).">
              <Input
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="npx -y @some/mcp-server"
                className="bg-secondary/40 font-mono text-[13px]"
              />
            </Field>
            <Field label="Arguments" hint="Space-separated. Leave blank if the command needs none.">
              <Input
                value={args}
                onChange={(e) => setArgs(e.target.value)}
                placeholder="--flag value"
                className="bg-secondary/40 font-mono text-[13px]"
              />
            </Field>
          </>
        ) : (
          <Field label="Server URL">
            <Input
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                setTestState((s) => (s.state === "idle" || s.state === "ok" ? { state: "idle" } : s))
              }}
              placeholder="https://api.example.com/mcp"
              className="bg-secondary/40 font-mono text-[13px]"
            />
          </Field>
        )}

        {serverType !== "Stdio" && (
          <Field label="Custom headers" hint="Optional headers sent on every request to the server.">
            <EnvVarsField value={headers} onChange={setHeaders} />
          </Field>
        )}

        {/* --- per-auth-method fields --- */}
        {authMethod === "API Key" && (
          <Field
            label="API key"
            hint={connection?.authConfigured && !apiKey ? "A key is already stored — leave blank to keep it." : "Sent as `Authorization: Bearer <key>` unless a header name is set."}
          >
            <PasswordInput value={apiKey} onChange={setApiKey} placeholder="••••••••••••••••" />
            <div className="mt-2">
              <Field label="Header name (optional)">
                <Input
                  value={authHeaderName}
                  onChange={(e) => setAuthHeaderName(e.target.value)}
                  placeholder="X-API-Key"
                  className="bg-secondary/40 font-mono text-[13px]"
                />
              </Field>
            </div>
          </Field>
        )}

        {authMethod === "Bearer Token" && (
          <Field
            label="Bearer token"
            hint={connection?.authConfigured && !apiKey ? "A token is already stored — leave blank to keep it." : "Sent as `Authorization: Bearer <token>`."}
          >
            <PasswordInput value={apiKey} onChange={setApiKey} placeholder="••••••••••••••••" />
          </Field>
        )}

        {authMethod === "Basic" && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Username">
              <Input value={basicUsername} onChange={(e) => setBasicUsername(e.target.value)} className="bg-secondary/40" />
            </Field>
            <Field label="Password">
              <PasswordInput value={basicPassword} onChange={setBasicPassword} placeholder="••••••••••••••••" />
            </Field>
          </div>
        )}

        {authMethod === "Header" && (
          <Field label="Headers" hint="Each header is sent verbatim on every request.">
            <EnvVarsField value={headerRows} onChange={setHeaderRows} />
          </Field>
        )}

        {authMethod === "OAuth 2.0" && (
          <>
            <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">OAuth 2.0</p>
                <p className="truncate text-xs text-muted-foreground">
                  {oauthConnected ? (
                    <span className="flex items-center gap-1 text-emerald-400">
                      <ShieldCheck className="h-3 w-3" />
                      OAuth session saved
                    </span>
                  ) : oauthBusy ? (
                    "Waiting for authorization…"
                  ) : (
                    "Authorize this server in your browser. Optional custom client below."
                  )}
                </p>
              </div>
              {oauthConnected ? (
                <span className="flex shrink-0 items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-400">
                  <CheckCircle2 className="h-3 w-3" />
                  Connected
                </span>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleOAuth}
                  disabled={oauthBusy || !url.trim() || serverType === "Stdio"}
                  className="gap-2 border border-border/60 bg-secondary/60 hover:bg-secondary"
                >
                  {oauthBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
                  Connect
                </Button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Client ID (optional)">
                <Input value={clientId} onChange={(e) => setClientId(e.target.value)} className="bg-secondary/40 font-mono text-[13px]" />
              </Field>
              <Field label="Client secret (optional)">
                <PasswordInput value={clientSecret} onChange={setClientSecret} placeholder="••••••••••••••••" />
              </Field>
            </div>
          </>
        )}

        <Field label="Environment variables" hint="Injected into the server process at startup.">
          <EnvVarsField value={envVars} onChange={setEnvVars} />
        </Field>

        <div className="flex items-center justify-between rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
          <div>
            <p className="text-[13px] font-medium text-foreground">Connect after saving</p>
            <p className="text-xs text-muted-foreground">
              {connectAfterSave ? "The agent will use this server immediately." : "Saved but left disconnected."}
            </p>
          </div>
          <Switch checked={connectAfterSave} onCheckedChange={setConnectAfterSave} aria-label="Connect after saving" />
        </div>

        <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-foreground">Test connection</p>
            <p className="truncate text-xs text-muted-foreground">
              {testState.state === "ok" && (
                <span className="flex items-center gap-1 text-emerald-400">
                  <CheckCircle2 className="h-3 w-3" />
                  {testState.detail}
                </span>
              )}
              {testState.state === "fail" && <span className="text-red-400">{testState.detail}</span>}
              {testState.state === "idle" && "Verify the server before saving"}
              {testState.state === "testing" && "Connecting…"}
            </p>
          </div>
          {testState.state === "testing" ? (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
          ) : (
            <TestConnectionButton
              testing={false}
              onTest={() =>
                handleTest().then((r) => {
                  handleTestResult(r.ok, r.detail)
                  return r
                })
              }
            />
          )}
        </div>
      </div>
    </DrawerShell>
  )
}

/* ------------------------------------------------------------------ */
/*  Install from marketplace                                           */
/*  Add-only: installs the plugin and provisions the .mcp.json servers  */
/*  with ${VAR} placeholders intact. Credentials are collected by the   */
/*  Setup dialog on the MCP page (McpSetupDialog), not at install time. */
/* ------------------------------------------------------------------ */
