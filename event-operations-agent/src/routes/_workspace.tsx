import { createFileRoute, Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import {
  LayoutGrid, Sparkles, Megaphone, Store, ListChecks, ShieldCheck, History, Settings, CalendarDays, MapPin, Users, ChevronsUpDown, Plus, FlaskConical,
} from "lucide-react";
import { forEvent, useAppState, useCurrentEvent, useHydrated } from "@/lib/store";
import { setCurrentEvent } from "@/lib/seed";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";

export const Route = createFileRoute("/_workspace")({
  component: WorkspaceLayout,
});

function WorkspaceLayout() {
  const hydrated = useHydrated();
  const s = useAppState();
  const ev = useCurrentEvent();
  const navigate = useNavigate();
  const path = useRouterState({ select: (r) => r.location.pathname });

  useEffect(() => {
    if (hydrated && !ev) navigate({ to: "/setup" });
  }, [hydrated, ev, navigate]);

  if (!hydrated || !ev) {
    return (
      <div className="flex min-h-screen">
        <div className="w-60 border-r bg-sidebar" />
        <div className="flex-1 space-y-4 p-8">
          <Skeleton className="h-8 w-80" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  const pending = forEvent(s.approvals, ev.id).filter((a) => a.status === "pending").length;
  const openTasks = forEvent(s.tasks, ev.id).filter((t) => t.status !== "done").length;
  const nav = [
    { to: "/", label: "Overview", icon: LayoutGrid },
    { to: "/agent", label: "AI Agent", icon: Sparkles },
    { to: "/outreach", label: "Outreach", icon: Megaphone, count: forEvent(s.contacts, ev.id).length },
    { to: "/vendors", label: "Vendors", icon: Store, count: forEvent(s.vendors, ev.id).length },
    { to: "/logistics", label: "Logistics", icon: ListChecks, count: openTasks },
    { to: "/approvals", label: "Approvals", icon: ShieldCheck, count: pending, hot: pending > 0 },
    { to: "/activity", label: "Activity", icon: History },
    { to: "/settings", label: "Settings", icon: Settings },
  ] as const;

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r bg-sidebar">
        <div className="flex items-center gap-2 px-4 pb-3 pt-4">
          <div className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-semibold">Event Ops Agent</div>
            <div className="text-[11px] text-muted-foreground">{s.workspace}</div>
          </div>
        </div>
        <div className="px-3">
          <DropdownMenu>
            <DropdownMenuTrigger className="flex w-full items-center justify-between rounded-lg border bg-card px-2.5 py-2 text-left text-[13px] hover:bg-sidebar-accent">
              <span className="truncate font-medium">{ev.name}</span>
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-60">
              <DropdownMenuLabel className="text-xs text-muted-foreground">Events in {s.workspace}</DropdownMenuLabel>
              {s.events.map((e) => (
                <DropdownMenuItem key={e.id} onClick={() => setCurrentEvent(e.id)}>
                  <span className="truncate">{e.name}</span>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate({ to: "/setup" })}>
                <Plus className="h-4 w-4" /> New event
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <nav className="mt-4 flex-1 space-y-0.5 px-2">
          {nav.map((n) => {
            const active = n.to === "/" ? path === "/" : path.startsWith(n.to);
            const I = n.icon;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${active ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/60"}`}
              >
                <I className="h-4 w-4" />
                <span className="flex-1">{n.label}</span>
                {"count" in n && n.count > 0 && (
                  <span className={`rounded px-1.5 text-[11px] tabular-nums ${"hot" in n && n.hot ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>{n.count}</span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="m-3 rounded-lg border border-dashed bg-warning-soft/60 p-2.5 text-[11px] leading-snug text-muted-foreground">
          <div className="mb-0.5 flex items-center gap-1 font-medium text-warning">
            <FlaskConical className="h-3 w-3" /> Demo mode
          </div>
          No AI model, search or email is connected. Agent output is deterministic fixture data; sends are simulated.
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center gap-5 border-b bg-background/85 px-8 py-3 backdrop-blur">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{ev.name}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{format(new Date(ev.date + "T12:00:00"), "EEE, MMM d, yyyy")} · {ev.startTime}–{ev.endTime}</span>
              <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{ev.venue || "Venue unknown"}</span>
              <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{ev.attendees} attendees</span>
            </div>
          </div>
          <div className="ml-auto">
            <Button size="sm" asChild>
              <Link to="/agent"><Sparkles className="h-4 w-4" /> Ask Agent</Link>
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-[1200px] px-8 py-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
