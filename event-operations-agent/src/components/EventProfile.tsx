import { useState } from "react";
import { Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/components/ui-bits";
import { log, money, update, useCurrentEvent } from "@/lib/store";
import type { EventRecord } from "@/lib/types";
import { toast } from "sonner";

const FIELDS: { k: keyof EventRecord; label: string; long?: boolean }[] = [
  { k: "name", label: "Name" }, { k: "type", label: "Type" }, { k: "date", label: "Date" }, { k: "startTime", label: "Start" }, { k: "endTime", label: "End" },
  { k: "venue", label: "Venue" }, { k: "location", label: "Location" }, { k: "attendees", label: "Attendees" }, { k: "budget", label: "Budget" },
  { k: "goals", label: "Goals", long: true }, { k: "existing", label: "Existing arrangements", long: true }, { k: "constraints", label: "Constraints", long: true },
];

export function EventProfile() {
  const ev = useCurrentEvent()!;
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState<EventRecord>(ev);

  const save = () => {
    const n = Number(f.attendees);
    if (!f.name.trim() || !Number.isInteger(n) || n < 1) return toast.error("Name and a whole-number attendee count are required.");
    const changed = FIELDS.filter((x) => String(f[x.k]) !== String(ev[x.k])).map((x) => x.label);
    update("events", ev.id, { ...f, attendees: n, budget: Number(f.budget) || 0 });
    if (changed.length) log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Edited event profile: ${changed.join(", ")}`, origin: "organizer" });
    if (changed.includes("Attendees")) toast.info("Attendance changed. Ask the agent what changes so it can flag affected tasks and suppliers.");
    setEdit(false);
  };

  return (
    <Panel
      title="Event profile"
      action={edit ? (
        <div className="flex gap-2"><Button size="sm" variant="ghost" onClick={() => setEdit(false)}>Cancel</Button><Button size="sm" onClick={save}>Save</Button></div>
      ) : (
        <Button size="sm" variant="ghost" onClick={() => { setF(ev); setEdit(true); }}><Pencil className="h-3.5 w-3.5" />Edit</Button>
      )}
    >
      <dl className="grid grid-cols-3 gap-x-6 gap-y-3">
        {FIELDS.map((x) => (
          <div key={x.k} className={x.long ? "col-span-3" : ""}>
            <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{x.label}</dt>
            <dd className="mt-0.5 text-[13px]">
              {edit ? (
                x.long ? <Textarea value={String(f[x.k] ?? "")} onChange={(e) => setF({ ...f, [x.k]: e.target.value })} /> : <Input className="h-8" value={String(f[x.k] ?? "")} onChange={(e) => setF({ ...f, [x.k]: e.target.value })} />
              ) : x.k === "budget" ? money(ev.budget, ev.currency) : String(ev[x.k] || "") || <span className="text-muted-foreground">Not provided</span>}
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
