"use client"

import { useState, type ReactNode } from "react"
import {
  Search as SearchIcon,
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Check,
  KeyRound,
  Plus,
  Settings,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { OptionMenu } from "@/components/option-menu"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"

/* ------------------------------------------------------------------ */
/*  Drawer (side panel) shell                                          */
/* ------------------------------------------------------------------ */

/* Shared right-side drawer used by the View, Edit, and Run popups so every
   overlay surface shares the same header / scroll / footer rhythm. The body
   owns its own padding so sticky full-bleed tab bars can be placed inside. */
export function DrawerShell({
  open,
  onOpenChange,
  eyebrow,
  title,
  description,
  icon,
  iconClassName,
  meta,
  actions,
  alert,
  children,
  footer,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  eyebrow?: string
  title: ReactNode
  description?: ReactNode
  icon?: ReactNode
  iconClassName?: string
  meta?: ReactNode
  actions?: ReactNode
  alert?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 border-border/60 bg-card p-0 sm:max-w-[720px]">
        <div className="flex h-full flex-col">
          <header className="border-b border-border/60 px-6 py-5 pr-12">
            <div className="flex items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3.5">
                {icon && (
                  <span
                    className={cn(
                      "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border",
                      iconClassName ?? "border-border/60 bg-secondary/60",
                    )}
                  >
                    {icon}
                  </span>
                )}
                <div className="min-w-0">
                  {eyebrow && (
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">{eyebrow}</p>
                  )}
                  <SheetTitle className="mt-1 font-heading text-xl font-semibold leading-tight text-foreground">
                    {title}
                  </SheetTitle>
                  {description && (
                    <SheetDescription className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                      {description}
                    </SheetDescription>
                  )}
                  {meta && <div className="mt-2 flex flex-wrap items-center gap-1.5">{meta}</div>}
                </div>
              </div>
              {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
            </div>
            {alert}
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
          {footer && <footer className="border-t border-border/60 px-6 py-4">{footer}</footer>}
        </div>
      </SheetContent>
    </Sheet>
  )
}

/* Scrollable outer container for every management page. */
export function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="relative z-10 h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1400px] px-6 pt-10 pb-14 sm:px-10 lg:pt-14">{children}</div>
    </div>
  )
}

/* Page header: title, description, optional icon badge, and an optional action slot. */
export function PageHeader({
  title,
  description,
  icon: Icon,
  action,
}: {
  title: string
  description: string
  icon?: LucideIcon
  action?: ReactNode
}) {
  return (
    <header className="dream-in mb-8 flex flex-col gap-5 border-b border-border/60 pb-7 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground text-balance flex items-center gap-3">
          {Icon && (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-secondary/60">
              <Icon className="h-4.5 w-4.5 text-primary" />
            </span>
          )}
          {title}
        </h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground text-pretty">{description}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}

/* Compact metric tile used in overview strips. */
export function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5 transition-colors duration-300 hover:border-border">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-2 font-heading text-2xl font-semibold text-foreground">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

/* Small status pill with a leading dot. */
export function StatusPill({
  active,
  activeLabel = "Connected",
  inactiveLabel = "Disconnected",
}: {
  active: boolean
  activeLabel?: string
  inactiveLabel?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        active
          ? "border-white/20 bg-white/[0.06] text-foreground"
          : "border-border/60 bg-transparent text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          active ? "bg-foreground shadow-[0_0_6px_rgba(255,255,255,0.6)]" : "bg-muted-foreground/50",
        )}
      />
      {active ? activeLabel : inactiveLabel}
    </span>
  )
}

/* Neutral tag chip. */
export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-border/60 bg-secondary/60 px-2 py-0.5 text-[11px] font-medium text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  )
}

/* Search input with a leading icon. */
export function SearchBar({
  value,
  onChange,
  placeholder = "Search...",
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div className="relative flex-1">
      <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-lg border border-border/60 bg-card/40 pl-9 pr-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-border focus:bg-card/70"
      />
    </div>
  )
}

/* Segmented control for switching views, with optional counts. */
export function SegmentedTabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string; count?: number }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border/60 bg-card/40 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "flex items-center gap-2 rounded-md px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-200",
            value === tab.id
              ? "bg-secondary text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span
              className={cn(
                "rounded-full px-1.5 text-[10px] tabular-nums",
                value === tab.id ? "bg-background/60 text-foreground" : "bg-secondary/60 text-muted-foreground",
              )}
            >
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

/* Section heading used to separate groups on a page. */
export function SectionLabel({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-4 mt-10 flex items-baseline gap-2.5">
      <h2 className="font-heading text-sm font-semibold uppercase tracking-wider text-foreground">{children}</h2>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  )
}

