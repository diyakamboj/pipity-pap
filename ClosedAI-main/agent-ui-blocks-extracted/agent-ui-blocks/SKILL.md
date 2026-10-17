---
name: agent-ui-blocks
description: Render structured, interactive UI (cards, charts, steppers, tables, forms, emails, approvals, etc.) in a side canvas by emitting fenced ```ui-block``` JSON inside normal markdown output. Use this skill whenever a task's output would benefit from visual UI instead of plain text — onboarding flows, approvals, comparisons, dashboards, people/team info, workflows, or any agent task that needs a rich, task-specific interface. Always consult this skill before hand-rolling custom HTML/markdown for a side canvas, and whenever the user asks to "show", "display", or build UI for agent output.
---

# Agent UI Blocks

A closed-vocabulary system for generating UI inside ordinary markdown. The agent keeps writing markdown as usual; wherever a piece of UI belongs, it drops in a fenced code block tagged `ui-block` containing a small JSON payload. A registry on the frontend maps `type` to a React component and renders it in the side canvas. Everything else in the markdown (headings, prose, lists) renders normally and degrades gracefully anywhere this convention isn't understood.

This skill is the wire format + component catalog for that system — read it before emitting any `ui-block` fence.

## Wire format

```
Some normal prose here.

​```ui-block
{"type": "employee-card-compact", "version": 1, "props": {"name": "Priya Nair", "role": "Staff Engineer", "status": "active"}}
​```

More prose after it. Multiple blocks and prose can be freely interleaved.
```

Every payload is a single JSON object with exactly three top-level keys:

| key | required | meaning |
|---|---|---|
| `type` | yes | one of the registered block types (see `references/block-catalog.md`) |
| `version` | yes | always `1` for this pack — lets the shape evolve later without breaking old output |
| `props` | yes | the data for that block — shape is type-specific |

**Rules:**
- One block per fence. Don't nest JSON objects for multiple blocks in one fence.
- Valid JSON only — no trailing commas, no comments, double-quoted keys/strings.
- If a `type` is unrecognized or the JSON is malformed, the canvas falls back to a visible raw/error card instead of crashing — so an occasional miss is non-fatal, but always prefer a real registered type over inventing one.
- Don't invent new `type` values. If nothing in the catalog fits perfectly, **just use plain markdown text instead of forcing it into a block**. Do NOT attempt to create generic cards for text.
- Compose, don't create bespoke types. A real task's UI (e.g. onboarding, an incident, a review) is usually several blocks stitched together with prose in between, not one custom block.

## Picking a block

Skim the category names below, then open `references/block-catalog.md` for the full list and a copy-pasteable example `props` payload for every one of the 58 block types.

| category | for |
|---|---|
| **people** | employee/person cards (5 density variants), team rosters, org charts |
| **data & charts** | stat grids, bar/line/area/donut charts, gauges |
| **workflow** | checklists, steppers (vertical/horizontal), approvals, timelines, progress bars |
| **content** | email previews, chat threads, alerts, tables, quotes, code, badges, ratings, attachments, calendar events, avatar groups |
| **forms & input** | field summaries, polls, signature blocks, toggle settings |
| **directory** | document previews, search results, FAQs, key-value lists |
| **metrics** | balance meters, spend breakdowns, before/after comparisons, milestones |
| **general purpose** | `stat-strip`, `icon-list`, `link-preview`, `accordion`, `tag-cloud`, `empty-state`, `divider-label`, `custom-list` — the flexible, "could be almost anything" tier |

When in doubt between a specific block and a general-purpose one, prefer the specific block if the data fits its shape — it renders more precisely. If no block fits well, **do not use a block**. Just write plain markdown text outside of any `ui-block` fence.

## Customization system

Every block that shows an accent color accepts a `tone` prop with two ways to set it:

1. **Named tone** — one of `"violet" | "teal" | "amber" | "emerald" | "red" | "blue" | "pink" | "slate"`. This is the default and keeps output visually consistent with the rest of the canvas.
2. **Raw hex color** — any CSS hex string, e.g. `"tone": "#0ea5e9"`. Use this when a task has its own brand/status color that doesn't map cleanly to a named tone (e.g. reflecting a real product's brand color, or a custom severity scale). Unrecognized non-hex strings silently fall back to violet, so only use hex or the exact named list.

Many blocks also accept, where it makes sense for that block:

- `"size": "compact" | "comfortable" | "spacious"` — default is `"comfortable"`. Use `"compact"` when several blocks are stacked densely, `"spacious"` when a block is the sole focus of the canvas.
- `"align": "left" | "center"` — for card-style blocks, to center a hero/empty-state style layout.
- Per-item `tone` overrides inside list-shaped blocks (`stat-strip`, `icon-list`, `tag-cloud`, `custom-list`) — set a `tone` on an individual item to override the block-level default for just that row, e.g. flagging one stat red while the rest stay neutral.

Don't over-customize: pick one tone per logical block and reserve per-item overrides for genuinely different states (e.g. an overdue item in a task list, a blocked stat in a strip).

## Composing a full task UI

A real agent task is rarely one block. Interleave prose and multiple blocks the way you would write a short report:

```
Here's where the setup workflow stands:

​```ui-block
{"type": "stepper", "version": 1, "props": {"title": "Setup steps", "steps": [{"label": "Connect your calendar", "status": "complete"}, {"label": "Invite a teammate", "status": "pending"}]}}
​```

Two steps left — want me to nudge your teammate for you?
```

Or, for something with no dedicated block, lean on the general-purpose tier composed together:

```
​```ui-block
{"type": "alert-banner", "version": 1, "props": {"title": "Comp review — Q3", "severity": "warning", "body": "3 reports pending manager sign-off."}}
​```

​```ui-block
{"type": "custom-list", "version": 1, "props": {"title": "Pending", "tone": "amber", "items": [{"label": "Jae Kim", "meta": "awaiting manager"}, {"label": "Lucia Ferrer", "meta": "awaiting manager"}]}}
​```
```

## Reference

- `references/block-catalog.md` — every block type, grouped by category, each with a complete example `props` payload generated directly from the component pack. Open this before emitting any block you haven't used before.
- `assets/agent-ui-block-pack.jsx` — the actual renderer (parser + component registry + canvas). Not needed to emit blocks, but useful if the user asks to see, modify, or extend the rendering side of this system.
