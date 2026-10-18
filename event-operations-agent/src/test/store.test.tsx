import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("workspace subscriptions and saved state", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => cleanup());

  it("unsubscribes safely when a workspace view unmounts", async () => {
    const store = await import("@/lib/store");
    function View() {
      return <output>{store.useAppState().workspace}</output>;
    }
    const first = render(<View />);
    act(() => store.setState((s) => ({ ...s, workspace: "Workshop team" })));
    expect(screen.getByText("Workshop team")).toBeInTheDocument();
    expect(() => first.unmount()).not.toThrow();
    act(() => store.setState((s) => ({ ...s, workspace: "Updated team" })));
    const second = render(<View />);
    expect(screen.getByText("Updated team")).toBeInTheDocument();
    expect(() => second.unmount()).not.toThrow();
  });

  it("reloads the selected workshop and its records from saved state", async () => {
    const seed = await import("@/lib/seed");
    const store = await import("@/lib/store");
    const eventId = seed.loadDemo();
    const saved = store.getState();
    expect(saved.currentEventId).toBe(eventId);
    expect(saved.events.find((event) => event.id === eventId)?.attendees).toBe(80);
    vi.resetModules();
    const refreshed = await import("@/lib/store");
    expect(refreshed.getState()).toEqual(saved);
    expect(refreshed.forEvent(refreshed.getState().contacts, eventId)).toHaveLength(1);
    expect(refreshed.forEvent(refreshed.getState().schedule, eventId)).toHaveLength(6);
  });
});