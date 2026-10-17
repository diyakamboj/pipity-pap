"use client"

/**
 * ui-block-canvas.tsx
 *
 * The generative UI rendering layer for the Side Canvas.
 *
 * The server-side Canvas pipeline emits structured UI blocks
 * ({type, version, props}) after a completed agent turn.
 * This module:
 *   1. Maps each block type to a pre-built React component via REGISTRY
 *   2. Renders blocks as the matching component
 *   3. Falls back to a visible error card for unknown/malformed blocks — never crashes
 *
 * Adapted from agent-ui-block-pack-v2.jsx (58 block types) with dark-mode theme
 * overrides to match the app's existing dark canvas palette.
 *
 * EXPORTS (public surface):
 *   UiBlockCanvas({ blocks: CanvasBlock[] }): JSX.Element
 *   REGISTRY: Record<string, React.ComponentType<{ props: any }>>
 */

import React, { useEffect, useState } from "react"
import ReactMarkdown from "react-markdown"
import { MARKDOWN_COMPONENTS, MARKDOWN_PLUGINS } from "@/components/chat-conversation"
import type { CanvasBlock } from "@/lib/canvas-types"
import {
  ListChecks, Mail, Table2, CheckCircle2, Circle, ChevronRight,
  Code2, AlertTriangle, Send, Trash2, Check, X, Clock, User,
  Users, BarChart3, LineChart as LineChartIcon, PieChart as PieChartIcon,
  Gauge as GaugeIcon, GitBranch, MessageSquare, Info, Quote as QuoteIcon,
  FileCode2, Tag, LayoutGrid, TrendingUp, TrendingDown, Minus, Plus,
  Briefcase, Calendar, Star, Paperclip, MapPin, Download, Mail as MailIcon,
  Phone, Activity, Sparkles, FileText, Search, HelpCircle, PenTool,
  ToggleLeft, Wallet, Flag, MessageCircle, Layers, ClipboardList,
  ArrowLeftRight, ListTodo, Link2, ChevronDown, Inbox, ListOrdered,
} from "lucide-react"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts"

/* ---------------------------------------------------------------------- */
/*  DARK-THEMED BLOCK SHELL (overrides the light-colored original)         */
/* ---------------------------------------------------------------------- */

// Named tones mapped to dark-palette accent classes
const TONE_CLASSES: Record<string, string> = {
  violet: "border-violet-500/30 text-violet-400",
  teal:   "border-teal-500/30 text-teal-400",
  amber:  "border-amber-500/30 text-amber-400",
  emerald:"border-emerald-500/30 text-emerald-400",
  red:    "border-red-500/30 text-red-400",
  blue:   "border-blue-500/30 text-blue-400",
  pink:   "border-pink-500/30 text-pink-400",
  slate:  "border-white/10 text-neutral-400",
}

function toneAccent(tone?: string): string {
  if (!tone) return TONE_CLASSES.violet
  if (TONE_CLASSES[tone]) return TONE_CLASSES[tone]
  // hex color — use inline style instead (returned separately, caller handles)
  return "border-white/10 text-neutral-400"
}

const CHART_COLORS = ["#a78bfa", "#2dd4bf", "#fb923c", "#f472b6", "#60a5fa", "#facc15"]
const STATUS_DOT: Record<string, string> = {
  active: "bg-emerald-500", away: "bg-amber-500", pto: "bg-neutral-500", offline: "bg-neutral-700"
}
const STATUS_LABEL: Record<string, string> = {
  active: "Active now", away: "Away", pto: "On leave", offline: "Offline"
}

function initials(name: string): string {
  return (name || "?").split(" ").map((p: string) => p[0]).filter(Boolean).slice(0, 2).join("").toUpperCase()
}

