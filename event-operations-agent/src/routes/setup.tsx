import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Sparkles, ArrowRight, FlaskConical, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createEvent, loadDemo } from "@/lib/seed";
import { useAppState } from "@/lib/store";
import { toast } from "sonner";

export const Route = createFileRoute("/setup")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Create an event — Event Operations Agent" },
      { name: "description", content: "Describe your event and let the agent find what's missing." },
      { property: "og:title", content: "Create an event — Event Operations Agent" },
      { property: "og:description", content: "Describe your event and let the agent find what's missing." },
    ],
  }),
  component: Setup,
});

const blank = {
  name: "", type: "Technology workshop", date: "2026-11-14", startTime: "13:00", endTime: "17:30", venue: "", location: "",
  attendees: "80", budget: "3500", currency: "USD", goals: "", existing: "", constraints: "",
};

function Setup() {
  const nav = useNavigate();
  const s = useAppState();
  const [f, setF] = useState(blank);
  const [step, setStep] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof blank) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  const next = () => {
    if (step === 0) {
      if (!f.name.trim()) return setErr("Event name is required.");
      if (!f.date) return setErr("Event date is required.");
      const n = Number(f.attendees);
      if (!Number.isInteger(n) || n < 1 || n > 100000) return setErr("Attendee count must be a whole number.");
    }
    setErr(null);
    if (step < 1) return setStep(step + 1);
    createEvent({
      name: f.name.trim(), type: f.type, date: f.date, startTime: f.startTime, endTime: f.endTime, venue: f.venue.trim(), location: f.location.trim(),
      attendees: Number(f.attendees), budget: Number(f.budget) || 0, currency: f.currency || "USD", goals: f.goals, existing: f.existing, constraints: f.constraints,
    });
    toast.success("Event created");
    nav({ to: "/agent", search: { q: "What are we missing for this event?" } });
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-xl px-6 py-14">
        {s.events.length > 0 && (
          <Link to="/" className="mb-6 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Back to workspace</Link>
        )}
        <div className="mb-8 flex items-center gap-2">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground"><Sparkles className="h-4 w-4" /></div>
          <span className="font-semibold">Event Operations Agent</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{step === 0 ? "Tell the agent about your event" : "Goals and constraints"}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Step {step + 1} of 2 · The agent uses this to find what's missing.</p>

        <div className="mt-8 space-y-4 rounded-xl border bg-card p-6 shadow-[var(--shadow-card)]">
          {step === 0 ? (
            <>
              <F label="Event name"><Input value={f.name} onChange={set("name")} placeholder="Build with AI: Applied LLM Workshop" /></F>
              <F label="Event type"><Input value={f.type} onChange={set("type")} /></F>
              <div className="grid grid-cols-3 gap-3">
                <F label="Date"><Input type="date" value={f.date} onChange={set("date")} /></F>
                <F label="Start"><Input type="time" value={f.startTime} onChange={set("startTime")} /></F>
                <F label="End"><Input type="time" value={f.endTime} onChange={set("endTime")} /></F>
              </div>
              <F label="Venue"><Input value={f.venue} onChange={set("venue")} placeholder="Paul G. Allen Center, Room G10" /></F>
              <F label="Address / location"><Input value={f.location} onChange={set("location")} placeholder="185 E Stevens Way NE, Seattle, WA" /></F>
              <div className="grid grid-cols-3 gap-3">
                <F label="Attendees"><Input inputMode="numeric" value={f.attendees} onChange={set("attendees")} /></F>
                <F label="Budget"><Input inputMode="decimal" value={f.budget} onChange={set("budget")} /></F>
                <F label="Currency"><Input value={f.currency} onChange={set("currency")} maxLength={3} /></F>
              </div>
            </>
          ) : (
            <>
              <F label="Event goals"><Textarea value={f.goals} onChange={set("goals")} placeholder="Teach 80 students to build an LLM app; secure one sponsor." /></F>
              <F label="Existing speakers, sponsors and vendors"><Textarea value={f.existing} onChange={set("existing")} placeholder="Venue booked. No speaker confirmed yet." /></F>
              <F label="Known requirements and constraints"><Textarea value={f.constraints} onChange={set("constraints")} placeholder="Room access from 11:30. No cooking on site." /></F>
            </>
          )}
          {err && <p className="text-sm text-destructive">{err}</p>}
          <div className="flex justify-between pt-2">
            <Button variant="ghost" disabled={step === 0} onClick={() => setStep(0)}>Back</Button>
            <Button onClick={next}>{step === 1 ? "Create event" : "Continue"} <ArrowRight className="h-4 w-4" /></Button>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between rounded-xl border border-dashed p-4">
          <div className="text-sm">
            <div className="flex items-center gap-1.5 font-medium"><FlaskConical className="h-4 w-4 text-warning" />Use the demo workshop</div>
            <p className="text-xs text-muted-foreground">80-person workshop with a fictional sponsor, caterer and schedule.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => { loadDemo(); nav({ to: "/" }); }}>Load demo</Button>
        </div>
      </div>
    </div>
  );
}

function F({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}
