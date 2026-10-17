"use client"

import { useMemo, useState, useEffect } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Blocks,
  Home,
  Plug,
  Plus,
  RefreshCw,
  SearchX,
  Sparkles,
  Store,
  WifiOff,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  MarketplaceMcpCard,
  MarketplaceSkillCard,
  SearchBar,
  SegmentedTabs,
  Tag,
  type McpCardStatus,
} from "@/components/management/shared"
import { McpConnectionDialog } from "@/components/pages/mcp/mcp-dialogs"
import { SkillActivateDialog } from "./skill-activate-dialog"
import { SKILL_TEMPLATES } from "@/components/pages/skills/skill-data"
import type { LibraryServer } from "@/components/pages/mcp/mcp-types"
import type { SkillPermissionFlags, SkillTemplate } from "@/components/pages/skills/skill-types"
import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"
import { useNavigation } from "@/lib/navigation"
import { useSkills } from "@/lib/skills-store"
import { useMcp } from "@/lib/mcp-store"
import { searchRegistry } from "@/lib/mcp-api"

/* ------------------------------------------------------------------ */
/*  Shared section scaffolding                                         */
/* ------------------------------------------------------------------ */

function DashboardHeader({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Marketplace</p>
        <h1 className="mt-1 font-heading text-[26px] font-semibold leading-tight tracking-tight text-foreground">
          {title}
        </h1>
        <p className="mt-2 max-w-xl text-[13px] leading-relaxed text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  )
}

function NoResults() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-card/30 px-6 py-16 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/60 bg-secondary/60">
        <SearchX className="h-5 w-5 text-muted-foreground" />
      </span>
      <p className="mt-4 text-sm font-medium text-foreground">No matches</p>
      <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
        Try a different search term or category.
      </p>
    </div>
  )
}

