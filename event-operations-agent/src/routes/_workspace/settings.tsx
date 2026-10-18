import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader, Panel, Pill } from "@/components/ui-bits";
import { resetAll, setState, useAppState } from "@/lib/store";
import { loadDemo } from "@/lib/seed";
import { toast } from "sonner";

export const Route = createFileRoute("/_workspace/settings")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Settings — Event Operations Agent" },
      { name: "description", content: "Workspace, members, integrations and demo data." },
      { property: "og:title", content: "Settings — Event Operations Agent" },
      { property: "og:description", content: "Workspace, members, integrations and demo data." },
    ],
  }),
  component: Settings,
});

function Settings() {
  const s = useAppState();
  const nav = useNavigate();
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid max-w-3xl gap-5">
        <Panel title="Workspace">
          <Input value={s.workspace} onChange={(e) => setState((st) => ({ ...st, workspace: e.target.value }))} />
          <div className="mt-3 flex flex-wrap gap-1">{s.members.map((m) => <Pill key={m}>{m}</Pill>)}</div>
        </Panel>
        <Panel title="Integrations">
          <ul className="space-y-2 text-[13px]">
            {[["AI model", "Not connected — agent runs deterministic demo workflows"], ["Web search", "Not connected — suppliers and contacts are labeled fixtures"], ["Email", "Not connected — approved sends are simulated"], ["Payments", "Disabled by policy"]].map(([k, v]) => (
              <li key={k} className="flex items-center justify-between"><span>{k}</span><span className="text-xs text-muted-foreground">{v}</span></li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-muted-foreground">Data is saved in this browser and survives refreshes.</p>
        </Panel>
        <Panel title="Demo data">
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { loadDemo(); toast.success("Demo workshop added"); nav({ to: "/" }); }}>Add demo workshop</Button>
            <Button variant="destructive" onClick={() => { if (confirm("Delete all events and records in this browser?")) { resetAll(); nav({ to: "/setup" }); } }}>Reset everything</Button>
          </div>
        </Panel>
      </div>
    </>
  );
}