/* Section heading row: title, optional count, optional action. */
export function SectionHeader({
  title,
  count,
  action,
}: {
  title: string
  count?: number
  action?: ReactNode
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="font-heading text-[15px] font-semibold text-foreground">{title}</h2>
      <div className="flex items-center gap-3">
        {count !== undefined && <span className="text-xs tabular-nums text-muted-foreground">{count}</span>}
        {action}
      </div>
    </div>
  )
}

/* Single installed-item card used by the Skills and MCP overviews.
   The main row opens the detail panel; the switch and menu stop propagation. */
/* Installed item card: large format with toggle switch and overflow menu. */
export function ItemCard({
  icon,
  name,
  description,
  enabled,
  onToggle,
  onOpen,
  menu,
  toggle,
}: {
  icon: ReactNode
  name: string
  description: string
  enabled: boolean
  /** Required only when `toggle` is omitted and the default enable switch renders. */
  onToggle?: (checked: boolean) => void
  onOpen: () => void
  menu?: ReactNode
  /** Optional replacement for the enable switch (e.g. a Setup or Uninstall
   *  button for installed servers, which have no soft-disable state). */
  toggle?: ReactNode
}) {
  return (
    <div className="group flex items-start gap-4 rounded-xl border border-border/60 bg-card/40 p-5 transition-colors duration-150 hover:border-border hover:bg-card/70">
      <button
        type="button"
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-start gap-4 rounded-lg text-left outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        aria-label={`Open ${name}`}
      >
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-secondary/60">
          {icon}
        </span>
        <span className="min-w-0 pt-0.5">
          <span className="block truncate text-[15px] font-semibold text-foreground">{name}</span>
          <span className="mt-1 block text-[13px] leading-relaxed text-muted-foreground line-clamp-2">{description}</span>
        </span>
      </button>
      <div className="flex shrink-0 items-center gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
        {toggle ?? <Switch checked={enabled} onCheckedChange={onToggle} aria-label={`Toggle ${name}`} />}
        {menu}
      </div>
    </div>
  )
}

/* Marketplace catalog card: tinted brand chip, one-line description, action slot. */
export function CatalogCard({
  icon,
  tone,
  name,
  description,
  action,
}: {
  icon: ReactNode
  tone?: string
  name: string
  description: string
  action: ReactNode
}) {
  return (
    <div className="group flex items-center gap-3.5 rounded-xl border border-border/60 bg-card/40 px-4 py-3.5 transition-colors duration-150 hover:border-border hover:bg-card/70">
      <span
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border",
          tone ?? "border-border/60 bg-secondary/60 text-foreground",
        )}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[14px] font-semibold text-foreground">{name}</p>
        <p className="mt-0.5 truncate text-[12px] text-muted-foreground">{description}</p>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  )
}

/* Empty state block. */
export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/60 bg-card/20 px-6 py-14 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-border/60 bg-secondary/40 text-muted-foreground">
        {icon}
      </div>
      <p className="font-heading text-[15px] font-semibold text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">{description}</p>
    </div>
  )
}

/* Label + value stacked meta cell. */
export function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground/70">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  )
}

/* Reusable confirmation dialog for destructive actions. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title = "Are you sure?",
  description = "This action cannot be undone.",
  confirmLabel = "Delete",
  destructive = true,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: string
  description?: string
  confirmLabel?: string
  destructive?: boolean
  onConfirm: () => void
}) {
  const [loading, setLoading] = useState(false)

  const handleConfirm = () => {
    setLoading(true)
    // Simulate a brief async action
    setTimeout(() => {
      onConfirm()
      setLoading(false)
      onOpenChange(false)
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm gap-0 border-border/60 bg-card p-0">
        <DialogHeader className="px-6 pt-6 pb-4">
          <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-border/60 bg-red-500/10">
            <AlertTriangle className="h-5 w-5 text-red-400" />
          </div>
          <DialogTitle className="font-heading text-lg">{title}</DialogTitle>
          <DialogDescription className="text-[13px] leading-relaxed text-muted-foreground">
            {description}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="border-t border-border/60 px-6 py-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={loading}
            className={cn(
              "gap-2",
              destructive
                ? "bg-red-500/90 text-white hover:bg-red-500"
                : "bg-primary text-primary-foreground hover:opacity-90",
            )}
          >
            {loading ? "Deleting…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* Timestamped activity log entry with category icon. */
