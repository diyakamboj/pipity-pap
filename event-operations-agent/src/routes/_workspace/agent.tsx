import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, Check, Loader2, Sparkles, User, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Pill } from "@/components/ui-bits";
import { ResultCard } from "@/components/ResultCards";
import { runAgent, STARTERS, type Card } from "@/lib/agent";
import { useCurrentEvent } from "@/lib/store";

export const Route = createFileRoute("/_workspace/agent")({
  validateSearch: (s: Record<string, unknown>): { q?: string } => ({ q: typeof s.q === "string" ? s.q : undefined }),
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "AI Agent — Event Operations Agent" },
      { name: "description", content: "Delegate research, drafting and planning to the event agent." },
      { property: "og:title", content: "AI Agent — Event Operations Agent" },
      { property: "og:description", content: "Delegate research, drafting and planning to the event agent." },
    ],
  }),
  component: AgentPage,
});

type Turn =
  | { role: "user"; text: string }
  | { role: "agent"; steps: { label: string; done: boolean }[]; text?: string; cards: Card[]; error?: string; running: boolean };

function AgentPage() {
  const ev = useCurrentEvent();
  const { q } = Route.useSearch();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const busy = turns.some((t) => t.role === "agent" && t.running);
  const ran = useRef(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const send = async (text: string) => {
    if (!ev || !text.trim() || busy) return;
    setInput("");
    setTurns((t) => [...t, { role: "user", text }, { role: "agent", steps: [], cards: [], running: true }]);
    const patch = (fn: (a: Extract<Turn, { role: "agent" }>) => Extract<Turn, { role: "agent" }>) =>
      setTurns((t) => { const c = [...t]; c[c.length - 1] = fn(c[c.length - 1] as Extract<Turn, { role: "agent" }>); return c; });
    try {
      const res = await runAgent(text, ev, async (label) => {
        patch((a) => ({ ...a, steps: [...a.steps.map((s) => ({ ...s, done: true })), { label, done: false }] }));
        await new Promise((r) => setTimeout(r, 60)); // yield so each real stage renders
      });
      patch((a) => ({ ...a, steps: a.steps.map((s) => ({ ...s, done: true })), text: res.text, cards: res.cards, running: false }));
    } catch (e) {
      patch((a) => ({ ...a, error: (e as Error).message, running: false }));
    }
  };

  useEffect(() => {
    if (q && !ran.current) { ran.current = true; send(q); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  if (!ev) return null;

  return (
    <div className="flex h-[calc(100vh-130px)] flex-col">
      <div className="mb-4 flex items-center justify-between">
        <div><h1 className="text-xl font-semibold tracking-tight">AI Agent</h1><p className="text-sm text-muted-foreground">One agent across outreach, vendors and logistics. Results are saved as records.</p></div>
        <Pill tone="amber">Demo mode · deterministic workflows</Pill>
      </div>
      <div className="flex-1 space-y-5 overflow-y-auto rounded-xl border bg-card p-5">
        {turns.length === 0 && (
          <div className="mx-auto max-w-lg pt-10 text-center">
            <div className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-accent text-accent-foreground"><Sparkles className="h-5 w-5" /></div>
            <p className="mt-3 text-sm font-medium">What should I work on for {ev.name}?</p>
            <div className="mt-5 grid grid-cols-2 gap-2">
              {STARTERS.map((s) => <button key={s} onClick={() => send(s)} className="rounded-lg border px-3 py-2.5 text-left text-[13px] transition-colors hover:border-primary/40 hover:bg-accent/50">{s}</button>)}
            </div>
          </div>
        )}
        {turns.map((t, i) =>
          t.role === "user" ? (
            <div key={i} className="flex justify-end gap-2"><div className="max-w-[70%] rounded-xl bg-secondary px-3.5 py-2 text-[13px]">{t.text}</div><User className="mt-1.5 h-4 w-4 text-muted-foreground" /></div>
          ) : (
            <div key={i} className="flex gap-3">
              <div className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground"><Sparkles className="h-3.5 w-3.5" /></div>
              <div className="min-w-0 flex-1 space-y-2.5">
                {t.steps.length > 0 && (
                  <ol className="space-y-1">{t.steps.map((s, j) => (
                    <li key={j} className="flex items-center gap-2 text-xs text-muted-foreground">{s.done ? <Check className="h-3.5 w-3.5 text-success" /> : <Loader2 className="h-3.5 w-3.5 animate-spin" />}{j + 1}. {s.label}</li>
                  ))}</ol>
                )}
                {t.error && <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-danger-soft p-2.5 text-xs text-destructive"><XCircle className="h-4 w-4" />Workflow failed: {t.error}. No records were changed after this point.</div>}
                {t.text && <p className="text-[13px] leading-relaxed">{t.text}</p>}
                {t.cards.map((c, j) => <ResultCard key={j} card={c} />)}
              </div>
            </div>
          ),
        )}
        <div ref={end} />
      </div>
      <form className="mt-3 flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <Textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
          placeholder="Ask the agent… e.g. “Find two suppliers for attendee badges.”" className="min-h-11 resize-none bg-card" rows={1} />
        <Button type="submit" size="icon" disabled={busy || !input.trim()} aria-label="Send"><ArrowUp className="h-4 w-4" /></Button>
      </form>
      {turns.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">{STARTERS.map((s) => <button key={s} disabled={busy} onClick={() => send(s)} className="rounded-full border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-50">{s}</button>)}</div>
      )}
    </div>
  );
}
