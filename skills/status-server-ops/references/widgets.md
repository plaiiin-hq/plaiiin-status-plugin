# Widgets — which ones actually render, and where

A probe's `layout:` block renders its stream paths as a grid of tiles, each naming a `widget`.

> 🚨 **Read this first. There are two renderers, fed by the same `layout:` block, and they
> accept different widget names.** A widget the probe card doesn't know renders **nothing** —
> silently. `ProbeLayout.vue` ends its dispatch chain with no fallback, so a tile naming
> `flame` or `odometer` produces an empty cell: no error, no warning, no log line.

| | Probe card — the board people look at | 3D topology view |
|---|---|---|
| Widget count | **10** | 33 |
| Use it for | Everyday monitoring | The topology/plate visualisation |

## The safe set — works in both (5)

`value` · `gauge` · `chart` · `bar` · `bars`

**Default to these.** Unless you specifically need something below, staying inside this set
means your tiles render everywhere.

| widget | fields | good for |
|---|---|---|
| `value` | `path` | Any single number or string. The workhorse. |
| `gauge` | `path`, `max` | A bounded ratio — disk %, memory %, queue depth against a cap. |
| `chart` | `path`, `style` (`blocky`, `smooth`, `ridge`) | Anything where the trend matters more than the current value — latency above all. |
| `bar` | `path` | One magnitude, compared against its own max. |
| `bars` | `paths`, `style` (`blocks`, `cylinders`), `height` | Several comparable magnitudes side by side — per-core CPU, per-disk usage. |

## Probe card only (5)

`color` · `grid` · `image` · `list` · `multizone`

These render on the board but **not** in the topology view. `image` also handles `mjpeg` when
the output type says so — that is how a camera probe shows a live frame. `multizone` draws a
segmented colour strip; `list` and `grid` take `paths` globs.

## Topology view only (28)

`action` `badge` `cake` `chart-billboard` `compass` `delta` `flame` `fluid-tank` `heatmap`
`hourglass` `log` `matrix-rain` `node` `odometer` `orbital` `oscilloscope` `paper-stack`
`progress-circle` `radar` `split-flap` `split-flap-board` `stacked-bars-tower` `text`
`thermometer` `ticker-tape` `tray` `uptime-strip` `vu-meter`

**Every one of these renders as an empty cell on a probe card.** They are for the plate/
topology visualisation — a wall display or an architecture view, not an operational board.

Their fields, for when you are authoring a plate:

| widget | fields |
|---|---|
| `badge` | `path`, `shape` (`pill`, `hex`, `shield`, `stamp`) |
| `progress-circle` | `path`, `mode` (`spinner`, `chase`, `progress-fill`, `countdown`, `heartbeat`), `segments`, `speed`, `trail-length` |
| `fluid-tank` | `path`, `fluid` (`water`, `lava`, `mercury`, `oil`) |
| `action` | `path`, `style` (`button`, `switch`, `knob`, `slider`, `lever`, `slot-machine`, `slot-machine-tall`, `slot-machine-mini`), `name` |
| `node` | `style` (`disc`, `hex`, `square`, `orb`, `spike`) |
| `paper-stack` | `path`, `growth`, `paper-thick`, `fade-start`, `fade-end` |
| `uptime-strip` | `path`, `reverse` |
| `chart-billboard` · `matrix-rain` · `stacked-bars-tower` · `vu-meter` | `path`, `height` |
| `split-flap-board` | `height` |
| `heatmap` | `paths` |
| everything else | `path` |

`state-dot` has a builder but is deliberately excluded from the picker; `plate` is a legacy
alias of `tray`.

## Tiles

```yaml
layout:
  - tile: 2x1              # <cols>x<rows>
    widget: chart
    path: responseMs
    label: Response Time
    group: "{host}"        # bind to a {var} expansion; omit for root-level summary tiles
```

**The panel is 4 units wide.** A span wider than that is clamped. Canonical sizes:
`1x1` `2x1` `1x2` `2x2` `3x1` `3x2` `4x1` `4x2`; the shipped catalog also uses `4x3`.

Three rules decide whether a tile appears at all:

| Rule | Consequence |
|---|---|
| The `widget` must be known to the renderer you are looking at | Otherwise **empty cell, silently** — the trap above |
| `path` must be a path the probe actually emits in `streamValues` | A tile whose path was never emitted is **skipped silently** |
| The `''` (empty) path is the **primary** value | Drives the inline sparkline on the probe row; omit it and the row renders flat |

## Choosing one

For an operational board, pick the widget that makes a bad number obvious at a glance:
`gauge` for a bounded ratio, `chart` for anything where the trend is the story, `value` when
the number speaks for itself. Note that `uptime-strip` — the obvious choice for pass/fail
history — is **topology-only**, so on a card use `chart` of a 0/1 stream instead.

Only 11 of ~45 shipped probes define a `layout:` at all; the other 34 render as plain
key/value rows, which is a perfectly good default. Add a layout when a probe emits enough
values that rows stop being readable.
