import { useSyncExternalStore } from "react";
import type { Activity, AppState, Approval, EventRecord, ID } from "./types";
import { hashPayload } from "./policy";

const KEY = "eoa-state-v1";

export const uid = (p = "id") => `${p}_${Math.random().toString(36).slice(2, 9)}`;
export const nowIso = () => new Date().toISOString();

export function emptyState(): AppState {
  return {
    version: 1,
    workspace: "DubHacks Events",
    members: ["Saachi A.", "Jordan P.", "Priya K.", "Marcus L."],
    currentEventId: null,
    events: [],
    requirements: [],
    contacts: [],
    messages: [],
    vendors: [],
    documents: [],
    tasks: [],
    schedule: [],
    approvals: [],
    activity: [],
  };
}

let state: AppState | null = null;
const listeners = new Set<() => void>();

function load(): AppState {
  if (typeof window === "undefined") return emptyState();
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as AppState;
  } catch {
    /* corrupted storage falls back to empty */
  }
  return emptyState();
}

export function getState(): AppState {
  if (!state) state = load();
  return state;
}

export function setState(fn: (s: AppState) => AppState) {
  state = fn(getState());
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* ignore quota */
  }
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

const serverSnap = emptyState();
export function useAppState(): AppState {
  return useSyncExternalStore(subscribe, getState, () => serverSnap);
}

export function useHydrated() {
  return useSyncExternalStore(subscribe, () => true, () => false);
}

export function useCurrentEvent(): EventRecord | null {
  const s = useAppState();
  return s.events.find((e) => e.id === s.currentEventId) ?? null;
}

export function forEvent<T extends { eventId: ID }>(list: T[], eventId: ID | null | undefined) {
  return list.filter((x) => x.eventId === eventId);
}

// ----- mutations -----
type ListKey = Exclude<keyof AppState, "version" | "workspace" | "members" | "currentEventId">;

export function log(a: Omit<Activity, "id" | "at">) {
  setState((s) => ({ ...s, activity: [{ ...a, id: uid("act"), at: nowIso() }, ...s.activity] }));
}

export function insert<K extends ListKey>(key: K, items: AppState[K]) {
  setState((s) => ({ ...s, [key]: [...(s[key] as unknown[]), ...(items as unknown[])] }) as AppState);
}

export function update<K extends ListKey>(key: K, id: ID, patch: Partial<AppState[K][number]>) {
  setState(
    (s) =>
      ({
        ...s,
        [key]: (s[key] as { id: ID }[]).map((x) => (x.id === id ? { ...x, ...patch } : x)),
      }) as AppState,
  );
}

export function remove<K extends ListKey>(key: K, id: ID) {
  setState((s) => ({ ...s, [key]: (s[key] as { id: ID }[]).filter((x) => x.id !== id) }) as AppState);
}

export function createApproval(a: Omit<Approval, "id" | "status" | "approvedHash" | "createdAt">) {
  const ap: Approval = { ...a, id: uid("apr"), status: "pending", approvedHash: null, createdAt: nowIso() };
  insert("approvals", [ap]);
  log({ eventId: a.eventId, actor: "agent", kind: "proposed", summary: `Proposed: ${a.title}`, origin: "simulated" });
  return ap;
}

/** Editing an approval payload always invalidates any prior approval. */
export function editApprovalPayload(id: ID, payload: string) {
  const ap = getState().approvals.find((a) => a.id === id);
  if (!ap) return;
  const changed = ap.payload !== payload;
  update("approvals", id, { payload, status: changed ? "pending" : ap.status, approvedHash: changed ? null : ap.approvedHash });
  if (changed && ap.status === "approved")
    log({ eventId: ap.eventId, actor: "system", kind: "changed", summary: `Approval invalidated after edit: ${ap.title}`, origin: "system" });
}

export function approve(id: ID, by: string) {
  const ap = getState().approvals.find((a) => a.id === id);
  if (!ap) return;
  update("approvals", id, { status: "approved", approvedHash: hashPayload(ap.payload) });
  log({ eventId: ap.eventId, actor: "organizer", kind: "approved", summary: `${by} approved: ${ap.title}`, origin: "organizer" });
}

export function reject(id: ID, by: string) {
  const ap = getState().approvals.find((a) => a.id === id);
  if (!ap) return;
  update("approvals", id, { status: "rejected", approvedHash: null });
  log({ eventId: ap.eventId, actor: "organizer", kind: "rejected", summary: `${by} rejected: ${ap.title}`, origin: "organizer" });
}

export function resetAll() {
  setState(() => emptyState());
}

export function money(n: number | null | undefined, cur = "USD") {
  if (n == null) return "Unknown";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 2 }).format(n);
}