/* Small horizontal chip list showing what is already installed. */
function InstalledRow({
  title,
  items,
}: {
  title: string
  items: { icon: LucideIcon; name: string }[]
}) {
  if (items.length === 0) return null
  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</span>
      {items.map((item) => {
        const Icon = item.icon
        return (
          <Tag key={item.name} className="gap-1.5 py-1">
            <Icon className="h-3 w-3" />
            {item.name}
          </Tag>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Welcome section                                                    */
/* ------------------------------------------------------------------ */

function WelcomeSection({
  skillCount,
  mcpCount,
  installedSkills,
  installedServers,
  onBrowse,
}: {
  skillCount: number
  mcpCount: number
  installedSkills: number
  installedServers: number
  onBrowse: (section: "skills" | "mcp") => void
}) {
  return (
    <div className="relative mx-auto w-full max-w-4xl">
      <div className="pointer-events-none absolute inset-x-0 -top-12 h-72 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.06),transparent_65%)]" />
      <div className="mt-6 flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
        <span className="flex h-5 w-5 items-center justify-center rounded-md border border-border/60 bg-secondary/60">
          <Sparkles className="h-3 w-3 text-foreground" />
        </span>
        Marketplace
      </div>
      <h1 className="mt-4 font-heading text-4xl font-semibold leading-[1.1] tracking-tight text-foreground sm:text-5xl">
        Extend what your agent can do.
      </h1>
      <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
        Discover and install Skills and MCP servers that give the agent new capabilities. Everything you install
        shows up in your workspace and can be configured from there.
      </p>

      {/* Feature cards */}
      <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <button
          onClick={() => onBrowse("skills")}
          className="group flex flex-col gap-4 rounded-2xl border border-border/60 bg-card/40 p-6 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-border hover:bg-card/70 hover:shadow-lg hover:shadow-black/20"
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
            <Blocks className="h-6 w-6" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-lg font-semibold text-foreground">Skills</h2>
              <span className="rounded-full border border-border/60 bg-secondary/40 px-2 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
                {skillCount}
              </span>
            </div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
              Reusable, one-shot capabilities the agent can invoke — code review, research, summarization, and more.
            </p>
          </div>
          <span className="mt-auto inline-flex items-center gap-1.5 text-[13px] font-medium text-foreground transition-transform duration-200 group-hover:translate-x-0.5">
            Browse skills
            <ArrowRight className="h-4 w-4" />
          </span>
        </button>

        <button
          onClick={() => onBrowse("mcp")}
          className="group flex flex-col gap-4 rounded-2xl border border-border/60 bg-card/40 p-6 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-border hover:bg-card/70 hover:shadow-lg hover:shadow-black/20"
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-sky-500/20 bg-sky-500/10 text-sky-400">
            <Plug className="h-6 w-6" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-lg font-semibold text-foreground">MCP servers</h2>
              <span className="rounded-full border border-border/60 bg-secondary/40 px-2 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
                {mcpCount}
              </span>
            </div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
              Connect live external services — Slack, Notion, Sentry, databases — and expose their tools to the agent.
            </p>
          </div>
          <span className="mt-auto inline-flex items-center gap-1.5 text-[13px] font-medium text-foreground transition-transform duration-200 group-hover:translate-x-0.5">
            Browse servers
            <ArrowRight className="h-4 w-4" />
          </span>
        </button>
      </div>

      {/* Quick stats */}
      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Skills available", value: skillCount },
          { label: "MCP servers", value: mcpCount },
          { label: "Installed skills", value: installedSkills },
          { label: "Installed servers", value: installedServers },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-border/60 bg-card/40 px-4 py-4">
            <p className="font-heading text-2xl font-semibold tabular-nums text-foreground">{stat.value}</p>
            <p className="mt-1 text-[12px] text-muted-foreground">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Skills section                                                     */
/* ------------------------------------------------------------------ */

function SkillsSection({
  query,
  onQueryChange,
  category,
  onCategoryChange,
  installedNames,
  onInstall,
  loading,
}: {
  query: string
  onQueryChange: (v: string) => void
  category: string
  onCategoryChange: (v: string) => void
  installedNames: Set<string>
  onInstall: (id: string) => void
  loading: boolean
}) {
  const categories = useMemo(
    () => ["All", ...Array.from(new Set(SKILL_TEMPLATES.map((t) => t.category)))],
    [],
  )
  const counts = useMemo(() => {
    const map: Record<string, number> = { All: SKILL_TEMPLATES.length }
    for (const t of SKILL_TEMPLATES) map[t.category] = (map[t.category] ?? 0) + 1
    return map
  }, [])

  const q = query.trim().toLowerCase()
  const filtered = useMemo(
    () =>
      SKILL_TEMPLATES.filter((t) => {
        const matchesCategory = category === "All" || t.category === category
        const matchesQuery = !q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
        return matchesCategory && matchesQuery
      }),
    [q, category],
  )

  const installedItems = useMemo(
    () => SKILL_TEMPLATES.filter((t) => installedNames.has(t.name.toLowerCase())),
    [installedNames],
  )

  return (
    <>
      <DashboardHeader
        title="Skills Marketplace"
        description="Reusable capabilities your agent can invoke on demand. Install a skill and it appears on your Skills page, ready to configure."
      />

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="w-full max-w-sm">
          <SearchBar value={query} onChange={onQueryChange} placeholder="Search skills..." />
        </div>
        <SegmentedTabs
          tabs={categories.map((c) => ({ id: c, label: c, count: counts[c] }))}
          value={category}
          onChange={onCategoryChange}
        />
      </div>

      <InstalledRow
        title="Installed"
        items={installedItems.map((t) => ({ icon: t.icon, name: t.name }))}
      />

      {loading ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[184px] animate-pulse rounded-xl border border-border/60 bg-card/30" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <NoResults />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {filtered.map((tpl, i) => (
            <div key={tpl.id} className="h-full dream-in" style={{ animationDelay: `${Math.min(i, 7) * 40}ms` }}>
              <MarketplaceSkillCard
                icon={tpl.icon}
                name={tpl.name}
                description={tpl.description}
                category={tpl.category}
                triggerType={tpl.triggerType}
                installed={installedNames.has(tpl.name.toLowerCase())}
                onInstall={() => onInstall(tpl.id)}
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  MCP servers section                                                */
/* ------------------------------------------------------------------ */

function McpSection({
  catalog,
  query,
  onQueryChange,
  category,
  onCategoryChange,
  statusByName,
  onInstall,
  onManage,
  onAddCustom,
  loading,
  error,
  onRetry,
}: {
  catalog: LibraryServer[]
  query: string
  onQueryChange: (v: string) => void
  category: string
  onCategoryChange: (v: string) => void
  /** Real state from the backend/plugin config for every installed
   *  integration — never a frontend guess. See McpCardStatus. */
  statusByName: Map<string, McpCardStatus>
  onInstall: (id: string) => void
  onManage: (id: string) => void
  onAddCustom: () => void
  loading: boolean
  /** True when the last catalog refetch failed — `catalog` still holds
   *  whatever was last loaded successfully, never wiped to empty. */
  error?: boolean
  onRetry?: () => void
}) {
  const installedNames = useMemo(
    () => new Set(Array.from(statusByName.entries()).filter(([, s]) => s !== "not-installed").map(([n]) => n)),
    [statusByName],
  )
  const categories = useMemo(
    () => ["All", ...Array.from(new Set(catalog.map((l) => l.category))), "Registry"],
    [catalog],
  )
  const counts = useMemo(() => {
    const map: Record<string, number> = { All: catalog.length, Registry: 0 }
    for (const l of catalog) map[l.category] = (map[l.category] ?? 0) + 1
    return map
  }, [catalog])

  const [registryResults, setRegistryResults] = useState<any[]>([])
  const [searchingRegistry, setSearchingRegistry] = useState(false)

  useEffect(() => {
    if (category === "Registry") {
      if (!query.trim()) {
        setRegistryResults([])
        return
      }
      setSearchingRegistry(true)
      const timeout = setTimeout(() => {
        searchRegistry(query)
          .then((data) => {
            setRegistryResults(data.servers || [])
          })
          .catch(console.error)
          .finally(() => setSearchingRegistry(false))
      }, 500)
      return () => clearTimeout(timeout)
    }
  }, [category, query])

  const q = query.trim().toLowerCase()
  const filtered = useMemo(
    () =>
      catalog.filter((l) => {
        const matchesCategory = category === "All" || l.category === category
        const matchesQuery = !q || l.name.toLowerCase().includes(q) || l.description.toLowerCase().includes(q)
        return matchesCategory && matchesQuery
      }),
    [q, category, catalog],
  )

  const installedItems = useMemo(
    () => catalog.filter((l) => installedNames.has(l.name.toLowerCase())),
    [installedNames, catalog],
  )

  return (
    <>
      <DashboardHeader
        title="MCP Server Marketplace"
        description="Connect live services so your agent can reach external tools and data. Installed servers appear on your MCP page for configuration."
        action={
          <Button variant="secondary" onClick={onAddCustom} className="gap-2">
            <Plus className="h-4 w-4" />
            Add custom server
          </Button>
        }
      />

      {error && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3">
          <div className="flex items-center gap-2 text-[13px] text-red-300">
            <WifiOff className="h-4 w-4 shrink-0" />
            Couldn&apos;t refresh the marketplace catalog — showing the last loaded list.
          </div>
          {onRetry && (
            <Button variant="secondary" size="sm" onClick={onRetry} className="shrink-0 gap-2">
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </Button>
          )}
        </div>
      )}

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="w-full max-w-sm">
          <SearchBar value={query} onChange={onQueryChange} placeholder="Search MCP servers..." />
        </div>
        <SegmentedTabs
          tabs={categories.map((c) => ({ id: c, label: c, count: counts[c] }))}
          value={category}
          onChange={onCategoryChange}
        />
      </div>

      <InstalledRow
        title="Installed"
        items={installedItems.map((l) => ({ icon: l.icon, name: l.name }))}
      />

      {loading || searchingRegistry ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[184px] animate-pulse rounded-xl border border-border/60 bg-card/30" />
          ))}
        </div>
      ) : category === "Registry" ? (
        registryResults.length === 0 ? (
          query.trim() ? <NoResults /> : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-card/30 px-6 py-16 text-center">
              <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/60 bg-secondary/60">
                <Store className="h-5 w-5 text-muted-foreground" />
              </span>
              <p className="mt-4 text-sm font-medium text-foreground">Search Official MCP Registry</p>
              <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
                Type above to discover servers from registry.modelcontextprotocol.io
              </p>
            </div>
          )
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {registryResults.map((item, i) => (
              <div key={item.server.name} className="h-full dream-in" style={{ animationDelay: `${Math.min(i, 7) * 40}ms` }}>
                <MarketplaceMcpCard
                  icon={Plug}
                  name={item.server.title || item.server.name}
                  description={item.server.description || "No description provided."}
                  category="Registry"
                  serverType="stdio"
                  status={statusByName.get(item.server.name.toLowerCase()) ?? "not-installed"}
                  onInstall={() => onAddCustom()}
                  onConfigure={() => onAddCustom()}
                />
              </div>
            ))}
          </div>
        )
      ) : filtered.length === 0 ? (
        <NoResults />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {filtered.map((lib, i) => (
            <div key={lib.id} className="h-full dream-in" style={{ animationDelay: `${Math.min(i, 7) * 40}ms` }}>
              <MarketplaceMcpCard
                icon={lib.icon}
                name={lib.name}
                description={lib.description}
                category={lib.category}
                serverType={lib.serverType}
                status={statusByName.get(lib.name.toLowerCase()) ?? "not-installed"}
                onInstall={() => onInstall(lib.id)}
                onConfigure={() => onInstall(lib.id)}
                onManage={() => onManage(lib.id)}
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  Dashboard shell                                                    */
/* ------------------------------------------------------------------ */

const SIDEBAR_NAV = [
  { key: "home", label: "Welcome", icon: Home },
  { key: "skills", label: "Skills", icon: Blocks },
  { key: "mcp", label: "MCP Servers", icon: Plug },
] as const

export function MarketplaceDashboard() {
  const { marketplaceSection, setMarketplaceSection, marketplaceOrigin, setView } = useNavigation()
  const { skills, installTemplate } = useSkills()
  const { connections, catalog, catalogLoading, catalogError, loadCatalog, upsertConnection, installAndProvision } = useMcp()

  const [skillQuery, setSkillQuery] = useState("")
  const [skillCategory, setSkillCategory] = useState("All")
  const [mcpQuery, setMcpQuery] = useState("")
  const [mcpCategory, setMcpCategory] = useState("All")
  const [customOpen, setCustomOpen] = useState(false)
  const [activateTarget, setActivateTarget] = useState<SkillTemplate | null>(null)

  const installedSkillNames = useMemo(() => new Set(skills.map((s) => s.name.toLowerCase())), [skills])
  // Real state from the backend/plugin config for every MCP integration —
  // never a frontend guess, and never stuck showing "Configure" (or worse,
  // "Install") for something that's actually already connected:
  //   not-installed  -- absent from both the plugin-installed catalog flag
  //                      and settings.mcp_config
  //   needs-setup    -- installed, but at least one of its provisioned
  //                      servers still needs credentials/OAuth
  //                      (McpConnection.setupNeeded)
  //   connected      -- installed and every provisioned server is
  //                      authenticated
  const mcpStatusByName = useMemo(() => {
    const map = new Map<string, McpCardStatus>()
    for (const lib of catalog) {
      const name = lib.name.toLowerCase()
      const serverNames = lib.servers ? Object.keys(lib.servers) : [lib.name]
      const provisioned = connections.filter((c) => serverNames.includes(c.id))
      if (provisioned.length > 0) {
        map.set(name, provisioned.some((c) => c.setupNeeded) ? "needs-setup" : "connected")
      } else if (lib.installed) {
        // Plugin installed but no servers provisioned yet (e.g. a
        // plugin-only install with nothing in settings.mcp_config yet).
        map.set(name, "needs-setup")
      } else {
        map.set(name, "not-installed")
      }
    }
    // A server can exist in settings.mcp_config without (or ahead of) its
    // catalog entry loading -- still needs a real status, not the implicit
    // "not-installed" a missing map entry would fall back to.
    for (const conn of connections) {
      const name = conn.name.toLowerCase()
      if (!map.has(name)) map.set(name, conn.setupNeeded ? "needs-setup" : "connected")
    }
    return map
  }, [catalog, connections])

  const installSkill = (id: string) => {
    const tpl = SKILL_TEMPLATES.find((t) => t.id === id)
    if (tpl) setActivateTarget(tpl)
  }
  const handleActivate = (tpl: SkillTemplate, flags: SkillPermissionFlags) => {
    installTemplate(tpl, { flags })
  }
  // Marketplace Install = add-only. It installs the plugin and provisions the
  // .mcp.json servers with ${VAR} placeholders intact (no credentials are
  // collected here), then lands on the MCP page where the Setup dialog drives
  // authentication. installAndProvision(lib, { values: {} }) is a no-op
  // reinstall when the integration is already installed, so "Configure" and
  // "Install" both end up in the same place.
  const installMcp = async (id: string) => {
    const lib = catalog.find((l) => l.id === id)
    if (!lib) return
    await installAndProvision(lib, { values: {} })
    setView("mcp")
  }
  // Already connected -- just go manage it, no need to touch settings.
  const manageMcp = () => setView("mcp")

  return (
    <div className="dream-in flex h-screen w-full overflow-hidden bg-background">
      {/* Marketplace sidebar */}
      <aside className="flex w-[236px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
        <div className="flex items-center gap-2.5 px-4 pb-3 pt-5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/15 bg-white/[0.06] shadow-lg shadow-black/40">
            <Store className="h-[18px] w-[18px] text-neutral-200" />
          </span>
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-semibold leading-tight text-sidebar-foreground">Marketplace</span>
            <span className="truncate text-[11px] leading-tight text-muted-foreground">Skill & MCP directory</span>
          </div>
        </div>

        <button
          onClick={() => setView(marketplaceOrigin)}
          className="mx-3 mb-4 flex items-center gap-2 rounded-lg border border-sidebar-border bg-sidebar-accent/40 px-3 py-2 text-[13px] font-medium text-sidebar-foreground transition-colors duration-200 hover:bg-sidebar-accent"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to app
        </button>

        <div className="flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            Explore
          </p>
          <nav className="space-y-0.5">
            {SIDEBAR_NAV.map(({ key, label, icon: Icon }) => {
              const active = marketplaceSection === key
              const count = key === "skills" ? SKILL_TEMPLATES.length : key === "mcp" ? catalog.length : undefined
              return (
                <button
                  key={key}
                  onClick={() => setMarketplaceSection(key)}
                  className={cn(
                    "group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors duration-200 hover:bg-sidebar-accent",
                    active && "bg-sidebar-accent",
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                  )}
                  <Icon
                    className={cn(
                      "h-[18px] w-[18px] text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground",
                      active && "text-sidebar-foreground",
                    )}
                  />
                  {label}
                  {count !== undefined && (
                    <span
                      className={cn(
                        "ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground",
                        active ? "bg-background/60" : "bg-sidebar-accent/60",
                      )}
                    >
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>

        <div className="border-t border-sidebar-border px-4 py-3">
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {skills.length} skills · {connections.length} servers installed
          </p>
        </div>
      </aside>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <ScrollArea className="h-full">
          <div className="mx-auto w-full max-w-[1400px] px-6 py-10 sm:px-10">
            <div key={marketplaceSection} className="dream-in">
              {marketplaceSection === "home" && (
                <WelcomeSection
                  skillCount={SKILL_TEMPLATES.length}
                  mcpCount={catalog.length}
                  installedSkills={skills.length}
                  installedServers={connections.length}
                  onBrowse={setMarketplaceSection}
                />
              )}
              {marketplaceSection === "skills" && (
                <SkillsSection
                  query={skillQuery}
                  onQueryChange={setSkillQuery}
                  category={skillCategory}
                  onCategoryChange={setSkillCategory}
                  installedNames={installedSkillNames}
                  onInstall={installSkill}
                  loading={false}
                />
              )}
              {marketplaceSection === "mcp" && (
                <McpSection
                  catalog={catalog}
                  query={mcpQuery}
                  onQueryChange={setMcpQuery}
                  category={mcpCategory}
                  onCategoryChange={setMcpCategory}
                  statusByName={mcpStatusByName}
                  onInstall={installMcp}
                  onManage={manageMcp}
                  onAddCustom={() => setCustomOpen(true)}
                  loading={catalogLoading}
                  error={catalogError}
                  onRetry={() => void loadCatalog()}
                />
              )}
            </div>
          </div>
        </ScrollArea>
      </div>

      <SkillActivateDialog
        template={activateTarget}
        onOpenChange={(open) => {
          if (!open) setActivateTarget(null)
        }}
        onActivate={handleActivate}
      />
      <McpConnectionDialog
        open={customOpen}
        connection={null}
        onOpenChange={setCustomOpen}
        onSave={upsertConnection}
      />
    </div>
  )
}
