import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ListChecks, Sparkles, Plus, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Empty, OriginPill, PageHeader, Panel, Pill, StatusPill } from "@/components/ui-bits";
import { createApproval, forEvent, insert, log, uid, update, useAppState, useCurrentEvent } from "@/lib/store";
import type { ScheduleItem, Task, TaskStatus } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

export const Route = createFileRoute("/_workspace/logistics")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Logistics — Event Operations Agent" },
      { name: "description", content: "Tasks, dependencies, run-of-show and venue requirements." },
      { property: "og:title", content: "Logistics — Event Operations Agent" },
      { property: "og:description", content: "Tasks, dependencies, run-of-show and venue requirements." },
    ],
  }),
  component: Logistics,
});

function Logistics() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const [filter, setFilter] = useState<"all" | TaskStatus>("all");
  const all = forEvent(s.tasks, ev.id);
  const tasks = all.filter((t) => filter === "all" || t.status === filter).sort((a, b) => a.due.localeCompare(b.due));
  const schedule = forEvent(s.schedule, ev.id).sort((a, b) => a.start.localeCompare(b.start));
  const changes = forEvent(s.activity, ev.id).filter((a) => /task|schedule|plan|attendance/i.test(a.summary)).slice(0, 5);
  const [newTask, setNewTask] = useState("");

  const isBlocked = (t: Task) => t.dependsOn.some((d) => all.find((x) => x.id === d)?.status !== "done");

  return (
    <>
      <PageHeader
        title="Logistics"
        description="Operational plan built from saved requirements, suppliers and outreach. Confirmed times can only change through an approval."
        actions={<Button size="sm" asChild><Link to="/agent" search={{ q: "Build our setup plan." }}><Sparkles className="h-4 w-4" />Build plan</Link></Button>}
      />
      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 space-y-3">
          <div className="flex gap-1">
            {(["all", "todo", "in_progress", "blocked", "done"] as const).map((f) => (
              <Button key={f} size="sm" variant={filter === f ? "secondary" : "ghost"} className="h-7 text-xs" onClick={() => setFilter(f)}>
                {f.replace("_", " ")} <span className="ml-1 text-muted-foreground">{f === "all" ? all.length : all.filter((t) => t.status === f).length}</span>
              </Button>
            ))}
          </div>
          {all.length === 0 ? <Empty icon={ListChecks} title="No tasks yet" body="Ask the agent to build the setup plan from your requirements and suppliers." /> : (
            <div className="overflow-hidden rounded-xl border bg-card">
              <table className="w-full text-[13px]">
                <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground"><tr>{["Task", "Phase", "Owner", "Due", "Depends on", "Status"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
                <tbody>{tasks.map((t) => (
                  <tr key={t.id} className="border-b last:border-0">
                    <td className="px-3 py-2"><div className="font-medium">{t.title}</div><div className="flex items-center gap-1 text-[11px] text-muted-foreground">{t.related} <OriginPill origin={t.origin} /></div></td>
                    <td className="px-3"><Pill>{t.phase}</Pill></td>
                    <td className="px-3">
                      <Select value={t.owner ?? "__none"} onValueChange={(v) => update("tasks", t.id, { owner: v === "__none" ? null : v })}>
                        <SelectTrigger className="h-7 w-32 text-xs"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="__none">Unassigned</SelectItem>{s.members.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                      </Select>
                    </td>
                    <td className="px-3 font-mono text-xs">{t.due}</td>
                    <td className="px-3 text-xs">{t.dependsOn.length === 0 ? "—" : t.dependsOn.map((d) => all.find((x) => x.id === d)?.title).filter(Boolean).map((n) => <div key={n} className="truncate text-muted-foreground">↳ {n}</div>)}{isBlocked(t) && t.status !== "done" && <Pill tone="red">waiting on deps</Pill>}</td>
                    <td className="px-3">
                      <Select value={t.status} onValueChange={(v) => { update("tasks", t.id, { status: v as TaskStatus }); log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Task "${t.title}" → ${v.replace("_", " ")}`, origin: "organizer" }); }}>
                        <SelectTrigger className="h-7 w-28 text-xs"><SelectValue /></SelectTrigger>
                        <SelectContent>{["todo", "in_progress", "blocked", "done"].map((x) => <SelectItem key={x} value={x}>{x.replace("_", " ")}</SelectItem>)}</SelectContent>
                      </Select>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          <div className="flex gap-2">
            <Input placeholder="Add a task…" value={newTask} onChange={(e) => setNewTask(e.target.value)} />
            <Button variant="outline" disabled={!newTask.trim()} onClick={() => { insert("tasks", [{ id: uid("tsk"), eventId: ev.id, title: newTask, phase: "prep", status: "todo", owner: null, due: ev.date, dependsOn: [], related: "Added manually", origin: "organizer" }]); log({ eventId: ev.id, actor: "organizer", kind: "created", summary: `Added task "${newTask}"`, origin: "organizer" }); setNewTask(""); }}><Plus className="h-4 w-4" />Add</Button>
          </div>
        </div>
        <div className="space-y-5">
          <Panel title="Run of show">
            {schedule.length === 0 ? <p className="text-xs text-muted-foreground">No schedule items.</p> : <ol className="space-y-1">{schedule.map((x) => <ScheduleRow key={x.id} x={x} />)}</ol>}
          </Panel>
          <Panel title="Venue & participant info">
            <dl className="space-y-2 text-xs">
              <div><dt className="text-muted-foreground">Venue</dt><dd>{ev.venue || "Unknown"} · {ev.location || "address unknown"}</dd></div>
              <div><dt className="text-muted-foreground">Constraints</dt><dd>{ev.constraints || "None recorded"}</dd></div>
              <div><dt className="text-muted-foreground">Participant instructions</dt><dd>Arrive by {ev.startTime}; check in at the entrance. Bring a laptop. <span className="text-muted-foreground">(draft — sending requires approval)</span></dd></div>
            </dl>
          </Panel>
          <Panel title="Recent changes">
            {changes.length === 0 ? <p className="text-xs text-muted-foreground">No changes yet.</p> : <ul className="space-y-2">{changes.map((c) => <li key={c.id} className="text-xs">{c.summary}<div className="text-[11px] text-muted-foreground">{formatDistanceToNow(new Date(c.at))} ago</div></li>)}</ul>}
          </Panel>
        </div>
      </div>
    </>
  );
}

function ScheduleRow({ x }: { x: ScheduleItem }) {
  const ev = useCurrentEvent()!;
  const [edit, setEdit] = useState(false);
  const [start, setStart] = useState(x.start);
  const [end, setEnd] = useState(x.end);
  const save = () => {
    if (x.confirmed) {
      createApproval({
        eventId: ev.id, kind: "schedule_change", title: `Change confirmed time: ${x.title}`, target: x.title,
        payload: `${x.title}\nFrom: ${x.start}–${x.end}\nTo: ${start}–${end}`, cost: null, evidence: `Currently confirmed: ${x.notes || "yes"}`,
        reason: "Organizer requested a change to a confirmed time.", refId: x.id, meta: { scheduleId: x.id, start, end },
      });
      toast.info("Confirmed time — change sent to Approvals instead of applied.");
    } else {
      update("schedule", x.id, { start, end });
      log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Proposed time for "${x.title}" → ${start}–${end}`, origin: "organizer" });
    }
    setEdit(false);
  };
  return (
    <li className="group rounded-md px-1 py-1.5 text-[13px] hover:bg-muted/50">
      {edit ? (
        <div className="flex items-center gap-1"><Input type="time" className="h-7 text-xs" value={start} onChange={(e) => setStart(e.target.value)} /><Input type="time" className="h-7 text-xs" value={end} onChange={(e) => setEnd(e.target.value)} /><Button size="sm" className="h-7" onClick={save}>Save</Button></div>
      ) : (
        <button className="flex w-full items-center gap-2 text-left" onClick={() => setEdit(true)}>
          <span className="w-20 shrink-0 font-mono text-[11px] text-muted-foreground">{x.start}–{x.end}</span>
          <span className="flex-1">{x.title}</span>
          {x.confirmed ? <Pill tone="green"><Lock className="h-3 w-3" />confirmed</Pill> : <StatusPill status="proposed" />}
        </button>
      )}
    </li>
  );
}