export function ActivityLogEntry({
  icon,
  title,
  detail,
  time,
  status = "default",
}: {
  icon: ReactNode
  title: string
  detail?: string
  time: string
  status?: "default" | "success" | "warning" | "error"
}) {
  const statusColor: Record<string, string> = {
    default: "text-muted-foreground",
    success: "text-emerald-400",
    warning: "text-amber-400",
    error: "text-red-400",
  }

  return (
    <div className="flex items-start gap-3 py-2.5">
      <span
        className={cn(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-secondary/40",
          statusColor[status],
        )}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-foreground">{title}</p>
        {detail && <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>}
      </div>
      <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground/70">{time}</span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Enterprise primitives                                              */
/* ------------------------------------------------------------------ */

/* Horizontal row of toolbar controls. */
export function Toolbar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-2", className)}>{children}</div>
}

/* Dropdown select styled consistently for filter/sort toolbars. */
export function FilterSelect({
  label,
  options,
  value,
  onChange,
  className,
}: {
  label: string
  options: string[]
  value: string
  onChange: (v: string) => void
  className?: string
}) {
  return (
    <OptionMenu
      label={label}
      options={options}
      value={value}
      onChange={onChange}
      align="end"
      trigger={
        <button
          className={cn(
            "flex h-10 shrink-0 items-center gap-1.5 rounded-lg border border-border/60 bg-card/40 px-3.5 text-[13px] text-foreground transition-colors hover:border-border",
            className,
          )}
        >
          <span className="hidden text-muted-foreground/70 sm:inline">{label}:</span>
          <span className="font-medium">{value}</span>
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      }
    />
  )
}

/* Small status badge for success / warning / error / info / neutral. */
const STATUS_STYLES = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  error: "border-red-500/30 bg-red-500/10 text-red-400",
  info: "border-sky-500/30 bg-sky-500/10 text-sky-400",
  neutral: "border-border/60 bg-secondary/40 text-muted-foreground",
} as const

export type StatusTone = keyof typeof STATUS_STYLES

export function StatusBadge({
  status = "neutral",
  children,
  className,
}: {
  status?: StatusTone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium",
        STATUS_STYLES[status],
        className,
      )}
    >
      {children}
    </span>
  )
}

/* Bordered section used inside detail panels. */
export function PanelSection({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn("rounded-lg border border-border/60 bg-card/40", className)}>
      <div className="flex items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
        <div className="min-w-0">
          <h3 className="text-[13px] font-semibold text-foreground">{title}</h3>
          {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

/* Label / value row used inside detail panels. */
export function DetailRow({
  label,
  value,
  mono,
}: {
  label: string
  value: ReactNode
  mono?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5 text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("text-right font-medium text-foreground", mono && "font-mono text-[12px]")}>
        {value}
      </span>
    </div>
  )
}

/* Shared toggle row (label + description + switch). */
export function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0">
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} className="shrink-0" />
    </div>
  )
}

/* Empty row inside a table body. */
export function EmptyTableRow({
  colSpan,
  title,
  description,
}: {
  colSpan: number
  title: string
  description?: string
}) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-16 text-center">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description && <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">{description}</p>}
      </td>
    </tr>
  )
}

/* Skeleton rows shown while a page is loading. */
export function SkeletonRows({ count, colSpan }: { count: number; colSpan: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i} className="border-b border-border/60">
          <td colSpan={colSpan} className="px-4 py-4">
            <div className="h-5 animate-pulse rounded-md bg-secondary/60" />
          </td>
        </tr>
      ))}
    </>
  )
}

/* Compact pagination bar used under tables and logs. */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  if (pageCount <= 1) return null

  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  // Window of up to 5 page buttons around the current page.
  const windowStart = Math.max(1, Math.min(page - 2, pageCount - 4))
  const windowEnd = Math.min(pageCount, Math.max(page + 2, windowStart + 4))
  const pages: number[] = []
  for (let p = windowStart; p <= windowEnd; p++) pages.push(p)

  const pageBtn =
    "flex h-7 min-w-7 items-center justify-center rounded-md border px-2 text-[12px] font-medium transition-colors"

  return (
    <div className="flex items-center justify-between gap-3 border-t border-border/60 px-4 py-2.5 text-xs text-muted-foreground">
      <span className="tabular-nums">
        Showing {start}-{end} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
          className={cn(
            pageBtn,
            "border-border/60 bg-card/40 hover:border-border hover:text-foreground disabled:opacity-40",
          )}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        {pages.map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            aria-current={p === page ? "page" : undefined}
            className={cn(
              pageBtn,
              p === page
                ? "border-border bg-secondary text-foreground"
                : "border-border/60 bg-card/40 hover:border-border hover:text-foreground",
            )}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pageCount}
          aria-label="Next page"
          className={cn(
            pageBtn,
            "border-border/60 bg-card/40 hover:border-border hover:text-foreground disabled:opacity-40",
          )}
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Marketplace large-format cards                                     */
/* ------------------------------------------------------------------ */

export const CATEGORY_TONES: Record<string, string> = {
  Engineering: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
  Productivity: "border-pink-500/20 bg-pink-500/10 text-pink-400",
  Research: "border-amber-500/20 bg-amber-500/10 text-amber-400",
  Communication: "border-sky-500/20 bg-sky-500/10 text-sky-400",
  Data: "border-violet-500/20 bg-violet-500/10 text-violet-400",
  System: "border-orange-500/20 bg-orange-500/10 text-orange-400",
  Custom: "border-orange-500/20 bg-orange-500/10 text-orange-400",
}

function InstalledPill() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 bg-secondary/40 px-3 py-1.5 text-[12px] font-medium text-muted-foreground">
      <Check className="h-3.5 w-3.5" />
      Installed
    </span>
  )
}

