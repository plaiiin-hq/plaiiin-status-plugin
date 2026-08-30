---
title: Rendering pipeline — how a probe's output becomes UI
summary: The complete presentation path from a probe result through the status tree to a 2D tile grid, a 3D plate, a plain key/value row, or an SVG infographic — including the three ways a tile disappears without an error.
audience: Engineers authoring probe layouts, adding widgets, or debugging a tile that renders blank; agents answering "why is nothing showing".
# source_of_truth paths are in the Status server repository, quoted so a claim
# can be traced by anyone who has it.
source_of_truth:
  - Status-Frontend/src/lib/plate/widgets/registry.ts
  - Status-Frontend/src/lib/plate/types.ts
  - Status-Frontend/src/lib/plate/utils/slot-value.ts
  - Status-Frontend/src/lib/plate/utils/flow.ts
  - Status-Frontend/src/lib/plate/utils/format.ts
  - Status-Frontend/src/lib/plate/tiles.ts
  - Status-Frontend/src/components/widgets/TileGrid.vue
  - Status-Frontend/src/components/common/ProbeLayout.vue
  - Status-Frontend/src/components/common/ProbeRow.vue
  - Status-Frontend/src/components/common/NodeTree.vue
  - Status-Frontend/src/components/common/StatusDot.vue
  - Status-Frontend/src/components/common/InfographicCard.vue
  - Status-Frontend/src/components/base/ExpandCard.vue
  - Status-Frontend/src/composables/useStatusData.ts
  - Status-Frontend/src/utils/infographic.ts
  - Status-Frontend/src/views/TopologyView.vue
  - Status-Server/src/main/java/com/plaiiin/status/catalog/CatalogService.java
  - Status-Server/src/main/java/com/plaiiin/status/infrastructure/StatusTree.java
  - Status-Server/src/main/java/com/plaiiin/status/agent/AgentController.java
related_docs:
  - Status-Server/docs/probe-plugin-format.md
  - Status-Server/docs/data-model.md
  - Status-Frontend/docs/plate-architecture.md
verified: 2026-08-28
---

# Rendering pipeline — how a probe's output becomes UI

This document owns **presentation**: what happens to a probe result after the server has it. It does not cover how a probe is authored or how history is stored.

| Neighbouring document | Owns |
|---|---|
| [Plate Architecture](./plate-architecture.md) | The 3D plate subsystem internals — builder contract, schema, icon, editor round-trip, how to add a widget |
| [Probe Plugin Format](probe-plugin-format.md) | Every file and field a probe package ships — `probe.yml`, `check.js` and its sandbox, actions, detect, credentials, and how an author **chooses** a fan-out mechanism |
| the server's data model | Identity and series keys, storage at four resolutions, rollups, WAL, retention |
| **this file** | The path from an emitted value to pixels, on all four surfaces |

This document never explains how to *author* a probe. Every `probe.yml` field, `check.js` API and sandbox question belongs to [Probe Plugin Format](probe-plugin-format.md); every storage, key and retention question belongs to the server's data model. What follows assumes a result already exists and asks only what the UI does with it.

## Quick answers

