"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { substitutePlaceholders, useMcp } from "@/lib/mcp-store"
import * as mcpApi from "@/lib/mcp-api"
import { SetupFields } from "./mcp-setup-form"
import type { LibraryServer, McpConnection } from "./mcp-types"

/** A few names don't title-case cleanly from their kebab-case id. */
const DISPLAY_NAME_OVERRIDES: Record<string, string> = {
  github: "GitHub",
  "microsoft-365": "Microsoft 365",
}

/** "google-drive" -> "Google Drive", used only for the button label
 *  ("Connect Gmail") — never shown as a description. */
function displayName(id: string): string {
  return DISPLAY_NAME_OVERRIDES[id] ?? id.split("-").map((w) => w[0]?.toUpperCase() + w.slice(1)).join(" ")
}

/** Convert an integration's .mcp.json server template (after ${VAR}
 *  substitution) into a POST /api/mcp/test spec. Uses the same normalization
 *  the store applies to connections: streamable-http -> http. */
function templateToProbeSpec(
  template: Record<string, unknown>,
  values: Record<string, string | boolean>,
): mcpApi.McpTestServerSpec | null {
  const t = JSON.parse(JSON.stringify(template)) as Record<string, unknown>
  substitutePlaceholders(t, values)
  if (t.transport === "stdio" || (typeof t.command === "string" && t.command)) {
    if (typeof t.command !== "string" || !t.command) return null
    return {
      type: "stdio",
      command: t.command,
      args: Array.isArray(t.args) ? (t.args as string[]) : [],
      ...(t.env && typeof t.env === "object" ? { env: t.env as Record<string, string> } : {}),
    }
  }
  if (typeof t.url !== "string" || !t.url) return null
  const remote: Record<string, unknown> = { type: "http", url: t.url }
  if (t.headers && typeof t.headers === "object" && Object.keys(t.headers as object).length > 0) {
    remote.headers = t.headers
  }
  // Preserve auth (especially strategy: "oauth2" + authentication metadata)
  // so the backend OAuth probe recognizes this as an OAuth server.
  if (t.auth && typeof t.auth === "object") {
    remote.auth = t.auth
  }
  return remote as mcpApi.McpTestServerSpec
}

/* ------------------------------------------------------------------ */
/*  Setup popup — deliberately just "Setup" + one button for every      */
/*  OAuth integration. All app credentials (client id/secret, redirect  */
/*  URIs, ...) are pre-configured on the backend (see                   */
/*  oauth_provider_config.py) and never appear here. The single button  */
/*  starts as "Connect {name}" (the OAuth redirect); once that browser   */
/*  flow settles it becomes "Save", which closes the popup. Postgres is  */
/*  the only exception — it genuinely needs a connection string, so its  */
/*  field(s) render above that same single button.                       */
/* ------------------------------------------------------------------ */

export function McpSetupDialog({
  server,
  connection,
  onOpenChange,
}: {
  /** The installed integration (setup schema + .mcp.json templates). */
  server: LibraryServer | null
  /** The provisioned server on the MCP page. */
  connection: McpConnection | null
  onOpenChange: (open: boolean) => void
}) {
  const { saveSecret, patchServerConfig, startOAuth, completeOAuth, load } = useMcp()
  const isOpen = server !== null && connection !== null

  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [oauthState, setOauthState] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)

  // Reset per-target state when the user switches integration/server without
  // closing the dialog in between.
  useEffect(() => {
    setValues({})
    setOauthState(null)
  }, [server?.id, connection?.id])

  if (!server || !connection) return null

  const schema = server.setup
  const templates = server.servers ?? {}
  const serverNames = Object.keys(templates)
  const firstTemplate = serverNames.length > 0 ? (templates[serverNames[0]] as Record<string, unknown> | undefined) : undefined

  const auth = schema?.auth
  const isOAuth = auth?.method === "oauth2"
  const providerReady = !isOAuth || !auth?.provider || auth.provider_configured === true
  const oauthJustConnected = oauthState !== null
  const name = displayName(connection.id)
  const nonAuthFields = (schema?.fields ?? []).filter((f) => f.name !== auth?.token_field)

  const runOAuthFlow = async () => {
    if (!firstTemplate) return
    const spec = templateToProbeSpec(firstTemplate, values)
    if (!spec) return
    setBusy(true)
    try {
      // No client_id/secret here — those are backend deployment config (see
      // oauth_provider_config.py), resolved server-side from the template's
      // `provider` tag. The frontend only ever asks the provider to connect.
      const jobId = await startOAuth(spec, { verifyToolCall: auth?.verify_tool_call })
      if (!jobId) return
      const result = await completeOAuth(jobId, (state) => {
        setOauthState(state)
        void patchServerConfig(connection.id, { auth: { strategy: "oauth2", state } })
      })
      if (result !== "ok") toast.error("Failed to connect — try again")
    } finally {
      setBusy(false)
    }
  }

  const handleSave = async () => {
    setBusy(true)
    try {
      for (const field of nonAuthFields) {
        if (field.required && !String(values[field.name] ?? "").trim()) {
          toast.error(`${field.label} is required`)
          return
        }
      }
      // Non-OAuth fields (Postgres' connection string, etc.) — persisted as
      // global secrets so ${VAR} placeholders resolve at conversation build time.
      for (const [fieldName, value] of Object.entries(values)) {
        if (typeof value === "string" && value.trim()) {
          await saveSecret(fieldName, value.trim())
        }
      }
      await load()
      toast.success(`${name} connected`)
      onOpenChange(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Failed to save ${name}`)
    } finally {
      setBusy(false)
    }
  }

  const handleClick = () => {
    if (isOAuth && !oauthJustConnected) void runOAuthFlow()
    else void handleSave()
  }

  const label = !isOAuth ? "Connect" : oauthJustConnected ? "Save" : busy ? "Connecting…" : `Connect ${name}`
  const disabled = busy || (isOAuth && !providerReady)

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 border-border/60 bg-card p-0 sm:max-w-xs">
        <DialogHeader className="border-b border-border/60 px-5 py-3.5">
          <DialogTitle className="font-heading text-[15px]">Setup</DialogTitle>
        </DialogHeader>

        {(!isOAuth || !providerReady) && (
          <div className="px-5 pt-5">
            {!providerReady ? (
              <p className="text-[11px] leading-snug text-amber-400">
                Needs an administrator to finish backend configuration first.
              </p>
            ) : (
              <SetupFields fields={nonAuthFields} values={values} onChange={setValues} disabled={busy} />
            )}
          </div>
        )}

        <DialogFooter className="px-5 py-5">
          <Button
            onClick={handleClick}
            disabled={disabled}
            className="w-full gap-2 bg-primary text-primary-foreground hover:opacity-90"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {label}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