/* Large marketplace skill card — matches the reference screenshot style. */
export function MarketplaceSkillCard({
  icon: Icon,
  name,
  description,
  category,
  triggerType,
  installed,
  onInstall,
}: {
  icon: LucideIcon
  name: string
  description: string
  category: string
  triggerType: string
  installed: boolean
  onInstall: () => void
}) {
  const tone = CATEGORY_TONES[category] ?? "border-border/60 bg-secondary/60 text-foreground"

  return (
    <div className="group flex h-full flex-col gap-4 rounded-xl border border-border/60 bg-card/40 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-border hover:bg-card/70 hover:shadow-lg hover:shadow-black/20">
      <div className="flex items-start gap-4">
        <span
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border",
            tone,
          )}
        >
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <h3 className="font-heading text-[15px] font-semibold text-foreground">{name}</h3>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{category}</span>
            <span className="rounded-full border border-border/60 bg-secondary/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              {triggerType}
            </span>
          </div>
        </div>
      </div>
      <p className="text-[13px] leading-relaxed text-muted-foreground line-clamp-2">{description}</p>
      <div className="flex items-center justify-end">
        {installed ? (
          <InstalledPill />
        ) : (
          <Button
            size="sm"
            variant="secondary"
            onClick={onInstall}
            className="gap-1.5 border border-border/60 transition-transform duration-150 active:scale-95"
          >
            <Plus className="h-3.5 w-3.5" />
            Activate
          </Button>
        )}
      </div>
    </div>
  )
}

/* Large marketplace MCP server card — matches the reference screenshot style. */
/** Real backend/plugin-config state, not a frontend guess:
 *  "not-installed" → the integration isn't installed at all yet.
 *  "needs-setup" → installed, but at least one of its servers still needs
 *    credentials or an OAuth session (McpConnection.setupNeeded).
 *  "connected" → installed and every one of its servers is authenticated. */
export type McpCardStatus = "not-installed" | "needs-setup" | "connected"

export function MarketplaceMcpCard({
  icon: Icon,
  name,
  description,
  category,
  serverType,
  status,
  onInstall,
  onConfigure,
  onManage,
}: {
  icon: LucideIcon
  name: string
  description: string
  category: string
  serverType: string
  status: McpCardStatus
  onInstall: () => void
  onConfigure?: () => void
  onManage?: () => void
}) {
  const tone = CATEGORY_TONES[category] ?? "border-border/60 bg-secondary/60 text-foreground"

  return (
    <div className="group flex h-full flex-col gap-4 rounded-xl border border-border/60 bg-card/40 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-border hover:bg-card/70 hover:shadow-lg hover:shadow-black/20">
      <div className="flex items-start gap-4">
        <span
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border",
            tone,
          )}
        >
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <h3 className="font-heading text-[15px] font-semibold text-foreground">{name}</h3>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{category}</span>
            <span className="rounded-full border border-border/60 bg-secondary/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              {serverType}
            </span>
          </div>
        </div>
      </div>
      <p className="text-[13px] leading-relaxed text-muted-foreground line-clamp-2">{description}</p>
      <div className="flex items-center justify-end">
        {status === "connected" ? (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-[12px] font-medium text-emerald-400">
              <Check className="h-3.5 w-3.5" />
              Connected
            </span>
            {(onManage ?? onConfigure) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onManage ?? onConfigure}
                className="gap-1.5 text-muted-foreground transition-transform duration-150 active:scale-95"
              >
                <Settings className="h-3.5 w-3.5" />
                Manage
              </Button>
            )}
          </div>
        ) : status === "needs-setup" ? (
          onConfigure ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={onConfigure}
              className="gap-1.5 border border-amber-500/25 bg-amber-500/10 text-amber-300 transition-transform duration-150 hover:bg-amber-500/15 hover:text-amber-200 active:scale-95"
            >
              <KeyRound className="h-3.5 w-3.5" />
              Connect
            </Button>
          ) : (
            <InstalledPill />
          )
        ) : (
          <Button
            size="sm"
            variant="secondary"
            onClick={onInstall}
            className="gap-1.5 border border-border/60 transition-transform duration-150 active:scale-95"
          >
            <Plus className="h-3.5 w-3.5" />
            Install
          </Button>
        )}
      </div>
    </div>
  )
}