| Question | Answer | Anchor |
|---|---|---|
| How many widgets exist? | 34 registry entries + 1 alias = 35 keys; 33 offered in the picker; 10 render on a 2D card | [Widget registry](#widget-registry-34-entries-1-alias-33-picker-chips) |
| Which rendering mode does my probe get? | Authored `layout:` → tile grid. No `layout:` → key/value rows. The rows are the majority path | [Two rendering modes](#two-rendering-modes-authored-tiles-vs-the-row-fallback) |
| How wide can a tile be? | 4 units. A wider `tile:` span is clamped, never errors | [The 4-unit panel](#the-4-unit-panel-and-how-a-wider-span-is-clamped) |
| My tile renders as an empty box. Why? | Unknown widget name, a path the probe never emitted, or `path: ""` with no `''` key | [Fails silently](#fails-silently) |
| Does the tree have a depth or row cap? | No. `NodeTree.vue` recurses unbounded and renders every child | [Tree rendering](#tree-rendering-depth-indentation-expansion-separators) |
| Is `layout:` used by both 2D and 3D? | Yes. One `layout:` array; 3D derives a `PlateSpec` from it at `TopologyView.vue:1908` | [The full path](#the-full-path-probe-result--pixels) |
| Where do custom SVG infographics live? | `<probe>/infographic/template.svg` + `bindings.yml`; 1 of 44 catalog probes ships one | [SVG infographics](#custom-svg-infographics-svgtemplate--bindings) |
| Does an unknown widget behave the same in 2D and 3D? | No. 2D leaves the cell empty; 3D silently substitutes the `value` widget | [Unknown widget](#rule-1-unknown-widget-name) |
| What does `path: ""` mean? | The probe's primary series — a real key, not "unset" | [The empty primary path](#rule-3-the-empty-primary-path-) |
| How often does the UI refresh? | 5 s poll plus an SSE `probe` event that forces an immediate reload | [The status tree](#the-status-tree-the-ui-consumes) |
| `streamValues` or `scriptResult.services` — what's the visible difference? | `streamValues` renders inside one card; `services` become real tree nodes with their own dots and history | [Two fan-out renderings](#streamvalues-vs-scriptresultservices-two-different-renderings) |
| How do I see a probe's own discovered children? | Open the `N sub-checks` disclosure under the probe row. Closed by default; the closed row names any failure inside | [Caveat](#caveat-a-probe-nodes-own-children-are-never-rendered-by-nodetree) |

---

## The full path: probe result → pixels

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │ SERVER                                                              │
  │  probe.yml (catalog)  ──►  CatalogEntry { layout, svgTemplate, … }  │
  │  check.js             ──►  result { streamValues, sparklines,       │
  │                                     outputTypes, scriptResult,      │
  │                                     actions, logs, message, state } │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │  GET /api/status  (whole tree, one call)
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │ useStatusData.ts   normalizeNodes() → { projects[], hosts[] }       │
  │   poll 5 s  +  SSE 'probe' → immediate reload                       │
  └────────────────────────────────┬────────────────────────────────────┘
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │ ExpandCard.vue      one card per project / host                     │
  │   └── NodeTree.vue  recursive; branch rows (app/service/group/…)    │
  │         └── NodeTree.vue  …unbounded depth, ms-4 per level          │
  │               └── ProbeRow.vue     ← the LEAF. always a row.        │
  │                     ⚠ type==='probe' wins over children:            │
  │                       a probe's own children are NOT drawn          │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │ click the chevron
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   hasInfographic            result.layout           no layout
              │                    │                    │
              ▼                    ▼                    ▼
   InfographicCard.vue      ProbeLayout.vue        StreamTree.vue
   GET /api/probes/         └─ TileGrid.vue        nested key/value rows
      infographic              └─ 10 × 2D widget   (+ per-`group:` tiles)
   v-html the SVG,               components         + actions + logs
   applyPatches() by id       + StreamTree.vue
                                for uncovered paths

  ── separate surface, same layout[] ─────────────────────────────────────
  TopologyView.vue  (/topology, /widgets showcase, ProbeIDE ▸ Plate tab)
     result.plate  ?? derive PlateSpec from result.layout   :1908
        └── flowLayout()          utils/flow.ts   pack + wrap in plate units
              └── buildSlotWidget()  TopologyView.vue:1307
                    └── WIDGET_BUILDERS[kind]  → THREE.Object3D
                          (unknown kind → falls back to `value`)
```

Four terminal surfaces exist, and a probe can reach more than one:

| Surface | Component | Chosen when |
|---|---|---|
| Row (in-tree) | `ProbeRow.vue` | Always. Every probe is a row first. |
| 2D tile grid | `ProbeLayout.vue` → `TileGrid.vue` | Row expanded **and** `result.layout` present **and** no infographic |
| Key/value tree | `StreamTree.vue` | Row expanded and no layout — or, alongside tiles, for paths no tile covers |
| SVG infographic | `InfographicCard.vue` | `node.hasInfographic` is true; **pre-empts** both of the above |
| 3D plate | `TopologyView.vue` | The `/topology` route, the `/widgets` showcase, or the Probe IDE's Plate tab |

`ProbeRow.vue:92-100` is the whole precedence rule, and it is exclusive: an infographic hides the tiles, and tiles are never shown next to an infographic.

---

## The status tree the UI consumes

`useStatusData.ts` fetches `/api/status` once and hands the SPA two arrays: `allProjects` and `hosts`. Both are passed through `normalizeNodes()` (`useStatusData.ts:8`), which does exactly three things: coalesces `state ?? status ?? 'UNKNOWN'`, coalesces `displayName ?? name`, and recurses into `children`.

| Fact | Value | Cite |
|---|---|---|
| Refresh | 5 000 ms poll | `useStatusData.ts:225` |
| Push refresh | SSE `probe` event → full reload | `useStatusData.ts:229` |
| Fetch failure | Silent; previous tree is kept | `useStatusData.ts:216` |
| Node types seen live | `project`, `host`, `app`, `service`, `probe` | measured |
| Leaf test used for counting | "has no children", not "type === probe" | `useStatusData.ts:129` |

Measured on one real deployment, 2026-08-28:

| Tree | Nodes | With children | Exactly 1 child | Max depth | Probe nodes |
|---|---|---|---|---|---|
| `projects` | 485 | 175 | 63 | 5 | 315 |
| `hosts` | 839 | 222 | 39 | 4 | 636 |
| combined | 1 324 | 397 | 102 | 5 | 951 |

A quarter of all branches (102 of 397) have exactly one child, so the tree is visually deep for its information content — the indent ladder is often carrying a single row.

---

## Two rendering modes: authored tiles vs the row fallback

There is one switch, and it is the presence of `result.layout`.

```
if (probe.result.layout)  → ProbeLayout.vue → TileGrid.vue   (authored tiles)
else                      → StreamTree.vue                    (key/value rows)
```

Cited at `ProbeRow.vue:127` and `ProbeRow.vue:145`.

**The row fallback is the majority path.** Measured:

| Population | Ship a `layout:` | Do not | Fallback share |
|---|---|---|---|
| Catalog probe types (`Status-Server/.../catalog/probes/*/probe.yml`) | 11 of 44 | 33 | 75% |
| Live probe nodes, 2026-08-28 | 59 of 951 | 892 | 94% |

The 11 catalog types with a layout: `demo-widgets`, `docker-services`, `folder-watch`, `host-metrics`, `http-endpoint`, `lifx`, `plaiiin-mirror`, `system-cpu`, `system-disk`, `system-memory`, `webcam`.

The two modes are not exclusive at the probe level. When a layout exists, `ProbeRow.vue:51-90` computes `uncoveredStreamValues` — every emitted path not claimed by a top-level tile, plus ancestors of claimed paths — and renders **those** through `StreamTree` underneath the tile grid. So an authored layout adds tiles; it never hides data. Tiles carrying `group:` are deliberately excluded from the covered set (`ProbeRow.vue:61`) because they render per-instance inside the tree instead.

### What the row fallback actually draws

`ProbeRow.vue` renders a fixed-height 28 px row (`--row-h`) containing, left to right:

| Element | Condition | Cite |
|---|---|---|
| Chevron | `hasInfographic \|\| hasStream`; otherwise a 10 px spacer | `ProbeRow.vue:106` |
| 32×20 sparkline | `result.sparklines['']` has points for the active 1d/7d mode | `ProbeRow.vue:33-36` |
| 32×20 flat colour bar | No `''` sparkline — the fallback for the fallback | `ProbeRow.vue:112` |
| Probe name + truncated message | Always | `ProbeRow.vue:114-115` |
| `StatusBadge` | `state !== 'OK'` only | `ProbeRow.vue:117` |

State colour is chosen from the probe state, not from any value: `ERROR` → `--status-red`, `WARNING` → `--status-amber`, everything else → `--status-green` (`ProbeRow.vue:40-44`). Note `UNKNOWN` gets the **green** bar here, while `StatusDot.vue:12` gives `UNKNOWN` grey — the row's colour bar and the branch dot above it disagree for an unknown probe.

---

## The 4-unit panel and how a wider span is clamped

The 2D panel is **4 units wide, always**. The clamp lives in `TileGrid.vue`:

| Rule | Implementation | Cite |
|---|---|---|
| `MAX_COLUMNS = 4` | Constant | `TileGrid.vue:21` |
| A `columns` prop may narrow, never widen | `Math.min(4, Math.max(1, floor(columns ?? 4)))` | `TileGrid.vue:23-25` |
| A tile's column span is clamped to the grid width | `colSpan: Math.min(gridColumns, Math.max(1, w \|\| 1))` | `TileGrid.vue:35` |
| A tile's **row** span is NOT clamped | `rowSpan: Math.max(1, h \|\| 1)` — no upper bound | `TileGrid.vue:36` |
| A malformed `tile:` string degrades to 1x1 | `(t.tile \|\| '1x1').split('x').map(Number)` then `w \|\| 1` | `TileGrid.vue:29,35` |
| Row height | `grid-auto-rows: 80px` | `TileGrid.vue:65` |
| Gap | 8 px | `TileGrid.vue:66` |

`TileGrid.vue:30-31` states the reason in the source: a tile wider than the grid *silently overflows its container in CSS grid rather than erroring*, so the clamp is a deliberate guard, not a validation.

### Canonical tile sizes

`tiles.ts:8-17` defines `TILE_SIZES`, which drives the tile picker in `PlateEditor`:

`1x1` · `2x1` · `1x2` · `2x2` · `3x1` · `3x2` · `4x1` · `4x2`

The catalog additionally uses **`4x3`**, which is *not* in `TILE_SIZES` — it renders correctly (row spans are unclamped) but cannot be selected in the editor. It appears twice, both in `webcam/probe.yml:38` and `webcam/probe.yml:42`, for the snapshot and live-stream image tiles.

Measured tile usage:

| Tile | Catalog (83 total) | Live board (253 total) |
|---|---|---|
| `1x1` | 48 | 152 |
| `2x1` | 14 | 59 |
| `4x1` | 6 | 36 |
| `2x2` | 5 | 0 |
| `3x2` | 3 | 0 |
| `1x2` | 3 | 0 |
| `4x3` | 2 | 0 |
| `3x1` | 2 | 6 |

Four of the eight canonical sizes — `2x2`, `1x2`, `3x2`, `4x2` — are **supported but currently unused on one real deployment**. `4x2` is unused in the catalog as well.

### The 3D plate uses the same numbers, differently

`TopologyView.vue:1908-1929` derives a `PlateSpec` from `result.layout` when no explicit `result.plate` exists (no catalog probe defines `plate:` today — the derivation is the only path in practice). Each tile becomes a `PlateSlot`; `tile: "3x2"` is parsed into `w: 3, h: 2`.

`flowLayout()` in `utils/flow.ts` then packs slots left-to-right with wrap:

| Rule | Value | Cite |
|---|---|---|
| Default plate width when unset | `4` units | `flow.ts:22` |
| Default gap | `0.12` units | `flow.ts:23` |
| Default padding | `0.3` units | `flow.ts:24` |
| Wrap target | `inner = width - padding * 2` | `flow.ts:25` |
| Explicit `x`/`y` bypasses packing | Both must be non-null | `flow.ts:36` |
| Plate unit → world unit | `PLATE_UNIT = 40` | `flow.ts:11` |
| Editor mode forces `gap: 0` | Otherwise cells drift by cumulative gaps | `TopologyView.vue:1060` |

There is **no clamp in `flowLayout`**. A slot wider than `inner` still lands: the wrap test at `flow.ts:40` moves it to a fresh row, then places it anyway, and the plate mesh auto-fits to the packed bounds (`TopologyView.vue:1073-1078`). So the same `tile: "6x1"` is truncated to 4 columns on a 2D card and rendered 6 units wide on the 3D plate.

---

## Widget registry: 34 entries, 1 alias, 33 picker chips

`registry.ts:146-186` defines `WIDGETS` as 34 entries. `registry.ts:188` then adds `WIDGETS.plate = WIDGETS.tray`, making 35 keys total.

| Set | Count | Note |
|---|---|---|
| `WIDGETS` literal entries | 34 | one builder each |
| `+ plate` alias | 35 keys | `plate` and `tray` are the same object |
| `WIDGET_NAMES` (picker chips) | 33 | excludes `state-dot` and `plate` |
| Entries with a dedicated schema file | 32 | `tray` and `state-dot` carry `schema: []` |
| Entries in `WIDGET_ICONS` | 33 | `state-dot` uses `placeholderIcon`, which `registry.ts:220` filters out so `WidgetIcon.vue`'s `?` still draws |
| 2D widget kinds in `ProbeLayout.vue` | 10 | a **different** set — see below |

Two exclusions are deliberate and documented at `registry.ts:191-196`: `state-dot` has a builder but no schema or icon, and `plate` is a legacy alias. Both stay in `WIDGETS` so the builder dispatcher resolves them; neither appears as a picker chip.

There are **two** `WIDGET_BUILDERS` maps. `registry.ts:207` is the source of truth and is what `TopologyView.vue:27` imports. `builders/index.ts:60` is a hand-maintained legacy copy kept for backward compatibility (its header says so) and is what `builders/tray.ts:20` imports for recursive sub-slot dispatch. A widget added only to `registry.ts` therefore renders at the top level but **not** inside a `tray`.

### 2D and 3D render different widget sets

`ProbeLayout.vue:185-225` is a flat `v-if`/`v-else-if` chain over 10 kinds. It shares only 5 names with the 3D registry.

| Kind | 2D card | 3D plate |
|---|---|---|
| `gauge`, `value`, `chart`, `bar`, `bars` | ✅ | ✅ |
| `color`, `list`, `grid`, `multizone`, `image` | ✅ | ❌ (no builder) |
| the other 29 registry entries | ❌ | ✅ |

The catalog's 11 layouts use **33 distinct widget names**; `ProbeLayout.vue` renders only 7 of them (`value`, `gauge`, `chart`, `bars`, `multizone`, `image`, `color`). Everything else in an authored layout — `progress-circle`, `tray`, `paper-stack`, `action`, `thermometer`, … — occupies a labelled but **empty** cell on the 2D card and only comes alive on the 3D plate.

### Complete widget table

`✅` = renders. `➖` = the surface has no implementation for that kind. Required fields are the schema keys the builder needs to produce anything; `path` resolves via `resolveSlotValue()`, `paths` is a glob.

| Widget | Required | Purpose | 2D | 3D | Notes |
|---|---|---|---|---|---|
| `value` | `path` | Glossy raised slab, canvas-textured face — the default readout | ✅ | ✅ | Also the 3D fallback for any unknown kind |
| `gauge` | `path` | 270° torus arc, filled proportionally | ✅ | ✅ | Formats by the declared output type. Until 2026-08-30 `formatWidgetValue` forced `%` for any gauge whatever the type said |
| `bar` | `path` | Single bar | ✅ | ✅ | 3D `bar` is a re-export of `bars` (`builders/bar.ts`) |
| `bars` | `paths` | Row of vertical columns, height ∝ each matched value | ✅ | ✅ | Needs a `paths` **glob**, not `path` |
| `chart` | `path` | Sparkline as blocks / area / ridge | ✅ | ✅ | Reads `sparklines[path]`, **not** `streamValues[path]` |
| `badge` | `path` | State-coloured pill / shield / hex for short enums | ➖ | ✅ | |
| `log` | — | Scrolling severity-coloured log strip | ➖ | ✅ | Reads `scriptResult`, not a path |
| `text` | `path` | Raised slab with text readout | ➖ | ✅ | |
| `fluid-tank` | `path` | Glass cylinder, animated liquid surface | ➖ | ✅ | Drop-in for `gauge`/`bar` |
| `thermometer` | `path` | Mercury bulb + rising column | ➖ | ✅ | |
| `compass` | `path` | Rotating needle, value = bearing 0..360 | ➖ | ✅ | |
| `radar` | `path` | Circular scope with rotating sweep | ➖ | ✅ | Reads `sparklines` |
| `orbital` | `path` | Electrons round a nucleus; orbit count = value | ➖ | ✅ | |
| `flame` | `path` | Animated plume, height ∝ value | ➖ | ✅ | |
| `cake` | `path` | Tiered cake, candles = value | ➖ | ✅ | |
| `hourglass` | `path` | Glass bulbs with falling sand | ➖ | ✅ | |
| `paper-stack` | `path` | Pile of slabs, one per file | ➖ | ✅ | Reads `scriptResult.files`; extra keys `growth`, `paper-thick`, `fade-start`, `fade-end` |
| `heatmap` | `paths` | Grid of tiles; colour = state, brightness = value | ➖ | ✅ | Needs a glob |
| `odometer` | `path` | Rolling digit drums | ➖ | ✅ | |
| `split-flap` | `path` | Split-flap text board, animates on change | ➖ | ✅ | For string enums |
| `delta` | `path` | Big value + up/down chevron with % change | ➖ | ✅ | Reads `sparklines` for the comparison |
| `uptime-strip` | `path` | Row of ticks coloured by value | ➖ | ✅ | **Topology-only.** Reads `data.sparklines`; default ramp is *higher = worse*, invert with `reverse: true` (`builders/uptime-strip.ts:11-22`) |
| `progress-circle` | `path` | N-segment ring; `mode` = spinner / progress-fill / heartbeat | ➖ | ✅ | `spinner` and `heartbeat` need no value at all |
| `node` | `style` | Embeds a referenced graph node's mesh onto a slot | ➖ | ✅ | Topology-only by nature; there is no graph on a card |
| `action` | `path`, `style` | Interactive control that fires a declared action; `style` = button / switch / knob / slider / lever | ➖ | ✅ | 13 uses in the catalog, all invisible on the 2D card |
| `tray` | — | Raised sub-plate carrying its own flow-packed sub-widgets | ➖ | ✅ | `cols`/`rows` set the inner grid; recurses via the **legacy** builder map |
| `plate` | — | Alias of `tray` | ➖ | ✅ | Not a picker chip |
| `chart-billboard` | `path` | Sparkline on an emissive screen; flat / tilted / upright | ➖ | ✅ | |
| `oscilloscope` | `path` | Round CRT, sweeping waveform with phosphor trail | ➖ | ✅ | Reads `sparklines` |
| `vu-meter` | `path` | Vertical lit cells with peak-hold marker | ➖ | ✅ | |
| `matrix-rain` | `path` | Cascading glyphs, density ∝ value | ➖ | ✅ | |
| `ticker-tape` | — | Horizontal scrolling text band | ➖ | ✅ | Reads `scriptResult` |
| `stacked-bars-tower` | `path` | Vertical bucket column, total height = value | ➖ | ✅ | |
| `split-flap-board` | — | Multi-row split-flap departure board | ➖ | ✅ | Reads `scriptResult` |
| `state-dot` | — | Small glowing orb on a pedestal | ➖ | ✅ | Builder exists; **excluded from the picker** (`registry.ts:184`) |
| `color` | `path` | Swatch of a parsed colour string | ✅ | ➖ | 2D only |
| `list` | `paths` | Key/value list over matched paths | ✅ | ➖ | 2D only; **unused in the catalog** |
| `grid` | `paths` | Coloured value grid over matched paths | ✅ | ➖ | 2D only; **unused in the catalog** |
| `multizone` | `paths` | Multi-colour strip, zone-sorted | ✅ | ➖ | 2D only; `lifx` |
| `image` | `path` | Still image or MJPEG stream | ✅ | ➖ | 2D only; `mode` switches on output type `mjpeg` |

Widget names used in the catalog that exist in **neither** registry, and therefore render nowhere: `slider` (3 uses), `hue-slider`, `kelvin-slider`, `color-picker` — all in `lifx/probe.yml:91-136`, all nested inside `tray` slots.

---

## Slot value resolution: how a path becomes a number

`utils/slot-value.ts` is the single resolver for the 3D path; `ProbeLayout.vue` re-implements the 2D equivalent inline.

| Case | Behaviour | Cite |
|---|---|---|
| No `streamValues` at all | `{ num: null, state: 'UNKNOWN', matched: [] }` | `slot-value.ts:12` |
| `slot.paths` (glob) | `*` → `[^/]+`, anchored `^…$`; every match collected into `matched[]` | `slot-value.ts:14` |
| Glob primary value | `matched[0]` — **iteration order of the object**, not sorted | `slot-value.ts:25` |
| Glob state | The first match carrying a `state` | `slot-value.ts:22` |
| `slot.path` (exact) | `sv[path]`; missing key → `num: null, state: 'UNKNOWN'` | `slot-value.ts:27-28` |
| Non-numeric value | `parseFloat` → `NaN` → `num: null`, state still resolves | `slot-value.ts:29-30` |

Formatting is shared. `format.ts:88` `formatWidgetValue(v, outputType, widget)` is the one formatter, and `ProbeLayout.vue:51-59` delegates to it. Its header carries the scar: a private 2D copy once drifted and rendered `9986%` for a coverage of `99.86`, and rendered an 8-digit trade count ungrouped where the plate showed `26m`.

| Output type | Rendering |
|---|---|
| `compact` | `1k`, `1.1k`, `103k`, `1.1m`, `10m` — 3 significant figures, never a padded zero |
| `percent` | `v ≤ 1 → v×100`; suffix `%`. The WIDGET no longer forces this — see the gauge row above |
| `bytes` | `B` / `KB` / `MB` / `GB` / `TB`, decimal (1e3), 1 dp |
| `duration` | `45s`, `12m`, `3h 20m`, `2d 4h` |
| `decimal`, `number` | Grouped, 2 dp for fractions |
| `timestamp` | 2D only — relative `5m ago` (`ProbeLayout.vue:62`) |
| `boolean` | 2D only — `Yes` / `No` (`ProbeLayout.vue:57`) |
| anything else | Grouped, 1 dp for fractions |

Thousands separator defaults to an **apostrophe** (`25'970'020`), the Swiss convention, chosen because a comma is misread as a decimal point by European readers (`format.ts:26-29`).

Label and unit lookup are two-pass in both `format.ts:9` and `ProbeLayout.vue:71`: exact `path` first, then **leaf against leaf**. That second pass is what makes a templated declaration `cantons/{canton}/d7` match a concrete emitted `cantons/ZH/d7`. It also means two different paths ending in the same leaf will resolve to the same output type.

---

## Tree rendering: depth, indentation, expansion, separators

`NodeTree.vue` is the recursive branch renderer. `ProbeRow.vue` terminates it.

| Rule | Behaviour | Cite |
|---|---|---|
| Recursion | `NodeTree` renders `NodeTree` for `node.children`; **no depth cap** | `NodeTree.vue:73` |
| Row cap | **None.** Every child is rendered; no virtualisation, no "show more" | `NodeTree.vue:50` |
| Indentation | `ms-4` (Bootstrap, 1.5 rem = 24 px) on the child container, one per level | `NodeTree.vue:72` |
| Row height | Fixed `var(--row-h, 28px)`, not content-driven | `NodeTree.vue:118` |
| Sibling spacing | `4px`, applied only **between** siblings via `.node-item + .node-item` | `NodeTree.vue:95` |
| Header row height | `34px` — 28 × 1.2, the one deliberate exception | `ExpandCard.vue:130` |
| Expansion key | `parentPath + ' / ' + node.name`, built by `nodePath()` | `NodeTree.vue:27` |
| Expansion default | **Open.** `collapsed` is empty, `isOpen = !collapsed[key]` | `NodeTree.vue:44-45` |
| Expansion scope | Component-local `reactive({})` — **not persisted**, resets on remount | `NodeTree.vue:44` |
| Chevron | Only when `children.length > 0`; otherwise a 10 px `.chevron-spacer` | `NodeTree.vue:65-66` |
| `alwaysExpandTop` | Depth 0 renders open, inert, chevron-less; deeper rows keep theirs | `NodeTree.vue:21-25` |

The expansion key is a **path string joined with `' / '`**, so two sibling subtrees containing the same name at the same path collapse together, and a node whose own name contains `' / '` can collide with a different path. The `v-for` key is `node.name` alone (`NodeTree.vue:50`), which is a weaker key than the path used for state.

### Separator rules

Documented in full at `NodeTree.vue:81-107`. The short version:

| Rule | Reason |
|---|---|
| No `border-bottom` on rows | Nested levels are indented, so per-row rules started at different offsets, trailed off mid-card, and divided nothing |
| A separator sits **between top-level siblings only** — `.node-item-top + .node-item-top::before` | Depth 0 is the only level where all rows share a left edge |
| Drawn as a `::before` pseudo-element | Keeps row content from shifting by the inset |
| Inset `calc(2px - var(--bs-card-spacer-x, 1rem))` | The 2 px is measured from the **card** edge; `.card-body` carries 16 px of padding, so a plain `margin: 0 2px` renders 18 px in and reads as a floating dash |

### Icons and dots

`iconFor()` (`NodeTree.vue:32`) maps `node.icon` first, then falls back per type: `app` → `app-window`, `service` → `component`, `group` → `folder`, `agent` → `cpu`, `host` → `server`. Any other type gets no icon.

`StatusDot.vue` is 8 px, `border-radius: 50%`, coloured `ok` → `--status-green`, `warning` → `--status-amber`, `error` → `--status-red`, everything else → `--bs-secondary-color` grey. `ProbeStatusDots.vue:122` renders a **capped** row of these on collapsed summaries — `probes.slice(0, max || 5)`, default 5. That cap applies to the summary bubble strip only; the tree itself is uncapped.

---

## `streamValues` vs `scriptResult.services`: two different renderings

A probe that reports many things can fan out two ways, and the two land in **completely different places in the UI**. This section covers only how each *renders*. How an author picks between them — and what a `check.js` must return for either — is [Probe Plugin Format](probe-plugin-format.md).

| | `streamValues` | `scriptResult.services` |
|---|---|---|
| Where the values live | Inside one probe node's `result` | Converted server-side into `StatusNode` children of the probe |
| Conversion | None — passed through | `AgentController.java:786` `convertScriptServices()`; attached at `StatusTree.java:939` |
| Renders as | Tiles and/or a nested key/value tree **inside one expanded card row** | Real tree nodes typed `service` / `probe` |
| Depth comes from | `/` in the flat key, split by `StreamTree.vue:44` | Actual `children[]` nesting |
| Reachable by | Expanding the probe row's chevron | Expanding branch rows in the tree — **see the caveat below** |
| Gets its own `StatusDot` | No — one dot for the whole probe | Yes, one per node |
| Gets its own history series | No (paths are columns of one series) | Yes — `StatusTree.java:618` attaches state sparklines per child |
| Can carry tiles | Yes | No — a discovered node has no `layout` |

There is a third, stronger form: when a service definition resolves to exactly **one** probe and that probe reports children, `StatusTree.java:315-337` **replaces** the wrapper service node with the discovered structure — children are retyped `service`, grandchildren `probe`. In that shape the discovered nodes render normally, because they arrive as service branches.

### Caveat: a probe node's own children need their own disclosure

**Fixed 2026-08-30.** Before that date `NodeTree` dispatched on type **before** it looked at
children, and `ProbeRow` renders none, so a probe node carrying children showed nothing at all —
while the state badges counted those children, because they use a different leaf test. A badge
could report a failure that no amount of expanding would reveal.

A probe row now renders a `N sub-checks` disclosure beneath itself when the node carries children.
It is **closed by default**, so no card changed height, and the closed row names any failure
inside — `3 sub-checks · 1 failing` — because a shut row silent about a failure inside it is the
same defect wearing a chevron. The summary counts leaves rather than branches, so it reports what
is actually reachable. See `NodeTree.vue` `subSummary()` and
`__tests__/nodeTreeProbeChildren.spec.ts`.

The shape that makes this necessary, which has not changed:

```
if (node.type === 'probe')  → ProbeRow.vue            ← draws no children itself
                            + "N sub-checks" row      ← the disclosure, closed by default
                            + recursive NodeTree      ← only once opened
else                        → branch row + recursive NodeTree
```

`ProbeRow.vue` has no children rendering. So when discovered children are attached to a node that is still typed `probe` (the `StatusTree.java:939` path, as opposed to the `:315` replacement path), the subtree exists in the payload and is **not drawn**.

Measured on one real deployment, 2026-08-30 — these are the leaves that were unreachable, and are
now behind the disclosure:

| Fact | Count |
|---|---|
| Probe nodes carrying children | 15 |
| Their direct children | 67 |
| Leaves beneath a probe node, currently `ERROR` | 4 |
| Leaves beneath a probe node, currently `WARNING` | 4 |

The counts move with the board's state; the 2026-08-28 reading of this table was taken at a
different moment and recorded larger numbers. What matters is not the figure but that it is
never zero.

Examples: `HL Mirror`, `Binance Mirror`, `Bybit Mirror` — each carries 4-5 `service`-typed children (`Coverage`, `Flow`, `Integrity`, …).

The state badges and the state-filter dialog use a **different** leaf test from the tree. `countByState` (`useStatusData.ts:129`), `collectByState` (`:155`) and `filterByState` (`:174`) all recurse on *"has children"*, so they descend into a probe's children and count those leaves. `collectProbes()` (`:120`) uses the *type* test instead and stops at the probe. Until 2026-08-30 `NodeTree` used the type test too, so a badge could count a failing node that no amount of expanding would reveal. The tree now reaches them through the `N sub-checks` disclosure, so the two tests agree on what is *reachable* even though they still differ on what is a leaf.

The 3D surface does not share the limitation — `TopologyView.vue`'s `walk()` recurses on `node.children` regardless of type, so those nodes do appear in `/topology`.

---

## Card composition

`ExpandCard.vue` wraps every project and host section. Three slots: `header`, `summary` (rendered only while collapsed and not animating, `ExpandCard.vue:78`), and default body.

| Behaviour | Detail | Cite |
|---|---|---|
| Two modes | `expanded` (collapsible, chevron, hover) and `alwaysExpanded` (open, inert, no chevron) | `ExpandCard.vue:14,22` |
| Animation | 200 ms `max-height` + `opacity`; `max-height` is reset to `none` after expand so the body can grow | `ExpandCard.vue:48-51` |
| Re-entrancy guard | `animating` blocks a toggle mid-transition | `ExpandCard.vue:28` |
| Body padding | 4 px top and bottom in **both** modes | `ExpandCard.vue:122` |
| Header icon nudge | `:slotted(svg:first-child) { margin-left: -3px }` — centres a 14 px icon over the 8 px dot below it | `ExpandCard.vue:142` |

`ExpandCard.vue:111-120` records a bug worth knowing when changing card spacing: the padding rule was once conditional on `alwaysExpanded`, so expanded cards on the overview kept Bootstrap's 8 px while every internal gap was 4 px. The gallery only rendered the static mode, so nothing measured the broken one. It also warns that Bootstrap spacing utilities carry `!important` — `py-2` must be **removed from the template**, not overridden in a scoped rule.

---

## Custom SVG infographics: `svgTemplate` + bindings

An infographic replaces the tile grid entirely for a probe. It is a hand-authored SVG whose elements carry `id` attributes, plus a YAML file binding probe values to those ids.

### Files and discovery

| File | Role | Optional |
|---|---|---|
| `<probe>/infographic/template.svg` | Light-theme SVG → `CatalogEntry.svgTemplate` | required |
| `<probe>/infographic/template-dark.svg` | Dark-theme SVG → `svgTemplateDark`; null = use light | yes |
| `<probe>/infographic/bindings.yml` | Value → element bindings → `bindingsYaml` | yes |

Discovery is at `CatalogService.java:375-392` (classpath probes) and `CatalogService.java:476-486` (filesystem probes); `CatalogService.java:164-174` writes the trio back out when materialising a builtin. `CatalogEntry.java:75` defines `hasInfographic()` as `svgTemplate != null && !svgTemplate.isBlank()` — the bindings file is not part of the test, so a template with no bindings still counts and renders as a static, never-updating picture.

**Measured: 1 of 44 catalog probe types ships an infographic** — `http-endpoint`, which has `template.svg` and `bindings.yml` but no dark variant. 9 of 44 ship an `icon.svg`, which is a *different* asset (the probe's icon, not an infographic). On the live board 24 nodes report `hasInfographic` (12 in `projects`, 12 in `hosts` — the same probes surfaced in both trees).

### How a value reaches an element

```
bindings.yml            server                 InfographicCard.vue        DOM
  source: stream   ──►  resolve against   ──►  GET /api/probes/    ──►  applyPatches()
  path: responseMs      the live result        infographic?probe=…      querySelector('#id')
  targets:                                     { svg, svgDark,
    - id: response-bar                           patches[] }
      set: attr.width
```

`applyPatches()` (`utils/infographic.ts:11-20`) is 10 lines and dispatches on the `set` prefix:

| `set:` | Effect | Cite |
|---|---|---|
| `text` | `el.textContent = value` | `infographic.ts:15` |
| `class` | `el.setAttribute('class', value)` | `infographic.ts:16` |
| `attr.<name>` | `el.setAttribute(name, value)` | `infographic.ts:17` |
| `style.<prop>` | `el.style.setProperty(prop, value)` | `infographic.ts:18` |
| anything else | **Ignored, no warning** | falls off the chain |
| id not found | `continue` — **ignored, no warning** | `infographic.ts:14` |

Three transforms apply, checked in order `scale` → `threshold` → `map`; the first one present wins and the others are never consulted (`infographic.ts:210-239`):

| Transform | Shape | Semantics |
|---|---|---|
| `scale` | `{min, max, output: "0,360"}` | Linear map, **clamped to 0..1** before scaling; output rounded to an integer |
| `threshold` | `{1000: "#f44336", 500: "#ff9800", default: "#4caf50"}` | Numeric keys sorted **descending**; first `num >= key` wins; non-numeric input → `default` |
| `map` | `{OK: "#4caf50", …}` | Exact lookup on the **raw** value; miss → the formatted value |

Sources are `stream` (needs `path`) and `state`; anything else resolves to `null` and the binding is skipped (`infographic.ts:159-167`). Formats are `number`, `bytes` (binary 1024, unlike `format.ts`'s decimal 1e3), `percent`, `duration`.

Theme selection is client-side and reactive: `pickSvg()` prefers `svgDark` when `prefers-color-scheme: dark` matches, and a `matchMedia` change listener re-renders and re-patches (`InfographicCard.vue:25-28,56-64`). Where no dark template exists, the light SVG is expected to carry its own `@media (prefers-color-scheme: dark)` block — `http-endpoint/infographic/template.svg` does exactly that.

The SVG is injected with `v-html` (`InfographicCard.vue:79`), so template content is trusted server-side content by construction.

Live updates arrive by SSE: `onServerEvent('probe', refresh)` refetches and re-patches (`InfographicCard.vue:68`). Both `load()` and `refresh()` swallow errors silently.

**Note the parser split.** `resolveLocalPatches()` in `utils/infographic.ts:26` is the IDE preview path only, and it uses `parseBindingsSimple()` — a line-by-line state machine keyed on **exact indentation** (`/^  - source:/`, `/^    path:/`, `/^      - id:/`, `/^        set:/`). Bindings that are valid YAML but differently indented parse to nothing in the preview while working correctly on the server, which resolves bindings itself. `infographic.ts:48` catches and discards every parse error "silently — user may be mid-edit".

---

## The three rules that decide whether a tile appears at all

All three fail as an **empty cell**: `TileGrid.vue` always renders `.tile-cell` and its label, and only the `<slot>` body comes up blank. Nothing is logged, nothing is thrown, and the layout does not reflow.

### Rule 1: unknown widget name

`ProbeLayout.vue:185-225` is a `v-if` / `v-else-if` chain with no `v-else`. A `widget:` value outside the 10 known 2D kinds matches nothing and the tile body is empty.

The 3D side behaves **differently**: `TopologyView.vue:1314-1316` looks up `WIDGET_BUILDERS[s.widget || 'value']` and, when the lookup misses, calls `WIDGET_BUILDERS.value(…)`. An unknown kind therefore renders as a **value plaque** on the plate. The same typo is invisible on a card and looks like a working value widget in topology.

> `if (widget is not one of the 10 2D kinds) then (2D cell is empty) and (3D renders a value plaque)`

### Rule 2: a path the probe never emitted

Every 2D widget branch is additionally guarded on its binding: `tile.path != null` for single-path widgets, `tile.resolvedPaths` for glob widgets. Those guards pass for a path that is *declared* but never *emitted* — `getValue()` returns `''` (`ProbeLayout.vue:32`), `formatValue()` returns `''` on a falsy raw (`ProbeLayout.vue:52`), and the widget renders with an empty string.

For a glob, `matchPaths()` (`ProbeLayout.vue:112`) filters `Object.keys(streamValues)`; zero matches yields `[]`, which is truthy, so `BarsWidget` / `ListWidget` / `GridWidget` mount with an empty `items` array and draw nothing.

On the 3D side `resolveSlotValue()` returns `{ num: null, state: 'UNKNOWN' }` (`slot-value.ts:28`) and the builder draws its empty form.

> `if (streamValues has no key equal to tile.path) then (the widget mounts and renders blank — no error, no missing-tile)`

### Rule 3: the empty primary path `''`

`path: ""` is a **real key**, not "unset". It is the probe's primary series and is used deliberately — `system-disk/probe.yml` binds both its gauge and its chart to `path: ""`.

Three different consumers read it, and they read *different* maps:

| Consumer | Reads | Cite |
|---|---|---|
| Inline row sparkline | `result.sparklines['']` | `ProbeRow.vue:34` |
| Tile `widget: chart` with `path: ""` | `sparklines[''][mode]`, needs ≥ 2 points | `ProbeLayout.vue:36` |
| Tile `widget: gauge`/`value`/`bar` with `path: ""` | `streamValues['']` | `ProbeLayout.vue:32` |

So a probe that emits a `''` sparkline but no `''` streamValue gets a working row sparkline and a working chart tile, and a **blank** gauge tile — from one and the same `path: ""`.

Measured on one real deployment: 137 probes carry sparklines, **97** of them carry the `''` key, but only **19** carry `''` in `streamValues`. 36 tiles bind `path: ""`, and 0 of them are currently on a probe missing the key — the trap is live-adjacent, not currently firing.

`StreamTree.vue:66` explicitly skips the `''` key (`if (key === '') continue`), so a primary value that no tile claims does **not** appear in the key/value fallback either. It is reachable only through a tile or the row sparkline.

**Boundary.** This document owns what `''` *renders as*: the inline 32×20 sparkline on the probe row (`ProbeRow.vue:34`), a `chart` tile, or a `gauge`/`value`/`bar` tile — and the fact that `StreamTree` hides it. The storage convention behind the key — why `''` exists, what the server writes into it, and how it is retained — is the server's data model.

> `if (tile.path === '' and the probe emits no '' key in the map that widget reads) then (empty cell, and the value appears nowhere else in the UI)`

### Not a failure: `group:` tiles are skipped on purpose

`ProbeLayout.vue:172-173` filters `layout` to `!t.group` before building the grid. A tile carrying `group:` is **meant** to be absent from the tile grid: it renders once per matching instance inside `StreamTree`, which receives the full `layout` for exactly that purpose (`ProbeRow.vue:143`). `lifx` uses this for per-light tiles. An authored `group:` tile that never appears anywhere means the group pattern matched no instance, not that the tile is broken.

---

## Fails silently

| Symptom | Cause | Fix |
|---|---|---|
| Labelled tile, empty body, on a 2D card | `widget:` is not one of the 10 kinds `ProbeLayout.vue` handles (e.g. `action`, `tray`, `progress-circle`, or a typo like `slider`) | Use a 2D-capable kind, or accept that the tile is topology-only. Check the widget table above. |
| The same tile looks fine in `/topology` | 3D substitutes the `value` builder for any unknown kind (`TopologyView.vue:1315`) | Never validate a widget name against the 3D plate; validate against the 2D card. |
| Tile renders but the value is blank | `tile.path` is declared but the probe never emitted that key. `getValue()` → `''` → `formatValue()` → `''` | Compare `layout[].path` against the live `result.streamValues` keys. Expand the row: `StreamTree` shows exactly the paths the probe *does* emit. |
| `bars` / `list` / `grid` / `multizone` / `heatmap` tile is empty | Glob matched zero paths. `matchPaths()` returns `[]`, which is truthy, so the widget mounts empty | `paths:` uses `*` → `[^/]+` (one segment, no slashes) and is anchored `^…$`. A `*` will not cross a `/`. |
| Gauge with `path: ""` is blank while the row sparkline works | The probe emits `sparklines['']` but not `streamValues['']` — different maps | Emit a primary streamValue, or bind the tile to `widget: chart`, which reads sparklines. |
| Chart tile blank, other tiles fine | `getSparkline()` requires `pts.length >= 2`; a single point returns `null` | Wait for a second sample, or check the 1d/7d mode toggle — a 7d series can be empty on a young probe. |
| Value renders as a run of ungrouped digits, or a percent reads `9986%` | A **second copy** of the formatter was introduced. This exact regression is recorded at `ProbeLayout.vue:41-49` | Always call `formatWidgetValue()` from `lib/plate/utils/format.ts`. Never re-implement it. |
| A `gauge` shows `%` on a non-percent value | `format.ts:90` forces the percent branch for `widget === 'gauge'`, whatever the output type says | Use `bar` or `value` for a non-ratio metric. |
| Tile wider than the panel is silently narrower | `TileGrid.vue:35` clamps `colSpan` to 4 | Use a canonical size from `tiles.ts`. `4x3` works but is not in the picker. |
| Same layout looks right in 3D, cramped in 2D | `flowLayout()` has no clamp — a 6-wide slot renders 6 wide on the plate and 4 wide on the card | Author to 4 columns. |
| Infographic never updates | `bindings.yml` missing entirely, or a `set:` value outside `text` / `class` / `attr.*` / `style.*`, or an `id` not present in the SVG | Patches with unknown ids `continue` without warning (`infographic.ts:14`). Check the id spelling against the SVG. |
| Infographic works live but is dead in the IDE preview | The IDE uses `parseBindingsSimple()`, whose regexes require **exact** indentation (2/4/6/8 spaces) | Match the indentation in `http-endpoint/infographic/bindings.yml` exactly. |
| Tiles vanished when an infographic was added | `ProbeRow.vue:92-100` — the infographic **pre-empts** the tile grid | Remove the infographic or accept it as the probe's sole expanded view. |
| An authored tile appears nowhere | It carries `group:` and no instance matched the pattern | This is by design (`ProbeLayout.vue:172`); the tile lives inside `StreamTree`. Verify the group pattern against emitted paths. |
| A widget added to `registry.ts` does not render inside a `tray` | `builders/tray.ts:20` dispatches through the **legacy** `builders/index.ts` map, not `registry.ts` | Add the builder to both maps until the legacy map is retired. |
| A probe's discovered sub-nodes are in `/api/status` but not on the board | **Fixed 2026-08-30.** `NodeTree.vue` dispatched on `type === 'probe'` before checking children, and `ProbeRow.vue` renders none | Open the `N sub-checks` disclosure under the probe row. On a build older than 2026-08-30, retype the wrapper so the `StatusTree.java:315` replacement path applies, or view it in `/topology`, which recurses regardless of type. |
| An ERROR badge counts a node that cannot be found by expanding | **Fixed 2026-08-30.** `NodeTree` dispatched on type while `countByState`/`filterByState` recurse on "has children", so leaves under a probe node were counted and undrawable | Open the `N sub-checks` disclosure under the probe row. On a build older than 2026-08-30, cross-check in `/topology` or query `/api/status` directly |
| Board stops updating, no error visible | `useStatusData.load()` swallows every fetch error and keeps the previous tree (`useStatusData.ts:216`) | Check the network tab. A stale board looks identical to a healthy one. |
| Tree expansion resets | Expansion state is a component-local `reactive({})` (`NodeTree.vue:44`) and is not persisted | Expected. There is no persistence layer for tree state. |

---

## Machine-readable widget table

```yaml
# Status-Frontend widget matrix. verified: 2026-08-28
# registry: Status-Frontend/src/lib/plate/widgets/registry.ts  (34 entries + `plate` alias)
# 2d      : Status-Frontend/src/components/common/ProbeLayout.vue:185-225  (10 kinds)
# required: schema keys the builder needs; `path` = single key, `paths` = glob (`*` -> [^/]+)
# unknown widget name -> 2D: empty cell (no v-else) ; 3D: falls back to `value` (TopologyView.vue:1315)
widgets:
  - {name: value,              required: [path],          two_d: true,  three_d: true,  notes: "default readout; also the 3D fallback for unknown kinds"}
  - {name: gauge,              required: [path],          two_d: true,  three_d: true,  notes: "270deg arc; format.ts:90 forces a % suffix regardless of output type"}
  - {name: bar,                required: [path],          two_d: true,  three_d: true,  notes: "3D bar re-exports the bars builder"}
  - {name: bars,               required: [paths],         two_d: true,  three_d: true,  notes: "glob only; zero matches renders empty, not missing"}
  - {name: chart,              required: [path],          two_d: true,  three_d: true,  notes: "reads sparklines[path], NOT streamValues; needs >=2 points"}
  - {name: badge,              required: [path],          two_d: false, three_d: true,  notes: "pill/shield/hex for short enums"}
  - {name: log,                required: [],              two_d: false, three_d: true,  notes: "reads scriptResult; no path"}
  - {name: text,               required: [path],          two_d: false, three_d: true,  notes: ""}
  - {name: fluid-tank,         required: [path],          two_d: false, three_d: true,  notes: "drop-in for gauge/bar; `fluid` selects the liquid"}
  - {name: thermometer,        required: [path],          two_d: false, three_d: true,  notes: ""}
  - {name: compass,            required: [path],          two_d: false, three_d: true,  notes: "value = bearing 0..360"}
  - {name: radar,              required: [path],          two_d: false, three_d: true,  notes: "reads sparklines"}
  - {name: orbital,            required: [path],          two_d: false, three_d: true,  notes: "orbit count = value"}
  - {name: flame,              required: [path],          two_d: false, three_d: true,  notes: "plume height ~ value"}
  - {name: cake,               required: [path],          two_d: false, three_d: true,  notes: "candles = value"}
  - {name: hourglass,          required: [path],          two_d: false, three_d: true,  notes: ""}
  - {name: paper-stack,        required: [path],          two_d: false, three_d: true,  notes: "reads scriptResult.files; growth/paper-thick/fade-start/fade-end"}
  - {name: heatmap,            required: [paths],         two_d: false, three_d: true,  notes: "glob; colour = state, brightness = value"}
  - {name: odometer,           required: [path],          two_d: false, three_d: true,  notes: ""}
  - {name: split-flap,         required: [path],          two_d: false, three_d: true,  notes: "string enums; animates on change"}
  - {name: delta,              required: [path],          two_d: false, three_d: true,  notes: "reads sparklines for the % change"}
  - {name: uptime-strip,       required: [path],          two_d: false, three_d: true,  notes: "TOPOLOGY-ONLY. reads sparklines. default ramp higher=worse; `reverse: true` inverts"}
  - {name: progress-circle,    required: [path],          two_d: false, three_d: true,  notes: "mode: spinner|progress-fill|heartbeat; spinner/heartbeat need no value"}
  - {name: node,               required: [style],         two_d: false, three_d: true,  notes: "TOPOLOGY-ONLY. embeds a referenced graph node's mesh"}
  - {name: action,             required: [path, style],   two_d: false, three_d: true,  notes: "style: button|switch|knob|slider|lever; 13 catalog uses, all invisible on a 2D card"}
  - {name: tray,               required: [],              two_d: false, three_d: true,  notes: "nested slots[]; cols/rows set the inner grid; dispatches via the LEGACY builders/index.ts map"}
  - {name: plate,              required: [],              two_d: false, three_d: true,  notes: "alias of tray (registry.ts:188); excluded from WIDGET_NAMES"}
  - {name: chart-billboard,    required: [path],          two_d: false, three_d: true,  notes: "flat|tilted|upright screen; height"}
  - {name: oscilloscope,       required: [path],          two_d: false, three_d: true,  notes: "reads sparklines"}
  - {name: vu-meter,           required: [path],          two_d: false, three_d: true,  notes: "height"}
  - {name: matrix-rain,        required: [path],          two_d: false, three_d: true,  notes: "density ~ value; height"}
  - {name: ticker-tape,        required: [],              two_d: false, three_d: true,  notes: "reads scriptResult"}
  - {name: stacked-bars-tower, required: [path],          two_d: false, three_d: true,  notes: "height"}
  - {name: split-flap-board,   required: [],              two_d: false, three_d: true,  notes: "reads scriptResult; height"}
  - {name: state-dot,          required: [],              two_d: false, three_d: true,  notes: "builder exists; EXCLUDED from the picker; empty schema, placeholder icon"}
  - {name: color,              required: [path],          two_d: true,  three_d: false, notes: "2D-only swatch of a parsed colour string"}
  - {name: list,               required: [paths],         two_d: true,  three_d: false, notes: "2D-only; UNUSED in the catalog"}
  - {name: grid,               required: [paths],         two_d: true,  three_d: false, notes: "2D-only; UNUSED in the catalog"}
  - {name: multizone,          required: [paths],         two_d: true,  three_d: false, notes: "2D-only; zone-sorted colour strip (lifx)"}
  - {name: image,              required: [path],          two_d: true,  three_d: false, notes: "2D-only; mode flips to mjpeg on output type `mjpeg`"}

# used in the catalog but present in NEITHER registry -> render nowhere
unimplemented_in_catalog: [slider, hue-slider, kelvin-slider, color-picker]  # lifx/probe.yml:91-136

tiles:
  panel_columns: 4                      # TileGrid.vue:21, MAX_COLUMNS
  col_span_clamped: true                # TileGrid.vue:35
  row_span_clamped: false               # TileGrid.vue:36
  malformed_tile_degrades_to: "1x1"     # TileGrid.vue:29,35
  row_height_px: 80                     # TileGrid.vue:65
  gap_px: 8                             # TileGrid.vue:66
  canonical: [1x1, 2x1, 1x2, 2x2, 3x1, 3x2, 4x1, 4x2]   # tiles.ts:8
  catalog_also_uses: [4x3]              # webcam/probe.yml:38,42 - renders, not in the picker
  plate_units:                          # utils/flow.ts
    default_width: 4
    default_gap: 0.12
    default_padding: 0.3
    world_scale: 40                     # PLATE_UNIT
    clamps_width: false                 # a 6-wide slot renders 6 wide in 3D

measured_2026_08_28:
  catalog_probe_types: 44
  catalog_types_with_layout: 11
  catalog_types_with_infographic: 1     # http-endpoint
  catalog_types_with_icon_svg: 9        # a DIFFERENT asset from an infographic
  live_nodes_total: 1324
  live_probe_nodes: 951
  live_probes_with_layout: 59           # 6.2% - the row fallback is the majority path
  live_branches_with_children: 397
  live_branches_with_exactly_one_child: 102
  live_max_depth: 5                     # projects tree; hosts tree is 4
  live_tree_depth_cap: none
  live_tree_row_cap: none
  live_probes_with_sparklines: 137
  live_probes_with_empty_key_sparkline: 97
  live_probes_with_empty_key_streamvalue: 19
  # probe nodes that carry children: NodeTree.vue:53 dispatches on type before
  # checking children, so ProbeRow renders and the subtree is never drawn.
  live_probe_nodes_with_children: 34
  live_direct_children_of_probe_nodes: 188
  live_leaves_under_probe_nodes: 8_non_ok_of_67_direct_children   # reachable since 2026-08-30
  live_hidden_leaves_error: 8
  live_hidden_leaves_warning: 16

fanout_rendering:
  streamValues:
    renders_in: "one probe card - tiles and/or a nested StreamTree"
    depth_from: "'/' in the flat key (StreamTree.vue:44)"
    own_status_dot: false
    own_history_series: false
    can_carry_tiles: true
  scriptResult_services:
    converted_by: "AgentController.java:786 convertScriptServices()"
    attached_by: "StatusTree.java:939"
    replacement_path: "StatusTree.java:315-337 - a lone probe under a service definition REPLACES the wrapper; children retyped `service`, grandchildren `probe`"
    renders_in: "real tree nodes"
    own_status_dot: true
    own_history_series: true      # StatusTree.java:618 attaches state sparklines
    can_carry_tiles: false
    caveat: "children left on a `probe`-typed node are NOT rendered by NodeTree; /topology does render them"
  # authoring choice between the two: see Status-Server/docs/probe-plugin-format.md

leaf_test_inconsistency:
  nodetree_render:  "node.type === 'probe'"        # NodeTree.vue:53
  collect_probes:   "node.type === 'probe'"        # useStatusData.ts:120  - agrees
  count_by_state:   "children.length > 0"          # useStatusData.ts:129  - DISAGREES
  collect_by_state: "children.length > 0"          # useStatusData.ts:155  - DISAGREES
  filter_by_state:  "children.length > 0"          # useStatusData.ts:174  - DISAGREES
  effect: "badges and the tree use different leaf tests; both reach the same leaves since 2026-08-30"
```
