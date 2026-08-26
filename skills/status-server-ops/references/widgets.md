# Dashboard widgets — the full registry

A probe's `layout:` block renders its stream paths as a grid of tiles. Each tile names a
`widget`. This is the complete registry as shipped.

> ⚠️ `writing-probes.md` → *Dashboard layout (tiles)* says the built-ins are `value`, `gauge`,
> `color` and `multizone`. **That list is stale** — there are 33 picker widgets plus two
> internal ones. Use this file for the vocabulary and that one for how `layout:` works.

## Tile shape

```yaml
layout:
  - tile: 2x1              # grid span: <cols>x<rows>
    widget: chart          # renderer, from the tables below
    path: responseMs       # one stream path (may contain {var})
    label: Response Time
    group: "{host}"        # bind to a {var} expansion — omit for root-level summary tiles
```

Spans in use across the shipped catalog: `1x1` (most common), `1x2`, `2x1`, `2x2`, `3x1`,
`3x2`, `4x1`, `4x3`. Tiles whose `path` was never emitted are **skipped silently**, which is
what lets one layout serve heterogeneous instances.

`path` takes a single stream path; `paths` takes a glob selecting many (`bars`, `heatmap`).

## The registry, by category

Categories are the picker's grouping in the plate editor.

### Numeric
| widget | fields |
|---|---|
| `value` | `path` — formatted text, the default |
| `odometer` | `path` — mechanical rolling digits |
| `split-flap` | `path` — single flip-board cell |
| `split-flap-board` | `height` — multi-row flip board |
| `delta` | `path` — change against the previous sample |

### Gauges & meters
| widget | fields |
|---|---|
| `gauge` | `path` — 0..max dial |
| `bar` | `path` |
| `bars` | `paths`, `style` (`blocks`, `cylinders`), `height` |
| `progress-circle` | `path`, `mode` (`spinner`, `chase`, `progress-fill`, `countdown`, `heartbeat`), `segments`, `speed`, `trail-length` |
| `fluid-tank` | `path`, `fluid` (`water`, `lava`, `mercury`, `oil`) |
| `thermometer` | `path` |
| `vu-meter` | `path`, `height` |
| `stacked-bars-tower` | `path`, `height` |

### Charts
| widget | fields |
|---|---|
| `chart` | `path`, `style` (`blocky`, `smooth`, `ridge`) |
| `chart-billboard` | `path`, `height` |
| `oscilloscope` | `path` |
| `heatmap` | `paths` |
| `radar` | `path` |

### Status
| widget | fields |
|---|---|
| `badge` | `path`, `shape` (`pill`, `hex`, `shield`, `stamp`) |
| `uptime-strip` | `path`, `reverse` |
| `flame` | `path` |

### Text
| widget | fields |
|---|---|
| `text` | `path` |
| `log` | — (reads a tree-attached log ref) |
| `ticker-tape` | — |
| `matrix-rain` | `path`, `height` |

### Spatial
| widget | fields |
|---|---|
| `compass` | `path` |
| `orbital` | `path` |
| `hourglass` | `path` |
| `cake` | `path` |
| `paper-stack` | `path`, `growth`, `paper-thick`, `fade-start`, `fade-end` |

### Grouping
| widget | fields |
|---|---|
| `tray` | — (container; `plate` is a legacy alias) |
| `node` | `style` (`disc`, `hex`, `square`, `orb`, `spike`) |
| `action` | `path`, `style` (`button`, `switch`, `knob`, `slider`, `lever`, `slot-machine`, `slot-machine-tall`, `slot-machine-mini`), `name` |

### Not in the picker
`state-dot` and `plate` exist for builder lookup only — they are deliberately excluded from
the picker chips. Some catalog probes also use `color`, `multizone`, `image` and `slider`
tiles, which are rendered by dedicated frontend components rather than plate builders.

## Choosing one

`value` and `chart` cover most real monitoring needs, and a probe row already shows an
inline sparkline from the primary (`''`) stream path. The decorative widgets — `matrix-rain`,
`flame`, `cake`, `orbital` — exist for wall-display boards. On an operational dashboard,
prefer the one that makes a bad number obvious at a glance: `gauge` or `progress-circle` for
a bounded ratio, `uptime-strip` for a pass/fail history, `badge` for a discrete state.
