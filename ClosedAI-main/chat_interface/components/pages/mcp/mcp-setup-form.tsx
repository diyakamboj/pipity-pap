"use client"

import { useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { SetupField } from "./mcp-types"

/* ------------------------------------------------------------------ */
/*  Shared field shell — small and unstyled beyond the input itself.   */
/* ------------------------------------------------------------------ */

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-[13px] font-medium text-foreground">
        {label}
        {required && <span className="ml-1 text-red-400">*</span>}
      </Label>
      {children}
      {hint && <p className="text-[11px] leading-snug text-muted-foreground">{hint}</p>}
    </div>
  )
}

function SecretInput({
  value,
  onChange,
  placeholder,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  disabled?: boolean
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="flex items-center gap-2 rounded-md border border-border/60 bg-secondary/40 px-3 focus-within:border-border">
      <input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="h-9 w-full bg-transparent font-mono text-[13px] text-foreground outline-none placeholder:text-muted-foreground/70 disabled:opacity-60"
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

/* ------------------------------------------------------------------ */
/*  Schema field renderer (text / password / textarea / select / bool) */
/*  Only ever used for genuinely user-owned values that can't be        */
/*  pre-configured on the backend — in practice, just Postgres'         */
/*  connection string. Every OAuth integration's credentials live in    */
/*  the centralized backend config (see oauth_provider_config.py) and   */
/*  never reach this form.                                              */
/* ------------------------------------------------------------------ */

export function SetupFields({
  fields,
  values,
  onChange,
  disabled,
}: {
  fields: SetupField[]
  values: Record<string, string | boolean>
  onChange: (next: Record<string, string | boolean>) => void
  disabled?: boolean
}) {
  if (!fields || fields.length === 0) return null

  const set = (name: string, value: string | boolean) => onChange({ ...values, [name]: value })

  return (
    <div className="flex flex-col gap-3">
      {fields.map((field) => {
        const raw = values[field.name]
        const current = typeof raw === "boolean" ? (raw ? "true" : "false") : (raw as string | undefined) ?? ""
        return (
          <Field key={field.name} label={field.label} hint={field.hint} required={field.required}>
            {field.type === "boolean" ? (
              <Switch
                checked={Boolean(raw)}
                onCheckedChange={(b) => set(field.name, b)}
                disabled={disabled}
                aria-label={field.label}
              />
            ) : field.type === "select" ? (
              <Select
                value={current}
                onValueChange={(val) => set(field.name, val)}
                disabled={disabled}
              >
                <SelectTrigger className="bg-secondary/40">
                  <SelectValue placeholder={field.placeholder ?? "Select…"} />
                </SelectTrigger>
                <SelectContent>
                  {field.options?.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : field.type === "textarea" ? (
              <Textarea
                value={current}
                onChange={(e) => set(field.name, e.target.value)}
                placeholder={field.placeholder}
                disabled={disabled}
                className="min-h-[64px] resize-none bg-secondary/40 font-mono text-[13px]"
              />
            ) : field.type === "password" || field.secret ? (
              <SecretInput
                value={current}
                onChange={(v) => set(field.name, v)}
                placeholder={field.placeholder}
                disabled={disabled}
              />
            ) : (
              <Input
                value={current}
                onChange={(e) => set(field.name, e.target.value)}
                placeholder={field.placeholder}
                disabled={disabled}
                className="bg-secondary/40 font-mono text-[13px]"
              />
            )}
          </Field>
        )
      })}
    </div>
  )
}
