# Infographics — custom probe cards from plain SVG

An **infographic** is a hand-drawn SVG card for a probe, with live values bound into it. It is
the most direct way to make a probe look like a designed instrument rather than a row of
numbers — and it needs no frontend build, no widget registry, and no rebuild of anything.

It is also almost entirely unused: of ~45 shipped probes, **1** has one. If you want a board
that looks deliberate, this is the surface with the most headroom.

## The two files

```
probes/<id>/infographic/
  template.svg     the drawing, with id="…" on the parts that change
  bindings.yml     which probe values drive which ids
```

## `template.svg`

An ordinary SVG. Put an `id` on anything that should change at runtime, and drive theming from
a `<style>` block:

```svg
<svg viewBox="0 0 400 120" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg        { fill: #f5f5f7; }
    .bar-track { fill: #e0e0e0; }
    .label     { fill: #999; }
    text       { font-family: system-ui, -apple-system, sans-serif; fill: #222; }

    @media (prefers-color-scheme: dark) {
      .bg        { fill: #1c1c1c; }
      .bar-track { fill: #2b2b2b; }
      .label     { fill: #888; }
      text       { fill: #e0e0e0; }
    }
  </style>

  <rect class="bg" width="400" height="120" rx="8"/>

  <circle id="status-dot" cx="24" cy="24" r="8" fill="#666"/>
  <text   id="status-label" x="40" y="29" font-size="14" font-weight="600">--</text>

  <text class="label" x="20" y="58" font-size="10">Response Time</text>
  <text id="response-time" x="20" y="78" font-size="22" font-weight="700">--</text>

  <rect class="bar-track" x="20" y="88" width="360" height="6" rx="3"/>
  <rect id="response-bar" x="20" y="88" width="0" height="6" rx="3" fill="#4caf50"/>
</svg>
```

Two things worth copying from that: give every dynamic element a **placeholder** (`--`, width
`0`) so the card looks intentional before the first result arrives, and support both themes
via `prefers-color-scheme`. Keep dark backgrounds **neutral** unless you mean the tint — a
blue-grey reads as "unfinished" next to the rest of the UI.

## `bindings.yml`

Each binding takes a **source**, and a list of **targets** naming an element id and what to
set on it.

```yaml
bindings:
  - source: state                       # the probe's overall state
    targets:
      - id: status-dot
        set: attr.fill
        map: {OK: "#4caf50", WARNING: "#ff9800", ERROR: "#f44336", UNKNOWN: "#666"}
      - id: status-label
        set: text

  - source: stream                      # one of the probe's streamValues paths
    path: responseMs
    format: number
    targets:
      - id: response-time
        set: text

      - id: response-bar                # ← drive a bar's WIDTH from a value
        set: attr.width
        scale: {min: 0, max: 2000, output: "0,360"}

      - id: response-bar                # ← and its COLOUR from thresholds
        set: attr.fill
        threshold:
          1000: "#f44336"
          500:  "#ff9800"
          default: "#4caf50"
```

### The whole vocabulary

| Key | Does |
|---|---|
| `source: state` | The probe's overall state (`OK`/`WARNING`/`ERROR`/`UNKNOWN`) |
| `source: stream` + `path:` | One `streamValues` path from `check.js` |
| `format: number` | Formatting applied before `set: text` |
| `set: text` | Replaces the element's text content |
| `set: attr.<name>` | Sets any SVG attribute — `width`, `fill`, `height`, `x`, `opacity`, `transform` … |
| `map: {…}` | Discrete value → output. For states and enums. |
| `scale: {min, max, output: "a,b"}` | Linear map from a value range onto an output range |
| `threshold: {n: v, …, default: v}` | Value → output by descending cutoff |

That is the entire language. `set: attr.*` plus `scale` is enough for bars, arcs, fills,
needles and anything else geometric — you are setting SVG attributes, so whatever SVG can
express, a binding can drive.

## Ideas this makes cheap

| | |
|---|---|
| Horizontal / vertical bar | `set: attr.width` (or `height`) with `scale` |
| Colour by severity | `set: attr.fill` with `threshold` |
| A needle or arc | `set: attr.transform` with `scale` mapping to a rotation range |
| Fill level | `scale` onto a rect's `y` **and** `height` together |
| Show/hide a warning glyph | `set: attr.opacity` with `map` |

## Getting it onto the server

| Route | How |
|---|---|
| **API** | `GET /api/ide/probe-svg?id=<probe>` to read, `POST /api/ide/probe-svg` with `{id, svg, svgDark}` to write. Live immediately, no redeploy. |
| **Probe IDE** | Edit alongside `probe.yml` and `check.js`. |

Both need `STATUS_ADMIN` or `INFRA_ADMIN`.

## When to use this instead of a layout

| Want | Use |
|---|---|
| A grid of standard readouts | `layout:` with the card-safe widgets |
| One value, many instances | `layout:` with `{var}` + `group:` |
| A designed, single-purpose card | **infographic** |
| Something the widget set simply cannot draw | **infographic** |

An infographic renders the probe as one composed picture; a layout renders it as tiles. They
answer different questions, and a probe can perfectly well have both.