function Avatar({ name, size = "w-9 h-9", status, textSize = "text-xs" }: {
  name: string; size?: string; status?: string; textSize?: string
}) {
  return (
    <div className={`relative ${size} rounded-full bg-violet-500/15 border border-violet-500/25 flex items-center justify-center ${textSize} font-medium text-violet-400 shrink-0`}>
      {initials(name)}
      {status && <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-[#0a0a0a] ${STATUS_DOT[status] || "bg-neutral-600"}`} />}
    </div>
  )
}

// Dark-themed shell that wraps every block
function BlockShell({ icon: Icon, label, children }: {
  icon: React.ComponentType<{ className?: string }>; label: string; children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06] bg-white/[0.015]">
        <Icon className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[10px] font-mono text-neutral-500 tracking-wide">{label}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

// Error / unknown-type fallback card
function UnknownBlock({ error, raw }: { error: string; raw?: string }) {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.05] p-3">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-[11px] font-medium text-amber-400">ui-block error — {error}</span>
      </div>
      {raw && (
        <pre className="text-[10px] font-mono text-neutral-400 overflow-x-auto whitespace-pre-wrap break-words leading-relaxed">
          {raw}
        </pre>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/*  PEOPLE BLOCKS                                                           */
/* ---------------------------------------------------------------------- */

function EmployeeCardCompact({ props }: { props: any }) {
  const { name, role, status = "active" } = props
  return (
    <BlockShell icon={User} label="employee-card-compact · v1">
      <div className="flex items-center gap-3">
        <Avatar name={name} status={status} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-neutral-100 truncate">{name}</div>
          <div className="text-xs text-neutral-400 truncate">{role}</div>
        </div>
      </div>
    </BlockShell>
  )
}

function EmployeeCardDetailed({ props }: { props: any }) {
  const { name, role, team, status = "active", email, tenure, projects } = props
  return (
    <BlockShell icon={User} label="employee-card-detailed · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} status={status} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-neutral-100 truncate">{name}</div>
          <div className="text-xs text-neutral-400 truncate">{role}{team ? ` · ${team}` : ""}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 pt-3 border-t border-white/[0.06]">
        {tenure && <div><div className="text-[10px] text-neutral-500">Tenure</div><div className="text-xs text-neutral-300">{tenure}</div></div>}
        {projects != null && <div><div className="text-[10px] text-neutral-500">Projects</div><div className="text-xs text-neutral-300">{projects}</div></div>}
        {email && <div className="col-span-2"><div className="text-[10px] text-neutral-500">Email</div><div className="text-xs font-mono text-neutral-400">{email}</div></div>}
      </div>
    </BlockShell>
  )
}

function EmployeeCardAvailability({ props }: { props: any }) {
  const { name, role, week = [] } = props
  return (
    <BlockShell icon={Calendar} label="employee-card-availability · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} size="w-8 h-8" textSize="text-[10px]" />
        <div className="min-w-0">
          <div className="text-sm font-medium text-neutral-100 truncate">{name}</div>
          <div className="text-xs text-neutral-400 truncate">{role}</div>
        </div>
      </div>
      <div className="flex gap-1.5">
        {week.map((d: any, i: number) => (
          <div key={i} className="flex-1 text-center">
            <div className="text-[9px] text-neutral-500 mb-1">{d.day}</div>
            <div className={`h-6 rounded ${d.free ? "bg-emerald-500/20 border border-emerald-500/30" : "bg-white/[0.03] border border-white/[0.07]"}`} />
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function EmployeeCardContact({ props }: { props: any }) {
  const { name, role, email, phone, status = "active" } = props
  return (
    <BlockShell icon={Phone} label="employee-card-contact · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} status={status} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-neutral-100 truncate">{name}</div>
          <div className="text-xs text-neutral-400 truncate">{role} · {STATUS_LABEL[status] || status}</div>
        </div>
      </div>
      <div className="space-y-1.5">
        {email && <div className="flex items-center gap-2 text-xs text-neutral-400"><MailIcon className="w-3 h-3 text-neutral-500" /><span className="font-mono">{email}</span></div>}
        {phone && <div className="flex items-center gap-2 text-xs text-neutral-400"><Phone className="w-3 h-3 text-neutral-500" /><span className="font-mono">{phone}</span></div>}
      </div>
    </BlockShell>
  )
}

function EmployeeCardStats({ props }: { props: any }) {
  const { name, role, stats = [] } = props
  return (
    <BlockShell icon={Briefcase} label="employee-card-stats · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-neutral-100 truncate">{name}</div>
          <div className="text-xs text-neutral-400 truncate">{role}</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {stats.map((s: any, i: number) => (
          <div key={i} className="text-center rounded-lg bg-white/[0.03] border border-white/[0.06] py-2">
            <div className="text-sm font-medium text-neutral-100">{s.value}</div>
            <div className="text-[10px] text-neutral-500">{s.label}</div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function TeamRoster({ props }: { props: any }) {
  const { title, members = [] } = props
  return (
    <BlockShell icon={Users} label="team-roster · v1">
      {title && <h4 className="text-sm font-medium text-neutral-100 mb-3">{title}</h4>}
      <div className="space-y-2.5">
        {members.map((m: any, i: number) => (
          <div key={i} className="flex items-center gap-2.5">
            <Avatar name={m.name} size="w-7 h-7" textSize="text-[10px]" status={m.status || "active"} />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-neutral-200 truncate">{m.name}</div>
              <div className="text-[11px] text-neutral-500 truncate">{m.role}</div>
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function OrgNode({ props }: { props: any }) {
  const { name, role, reports = [] } = props
  return (
    <BlockShell icon={GitBranch} label="org-node · v1">
      <div className="flex items-center gap-3 mb-4">
        <Avatar name={name} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-neutral-100">{name}</div>
          <div className="text-xs text-neutral-400">{role}</div>
        </div>
      </div>
      {reports.length > 0 && (
        <div className="pl-3 border-l border-white/[0.07] space-y-2">
          {reports.map((r: any, i: number) => (
            <div key={i} className="flex items-center gap-2">
              <Avatar name={r.name} size="w-6 h-6" textSize="text-[9px]" />
              <div className="min-w-0">
                <div className="text-xs text-neutral-200 truncate">{r.name}</div>
                <div className="text-[10px] text-neutral-500 truncate">{r.role}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </BlockShell>
  )
}

function AvatarGroup({ props }: { props: any }) {
  const { names = [], label } = props
  return (
    <BlockShell icon={Users} label="avatar-group · v1">
      <div className="flex items-center gap-3">
        <div className="flex -space-x-2">
          {names.slice(0, 6).map((n: string, i: number) => (
            <Avatar key={i} name={n} size="w-8 h-8" textSize="text-[10px]" />
          ))}
          {names.length > 6 && (
            <div className="w-8 h-8 rounded-full bg-white/[0.06] border border-white/[0.08] flex items-center justify-center text-[10px] text-neutral-400">
              +{names.length - 6}
            </div>
          )}
        </div>
        {label && <span className="text-xs text-neutral-400">{label}</span>}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  DATA & CHART BLOCKS                                                     */
/* ---------------------------------------------------------------------- */

function StatGrid({ props }: { props: any }) {
  const { title, stats = [] } = props
  return (
    <BlockShell icon={BarChart3} label="stat-grid · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3 uppercase tracking-wide">{title}</h4>}
      <div className="grid grid-cols-2 gap-2">
        {stats.map((s: any, i: number) => (
          <div key={i} className="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3">
            <div className="text-lg font-semibold text-neutral-100 tabular-nums">{s.value}</div>
            <div className="text-[10px] text-neutral-500 mt-0.5">{s.label}</div>
            {s.delta && (
              <div className={`flex items-center gap-1 text-[10px] mt-1 ${s.delta > 0 ? "text-emerald-400" : "text-red-400"}`}>
                {s.delta > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {Math.abs(s.delta)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function StatHero({ props }: { props: any }) {
  const { value, label, sub, tone } = props
  return (
    <BlockShell icon={Activity} label="stat-hero · v1">
      <div className="text-center py-2">
        <div className="text-4xl font-bold text-neutral-50 tabular-nums">{value}</div>
        <div className="text-sm text-neutral-300 mt-1">{label}</div>
        {sub && <div className="text-xs text-neutral-500 mt-0.5">{sub}</div>}
      </div>
    </BlockShell>
  )
}

function BarChartBlock({ props }: { props: any }) {
  const { title, data = [], xKey = "label", yKey = "value" } = props
  return (
    <BlockShell icon={BarChart3} label="bar-chart · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#6b7280" }} />
          <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
          <Tooltip contentStyle={{ backgroundColor: "#0f0f0f", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11 }} />
          <Bar dataKey={yKey} fill="#a78bfa" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </BlockShell>
  )
}

function LineChartBlock({ props }: { props: any }) {
  const { title, data = [], xKey = "label", yKey = "value" } = props
  return (
    <BlockShell icon={LineChartIcon} label="line-chart · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#6b7280" }} />
          <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
          <Tooltip contentStyle={{ backgroundColor: "#0f0f0f", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11 }} />
          <Line type="monotone" dataKey={yKey} stroke="#a78bfa" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </BlockShell>
  )
}

function AreaChartBlock({ props }: { props: any }) {
  const { title, data = [], xKey = "label", yKey = "value" } = props
  return (
    <BlockShell icon={LineChartIcon} label="area-chart · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="areag" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#6b7280" }} />
          <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
          <Tooltip contentStyle={{ backgroundColor: "#0f0f0f", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11 }} />
          <Area type="monotone" dataKey={yKey} stroke="#a78bfa" strokeWidth={2} fill="url(#areag)" />
        </AreaChart>
      </ResponsiveContainer>
    </BlockShell>
  )
}

function DonutChart({ props }: { props: any }) {
  const { title, slices = [], data = [] } = props
  const chartData = slices.length ? slices : data
  return (
    <BlockShell icon={PieChartIcon} label="donut-chart · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-2">{title}</h4>}
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={100} height={100}>
          <PieChart>
            <Pie data={chartData} cx="50%" cy="50%" innerRadius={28} outerRadius={44} dataKey="value" strokeWidth={0}>
              {chartData.map((_: any, i: number) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="space-y-1.5">
          {chartData.map((s: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
              <span className="text-neutral-400">{s.label || s.name}</span>
              <span className="text-neutral-200 font-medium tabular-nums">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </BlockShell>
  )
}

function GaugeBlock({ props }: { props: any }) {
  const { value, max = 100, label, tone } = props
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <BlockShell icon={GaugeIcon} label="gauge · v1">
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-neutral-400">{label}</span>
          <span className="text-neutral-200 font-medium tabular-nums">{value} / {max}</span>
        </div>
        <div className="h-3 rounded-full bg-white/[0.06] overflow-hidden">
          <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <div className="text-right text-[10px] text-neutral-500">{Math.round(pct)}%</div>
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  WORKFLOW BLOCKS                                                          */
/* ---------------------------------------------------------------------- */

function Checklist({ props }: { props: any }) {
  const { title, items = [] } = props
  return (
    <BlockShell icon={ListChecks} label="checklist · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-2">
        {items.map((item: any, i: number) => (
          <div key={i} className="flex items-start gap-2.5">
            {item.done
              ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              : <Circle className="w-4 h-4 text-neutral-600 shrink-0 mt-0.5" />}
            <span className={`text-xs leading-relaxed ${item.done ? "line-through text-neutral-500" : "text-neutral-200"}`}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function VerticalStepper({ props }: { props: any }) {
  const { title, steps = [] } = props
  return (
    <BlockShell icon={ListChecks} label="vertical-stepper · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="relative space-y-3">
        {steps.map((step: any, i: number) => {
          const isDone = step.status === "done"
          const isActive = step.status === "active"
          return (
            <div key={i} className="flex items-start gap-3">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-medium border ${
                isDone ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                : isActive ? "bg-violet-500/20 border-violet-500/40 text-violet-400"
                : "bg-white/[0.03] border-white/[0.08] text-neutral-600"
              }`}>
                {isDone ? <Check className="w-3 h-3" /> : i + 1}
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-medium ${isActive ? "text-violet-300" : isDone ? "text-neutral-400 line-through" : "text-neutral-200"}`}>{step.label}</div>
                {step.sub && <div className="text-[10px] text-neutral-500 mt-0.5">{step.sub}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </BlockShell>
  )
}

function HorizontalStepper({ props }: { props: any }) {
  const { steps = [] } = props
  return (
    <BlockShell icon={ArrowLeftRight} label="horizontal-stepper · v1">
      <div className="flex items-center gap-2">
        {steps.map((step: any, i: number) => {
          const isDone = step.status === "done"
          const isActive = step.status === "active"
          return (
            <React.Fragment key={i}>
              <div className="flex flex-col items-center gap-1 min-w-0">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium border ${
                  isDone ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                  : isActive ? "bg-violet-500/20 border-violet-500/40 text-violet-400"
                  : "bg-white/[0.03] border-white/[0.08] text-neutral-600"
                }`}>
                  {isDone ? <Check className="w-3 h-3" /> : i + 1}
                </div>
                <div className={`text-[9px] text-center ${isActive ? "text-violet-300" : "text-neutral-500"}`}>{step.label}</div>
              </div>
              {i < steps.length - 1 && <div className={`flex-1 h-px ${isDone ? "bg-emerald-500/40" : "bg-white/[0.06]"}`} />}
            </React.Fragment>
          )
        })}
      </div>
    </BlockShell>
  )
}

function ApprovalCard({ props }: { props: any }) {
  const { title, body, approve_label = "Approve", reject_label = "Reject", tone } = props
  const [decided, setDecided] = useState<"approved" | "rejected" | null>(null)
  return (
    <BlockShell icon={CheckCircle2} label="approval-card · v1">
      <h4 className="text-sm font-medium text-neutral-100 mb-2">{title}</h4>
      {body && <p className="text-xs text-neutral-400 leading-relaxed mb-4">{body}</p>}
      {decided ? (
        <div className={`text-xs font-medium ${decided === "approved" ? "text-emerald-400" : "text-red-400"}`}>
          {decided === "approved" ? "✓ Approved" : "✗ Rejected"}
        </div>
      ) : (
        <div className="flex gap-2">
          <button onClick={() => setDecided("approved")} className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors">
            {approve_label}
          </button>
          <button onClick={() => setDecided("rejected")} className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors">
            {reject_label}
          </button>
        </div>
      )}
    </BlockShell>
  )
}

function ApprovalCompact({ props }: { props: any }) {
  return <ApprovalCard props={{ ...props, _compact: true }} />
}

function Timeline({ props }: { props: any }) {
  const { title, events = [] } = props
  return (
    <BlockShell icon={Clock} label="timeline · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-3">
        {events.map((e: any, i: number) => (
          <div key={i} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="w-2 h-2 rounded-full bg-violet-500 shrink-0 mt-1" />
              {i < events.length - 1 && <div className="w-px flex-1 bg-white/[0.06] mt-1" />}
            </div>
            <div className="min-w-0 pb-3">
              <div className="text-xs font-medium text-neutral-200">{e.label}</div>
              {e.when && <div className="text-[10px] text-neutral-500">{e.when}</div>}
              {e.body && <div className="text-[11px] text-neutral-400 mt-0.5 leading-relaxed">{e.body}</div>}
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function ProgressBar({ props }: { props: any }) {
  const { label, value, max = 100, show_pct = true } = props
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <BlockShell icon={Activity} label="progress-bar · v1">
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-neutral-400">{label}</span>
          {show_pct && <span className="text-neutral-300 font-medium tabular-nums">{Math.round(pct)}%</span>}
        </div>
        <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
          <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  CONTENT BLOCKS                                                          */
/* ---------------------------------------------------------------------- */

function EmailPreview({ props }: { props: any }) {
  const { from, to, subject, body, date } = props
  return (
    <BlockShell icon={Mail} label="email-preview · v1">
      <div className="space-y-2">
        <div className="flex justify-between">
          <span className="text-xs font-medium text-neutral-200">{subject}</span>
          {date && <span className="text-[10px] text-neutral-500">{date}</span>}
        </div>
        <div className="text-[10px] text-neutral-500">
          {from && <span className="mr-3">From: <span className="font-mono">{from}</span></span>}
          {to && <span>To: <span className="font-mono">{to}</span></span>}
        </div>
        {body && (
          <div className="pt-2 border-t border-white/[0.06]">
            <p className="text-xs text-neutral-300 leading-relaxed whitespace-pre-wrap">{body}</p>
          </div>
        )}
      </div>
    </BlockShell>
  )
}

function ChatThread({ props }: { props: any }) {
  const { messages = [] } = props
  return (
    <BlockShell icon={MessageSquare} label="chat-thread · v1">
      <div className="space-y-3">
        {messages.map((m: any, i: number) => (
          <div key={i} className={`flex gap-2 ${m.align === "right" ? "flex-row-reverse" : ""}`}>
            <Avatar name={m.author} size="w-7 h-7" textSize="text-[9px]" />
            <div className={`max-w-[80%] rounded-lg px-2.5 py-1.5 ${m.align === "right" ? "bg-violet-500/20 border border-violet-500/20" : "bg-white/[0.04] border border-white/[0.06]"}`}>
              <div className="text-[10px] text-neutral-500 mb-0.5">{m.author}</div>
              <div className="text-xs text-neutral-200 leading-relaxed">{m.body}</div>
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function AlertBanner({ props }: { props: any }) {
  const { title, body, severity = "info" } = props
  const colors: Record<string, string> = {
    info: "border-blue-500/30 bg-blue-500/[0.06] text-blue-300",
    warning: "border-amber-500/30 bg-amber-500/[0.06] text-amber-300",
    error: "border-red-500/30 bg-red-500/[0.06] text-red-300",
    success: "border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-300",
  }
  const icons: Record<string, any> = { info: Info, warning: AlertTriangle, error: AlertTriangle, success: CheckCircle2 }
  const Icon = icons[severity] || Info
  return (
    <div className={`rounded-xl border p-3 ${colors[severity] || colors.info}`}>
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 shrink-0 mt-0.5" />
        <div>
          {title && <div className="text-xs font-medium mb-0.5">{title}</div>}
          {body && <div className="text-xs opacity-80 leading-relaxed">{body}</div>}
        </div>
      </div>
    </div>
  )
}

function DataTable({ props }: { props: any }) {
  const { title, columns = [], rows = [] } = props
  return (
    <BlockShell icon={Table2} label="data-table · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              {columns.map((c: string, i: number) => (
                <th key={i} className="text-left text-[10px] font-medium text-neutral-500 pb-2 pr-4 uppercase tracking-wide">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row: any[], i: number) => (
              <tr key={i} className="border-t border-white/[0.04]">
                {row.map((cell: any, j: number) => (
                  <td key={j} className="py-2 pr-4 text-neutral-300">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </BlockShell>
  )
}

function Quote({ props }: { props: any }) {
  const { text, attribution } = props
  return (
    <BlockShell icon={QuoteIcon} label="quote · v1">
      <blockquote className="border-l-2 border-violet-500/40 pl-3">
        <p className="text-sm text-neutral-200 italic leading-relaxed">{text}</p>
        {attribution && <footer className="text-[10px] text-neutral-500 mt-2">— {attribution}</footer>}
      </blockquote>
    </BlockShell>
  )
}

function CodeBlock({ props }: { props: any }) {
  const { language, code } = props
  return (
    <BlockShell icon={Code2} label="code-block · v1">
      {language && <div className="text-[10px] text-violet-400 font-mono mb-2">{language}</div>}
      <pre className="text-[11.5px] font-mono text-neutral-300 overflow-x-auto whitespace-pre leading-relaxed">
        {code}
      </pre>
    </BlockShell>
  )
}

function BadgeRow({ props }: { props: any }) {
  const { items = [] } = props
  return (
    <BlockShell icon={Tag} label="badge-row · v1">
      <div className="flex flex-wrap gap-1.5">
        {items.map((b: any, i: number) => (
          <span key={i} className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-white/[0.08] bg-white/[0.04] text-neutral-300">
            {typeof b === "string" ? b : b.label}
          </span>
        ))}
      </div>
    </BlockShell>
  )
}

function RatingBlock({ props }: { props: any }) {
  const { score, max = 5, label } = props
  return (
    <BlockShell icon={Star} label="rating · v1">
      <div className="flex items-center gap-3">
        <div className="flex gap-0.5">
          {Array.from({ length: max }).map((_, i) => (
            <Star key={i} className={`w-4 h-4 ${i < score ? "text-amber-400 fill-amber-400" : "text-neutral-700"}`} />
          ))}
        </div>
        {label && <span className="text-xs text-neutral-400">{label}</span>}
      </div>
    </BlockShell>
  )
}

function AttachmentBlock({ props }: { props: any }) {
  const { filename, size, mime } = props
  return (
    <BlockShell icon={Paperclip} label="attachment · v1">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center">
          <FileText className="w-4 h-4 text-neutral-400" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-neutral-200 truncate">{filename}</div>
          {size && <div className="text-[10px] text-neutral-500">{size}{mime ? ` · ${mime}` : ""}</div>}
        </div>
        <Download className="w-4 h-4 text-neutral-500 shrink-0" />
      </div>
    </BlockShell>
  )
}

function CalendarEvent({ props }: { props: any }) {
  const { title, date, time, location, attendees = [] } = props
  return (
    <BlockShell icon={Calendar} label="calendar-event · v1">
      <div className="space-y-2">
        <div className="text-sm font-medium text-neutral-100">{title}</div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-400">
          {date && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{date}</span>}
          {time && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{time}</span>}
          {location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{location}</span>}
        </div>
        {attendees.length > 0 && (
          <div className="pt-2 border-t border-white/[0.06]">
            <div className="text-[10px] text-neutral-500 mb-1.5">Attendees</div>
            <div className="flex -space-x-2">
              {attendees.slice(0, 5).map((name: string, i: number) => (
                <Avatar key={i} name={name} size="w-7 h-7" textSize="text-[9px]" />
              ))}
              {attendees.length > 5 && (
                <div className="w-7 h-7 rounded-full bg-white/[0.06] border border-white/[0.08] flex items-center justify-center text-[9px] text-neutral-400">
                  +{attendees.length - 5}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  FORM & INPUT BLOCKS                                                     */
/* ---------------------------------------------------------------------- */

function FieldSummary({ props }: { props: any }) {
  const { title, fields = [] } = props
  return (
    <BlockShell icon={ClipboardList} label="field-summary · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-2.5">
        {fields.map((f: any, i: number) => (
          <div key={i} className="flex justify-between gap-4">
            <span className="text-[10px] text-neutral-500 uppercase tracking-wide shrink-0">{f.label}</span>
            <span className="text-xs text-neutral-200 text-right">{f.value ?? <em className="text-neutral-600">—</em>}</span>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function Poll({ props }: { props: any }) {
  const { question, options = [] } = props
  const [voted, setVoted] = useState<number | null>(null)
  return (
    <BlockShell icon={LayoutGrid} label="poll · v1">
      <h4 className="text-sm font-medium text-neutral-100 mb-3">{question}</h4>
      <div className="space-y-2">
        {options.map((o: any, i: number) => (
          <button key={i} onClick={() => setVoted(i)}
            className={`w-full text-left text-xs px-3 py-2 rounded-lg border transition-colors ${
              voted === i
                ? "border-violet-500/40 bg-violet-500/15 text-violet-300"
                : "border-white/[0.07] bg-white/[0.02] text-neutral-300 hover:bg-white/[0.05]"
            }`}>
            {typeof o === "string" ? o : o.label}
          </button>
        ))}
      </div>
    </BlockShell>
  )
}

function SignatureBlock({ props }: { props: any }) {
  const { name, role, date, signed = false } = props
  return (
    <BlockShell icon={PenTool} label="signature-block · v1">
      <div className="space-y-3">
        <div className="h-12 rounded-lg border border-dashed border-white/[0.1] bg-white/[0.01] flex items-center justify-center">
          {signed
            ? <span className="text-sm font-medium text-emerald-400 italic">{name}</span>
            : <span className="text-xs text-neutral-600">Signature required</span>}
        </div>
        <div className="flex justify-between text-xs text-neutral-500">
          <span>{name}{role ? ` · ${role}` : ""}</span>
          {date && <span>{date}</span>}
        </div>
      </div>
    </BlockShell>
  )
}

function ToggleSetting({ props }: { props: any }) {
  const { label, description, on = false } = props
  const [enabled, setEnabled] = useState(on)
  return (
    <BlockShell icon={ToggleLeft} label="toggle-setting · v1">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-medium text-neutral-200">{label}</div>
          {description && <div className="text-[10px] text-neutral-500 mt-0.5">{description}</div>}
        </div>
        <button onClick={() => setEnabled(!enabled)}
          className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${enabled ? "bg-violet-500" : "bg-white/[0.08]"}`}>
          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? "translate-x-4" : "translate-x-0.5"}`} />
        </button>
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  DIRECTORY BLOCKS                                                        */
/* ---------------------------------------------------------------------- */

function DocumentPreview({ props }: { props: any }) {
  const { filename, excerpt, pages, type } = props
  return (
    <BlockShell icon={FileText} label="document-preview · v1">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center shrink-0">
          <FileText className="w-4 h-4 text-neutral-400" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-neutral-200 truncate">{filename}</div>
          {(type || pages) && (
            <div className="text-[10px] text-neutral-500 mt-0.5">
              {type}{type && pages ? " · " : ""}{pages ? `${pages} pages` : ""}
            </div>
          )}
          {excerpt && <p className="text-[11px] text-neutral-400 mt-2 leading-relaxed">{excerpt}</p>}
        </div>
      </div>
    </BlockShell>
  )
}

function SearchResults({ props }: { props: any }) {
  const { title, results = [] } = props
  return (
    <BlockShell icon={Search} label="search-results · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-3">
        {results.map((r: any, i: number) => (
          <div key={i} className="space-y-0.5">
            <div className="text-xs font-medium text-violet-400">{r.title}</div>
            {r.url && <div className="text-[10px] font-mono text-neutral-500 truncate">{r.url}</div>}
            {r.excerpt && <div className="text-[11px] text-neutral-400 leading-relaxed">{r.excerpt}</div>}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function FaqBlock({ props }: { props: any }) {
  const { items = [] } = props
  const [open, setOpen] = useState<number | null>(null)
  return (
    <BlockShell icon={HelpCircle} label="faq · v1">
      <div className="space-y-2">
        {items.map((item: any, i: number) => (
          <div key={i} className="border border-white/[0.06] rounded-lg overflow-hidden">
            <button onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex justify-between items-center px-3 py-2 text-xs font-medium text-neutral-200 hover:bg-white/[0.03] transition-colors">
              {item.q}
              <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 transition-transform ${open === i ? "rotate-180" : ""}`} />
            </button>
            {open === i && (
              <div className="px-3 py-2 border-t border-white/[0.05]">
                <p className="text-[11px] text-neutral-400 leading-relaxed">{item.a}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function KeyValue({ props }: { props: any }) {
  const { title, pairs = [] } = props
  return (
    <BlockShell icon={Layers} label="key-value · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <dl className="space-y-2">
        {pairs.map((p: any, i: number) => (
          <div key={i} className="flex justify-between gap-4 text-xs">
            <dt className="text-neutral-500 shrink-0">{p.key}</dt>
            <dd className="text-neutral-200 text-right font-medium">{p.value}</dd>
          </div>
        ))}
      </dl>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  METRICS BLOCKS                                                          */
/* ---------------------------------------------------------------------- */

function BalanceMeter({ props }: { props: any }) {
  const { label, left, right, value, max = 100 } = props
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <BlockShell icon={Wallet} label="balance-meter · v1">
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-neutral-400">
          <span>{left}</span>
          <span>{right}</span>
        </div>
        <div className="h-3 rounded-full bg-white/[0.06] overflow-hidden">
          <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        {label && <div className="text-center text-[10px] text-neutral-500">{label}</div>}
      </div>
    </BlockShell>
  )
}

function SpendBreakdown({ props }: { props: any }) {
  return <DonutChart props={props} />
}

function BeforeAfter({ props }: { props: any }) {
  const { title, before, after } = props
  return (
    <BlockShell icon={ArrowLeftRight} label="before-after · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-white/[0.02] border border-white/[0.06] p-3">
          <div className="text-[10px] text-neutral-500 mb-1 uppercase tracking-wide">Before</div>
          <div className="text-sm font-medium text-neutral-300">{before}</div>
        </div>
        <div className="rounded-lg bg-violet-500/[0.08] border border-violet-500/20 p-3">
          <div className="text-[10px] text-violet-400 mb-1 uppercase tracking-wide">After</div>
          <div className="text-sm font-medium text-violet-200">{after}</div>
        </div>
      </div>
    </BlockShell>
  )
}

function Milestones({ props }: { props: any }) {
  const { title, items = [] } = props
  return (
    <BlockShell icon={Flag} label="milestones · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-2.5">
        {items.map((m: any, i: number) => (
          <div key={i} className="flex items-center gap-3">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${m.done ? "bg-emerald-500/20 border border-emerald-500/40" : "bg-white/[0.03] border border-white/[0.08]"}`}>
              {m.done ? <Check className="w-3 h-3 text-emerald-400" /> : <span className="w-2 h-2 rounded-full bg-white/[0.15]" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className={`text-xs font-medium ${m.done ? "text-neutral-400 line-through" : "text-neutral-200"}`}>{m.label}</div>
              {m.date && <div className="text-[10px] text-neutral-500">{m.date}</div>}
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  GENERAL PURPOSE BLOCKS                                                  */
/* ---------------------------------------------------------------------- */

function FreeformCard({ props }: { props: any }) {
  const { icon: iconName, title, subtitle, body, tone, actions = [] } = props
  const icons: Record<string, any> = {
    sparkles: Sparkles, flag: Flag, alert: AlertTriangle, check: CheckCircle2,
    info: Info, user: User, users: Users, file: FileText, mail: Mail,
    briefcase: Briefcase, calendar: Calendar, clock: Clock, code: Code2,
    layers: Layers, star: Star, search: Search,
  }
  const Icon = icons[iconName] || Sparkles
  return (
    <BlockShell icon={Icon} label="freeform-card · v1">
      <div className="space-y-2">
        {title && <div className="text-sm font-medium text-neutral-100">{title}</div>}
        {subtitle && <div className="text-xs text-neutral-400">{subtitle}</div>}
        {body && (
          <div className="text-xs text-neutral-300 leading-relaxed max-w-none prose prose-invert prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-sm">
            <ReactMarkdown components={MARKDOWN_COMPONENTS} remarkPlugins={MARKDOWN_PLUGINS}>
              {body}
            </ReactMarkdown>
          </div>
        )}
        {actions.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {actions.map((a: any, i: number) => (
              <button key={i} className="text-[11px] font-medium px-2.5 py-1 rounded-lg border border-violet-500/30 bg-violet-500/10 text-violet-300 hover:bg-violet-500/20 transition-colors">
                {a.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </BlockShell>
  )
}

function StatStrip({ props }: { props: any }) {
  const { stats = [] } = props
  return (
    <BlockShell icon={BarChart3} label="stat-strip · v1">
      <div className="flex divide-x divide-white/[0.06]">
        {stats.map((s: any, i: number) => (
          <div key={i} className={`flex-1 text-center ${i > 0 ? "pl-3" : ""} ${i < stats.length - 1 ? "pr-3" : ""}`}>
            <div className="text-base font-semibold text-neutral-100 tabular-nums">{s.value}</div>
            <div className="text-[10px] text-neutral-500">{s.label}</div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function IconList({ props }: { props: any }) {
  const { title, items = [] } = props
  const icons: Record<string, any> = {
    check: CheckCircle2, x: X, warning: AlertTriangle, info: Info, star: Star,
    clock: Clock, flag: Flag, user: User, briefcase: Briefcase, sparkles: Sparkles,
  }
  return (
    <BlockShell icon={ListChecks} label="icon-list · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-2">
        {items.map((item: any, i: number) => {
          const Icon = (item.icon && icons[item.icon]) || CheckCircle2
          return (
            <div key={i} className="flex items-start gap-2.5">
              <Icon className="w-3.5 h-3.5 text-violet-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs text-neutral-200">{item.label}</div>
                {item.meta && <div className="text-[10px] text-neutral-500">{item.meta}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </BlockShell>
  )
}

function LinkPreview({ props }: { props: any }) {
  const { title, url, description, domain } = props
  return (
    <BlockShell icon={Link2} label="link-preview · v1">
      <div className="space-y-1">
        {(domain || url) && <div className="text-[10px] font-mono text-neutral-500">{domain || url}</div>}
        {title && <div className="text-xs font-medium text-violet-300">{title}</div>}
        {description && <div className="text-[11px] text-neutral-400 leading-relaxed">{description}</div>}
      </div>
    </BlockShell>
  )
}

function AccordionBlock({ props }: { props: any }) {
  const { title, defaultOpen = 0, items = [] } = props
  const [openIndex, setOpenIndex] = useState<number>(defaultOpen)
  return (
    <BlockShell icon={ChevronDown} label="accordion · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-1.5">
        {items.map((item: any, i: number) => (
          <div key={i} className="border border-white/[0.06] rounded-lg overflow-hidden">
            <button onClick={() => setOpenIndex(openIndex === i ? -1 : i)}
              className="w-full flex justify-between items-center px-3 py-2 text-xs font-medium text-neutral-200 hover:bg-white/[0.03] transition-colors">
              {item.title}
              <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 transition-transform ${openIndex === i ? "rotate-180" : ""}`} />
            </button>
            {openIndex === i && (
              <div className="px-3 py-2 border-t border-white/[0.05]">
                <p className="text-[11px] text-neutral-400 leading-relaxed">{item.body}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function TagCloud({ props }: { props: any }) {
  const { title, tags = [] } = props
  return (
    <BlockShell icon={Tag} label="tag-cloud · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-2">{title}</h4>}
      <div className="flex flex-wrap gap-1.5">
        {tags.map((t: any, i: number) => {
          const label = typeof t === "string" ? t : t.label
          return (
            <span key={i} className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-white/[0.08] bg-white/[0.04] text-neutral-300">
              {label}
            </span>
          )
        })}
      </div>
    </BlockShell>
  )
}

function EmptyState({ props }: { props: any }) {
  const { icon: iconName, title, message, cta } = props
  const icons: Record<string, any> = { sparkles: Sparkles, inbox: Inbox, search: Search, users: Users }
  const Icon = (iconName && icons[iconName]) || Inbox
  return (
    <BlockShell icon={Icon} label="empty-state · v1">
      <div className="flex flex-col items-center text-center gap-2 py-4">
        <Icon className="w-8 h-8 text-neutral-600" />
        {title && <div className="text-sm font-medium text-neutral-300">{title}</div>}
        {message && <div className="text-xs text-neutral-500 leading-relaxed max-w-[200px]">{message}</div>}
        {cta && (
          <button className="mt-1 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-violet-500/15 border border-violet-500/25 text-violet-300 hover:bg-violet-500/25 transition-colors">
            {cta}
          </button>
        )}
      </div>
    </BlockShell>
  )
}

function DividerLabel({ props }: { props: any }) {
  const { label } = props
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="flex-1 h-px bg-white/[0.06]" />
      <span className="text-[10px] font-medium text-neutral-500 uppercase tracking-wide">{label}</span>
      <div className="flex-1 h-px bg-white/[0.06]" />
    </div>
  )
}

function CustomList({ props }: { props: any }) {
  const { title, items = [], ordered = false } = props
  return (
    <BlockShell icon={ordered ? ListOrdered : ListTodo} label="custom-list · v1">
      {title && <h4 className="text-xs font-medium text-neutral-400 mb-3">{title}</h4>}
      <div className="space-y-2">
        {items.map((item: any, i: number) => (
          <div key={i} className="flex items-start gap-2.5">
            <span className="text-[10px] text-neutral-600 mt-0.5 shrink-0 tabular-nums w-4">{ordered ? `${i + 1}.` : "•"}</span>
            <div className="min-w-0">
              <div className="text-xs text-neutral-200">{item.label}</div>
              {item.meta && <div className="text-[10px] text-neutral-500">{item.meta}</div>}
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  REGISTRY                                                               */
/* ---------------------------------------------------------------------- */

export const REGISTRY: Record<string, React.ComponentType<{ props: any }>> = {
  // People
  "employee-card-compact": EmployeeCardCompact,
  "employee-card-detailed": EmployeeCardDetailed,
  "employee-card-availability": EmployeeCardAvailability,
  "employee-card-contact": EmployeeCardContact,
  "employee-card-stats": EmployeeCardStats,
  "team-roster": TeamRoster,
  "org-node": OrgNode,
  "avatar-group": AvatarGroup,
  // Data & charts
  "stat-grid": StatGrid,
  "stat-hero": StatHero,
  "bar-chart": BarChartBlock,
  "line-chart": LineChartBlock,
  "area-chart": AreaChartBlock,
  "donut-chart": DonutChart,
  "gauge": GaugeBlock,
  // Workflow
  "checklist": Checklist,
  "vertical-stepper": VerticalStepper,
  "horizontal-stepper": HorizontalStepper,
  "approval-card": ApprovalCard,
  "approval-compact": ApprovalCompact,
  "timeline": Timeline,
  "progress-bar": ProgressBar,
  // Content
  "email-preview": EmailPreview,
  "chat-thread": ChatThread,
  "alert-banner": AlertBanner,
  "data-table": DataTable,
  "quote": Quote,
  "code-block": CodeBlock,
  "badge-row": BadgeRow,
  "rating": RatingBlock,
  "attachment": AttachmentBlock,
  "calendar-event": CalendarEvent,
  // Forms & input
  "field-summary": FieldSummary,
  "poll": Poll,
  "signature-block": SignatureBlock,
  "toggle-setting": ToggleSetting,
  // Directory
  "document-preview": DocumentPreview,
  "search-results": SearchResults,
  "faq": FaqBlock,
  "key-value": KeyValue,
  // Metrics
  "balance-meter": BalanceMeter,
  "spend-breakdown": SpendBreakdown,
  "before-after": BeforeAfter,
  "milestones": Milestones,
  // General purpose
  "freeform-card": FreeformCard,
  "stat-strip": StatStrip,
  "icon-list": IconList,
  "link-preview": LinkPreview,
  "accordion": AccordionBlock,
  "tag-cloud": TagCloud,
  "empty-state": EmptyState,
  "divider-label": DividerLabel,
  "custom-list": CustomList,
  
  // Aliases for block-catalog.md discrepancies
  "key-value-list": KeyValue,
  "amount-breakdown": SpendBreakdown,
  "approval": ApprovalCard,
  "badge-list": BadgeRow,
  "code-snippet": CodeBlock,
  "comment-thread": ChatThread,
  "comparison-two-column": BeforeAfter,
  "directory-search-result": SearchResults,
  "email": EmailPreview,
  "faq-expandable": FaqBlock,
  "file-attachment": AttachmentBlock,
  "form-field-group": FieldSummary,
  "horizontal-bar-chart": BarChartBlock,
  "metric-comparison": BeforeAfter,
  "milestone-tracker": Milestones,
  "stepper": VerticalStepper,
  "stepper-horizontal": HorizontalStepper,
  "summary-card": FreeformCard,
  "survey-poll": Poll,
  "table": DataTable,
  "task-card": FreeformCard,
  "toggle-settings": ToggleSetting,
}

/* ---------------------------------------------------------------------- */
/*  CANVAS RENDERER                                                         */
/* ---------------------------------------------------------------------- */

export function UiBlockCanvas({
  blocks,
  conversationId,
  turnId,
}: {
  blocks: CanvasBlock[]
  conversationId?: string | null
  turnId?: string | null
}) {
  useEffect(() => {
    if (!blocks.length) return
    console.info('[canvas-trace]', JSON.stringify({
      conversationId: conversationId ?? null,
      turnId: turnId ?? null,
      stage: 'block rendered',
      timestamp: new Date().toISOString(),
      status: 'success',
      count: blocks.length,
    }))
  }, [blocks, conversationId, turnId])

  return (
    <div className="space-y-3">
      {blocks.map((block, i) => {
        const Component = REGISTRY[block.type]
        if (!Component) {
          return <UnknownBlock key={i} error={`no renderer for "${block.type}"`} raw={JSON.stringify(block, null, 2)} />
        }
        return <Component key={i} props={block.props} />
      })}
    </div>
  )
}
