# Writing Custom Probes

A probe is a folder with two files:

```
probes/
  my-probe/
    probe.yml    — manifest (id, name, description, params)
    check.js     — the probe script
```

Drop it into the server's `config-path/probes/` folder and it's live — agents sync within seconds.

## Step 1: Create probe.yml

```yaml
id: redis-check
name: Redis Health
description: Check Redis is accepting connections and responding to PING
updated: 2026-04-06
icon: database

changelog:
  - date: 2026-04-06
    note: Initial release

params:
  - name: host
    type: hostname
    required: true
    description: Redis host

  - name: port
    type: port
    default: 6379
    configurable: true
    description: Redis port
```

### Parameter modes

| Mode | YAML | Meaning |
|------|------|---------|
| Required | `required: true` | User must provide a value |
| Configurable | `configurable: true` + `default: ...` | Has a default, user can override |
| Fixed | `fixed: true` + `default: ...` | Shown in UI but not editable |

### Parameter types

Use semantic types — they enable host/endpoint tracking and UI behavior:

- `hostname` — a host the probe connects to
- `port` — a network port
- `url` — a full URL
- `string` — generic text
- `int` — a number
- `map` — key-value pairs
- `credential` — reference to a credential from the credentials store (see below)

### Credential parameters

For probes that need authentication, use `type: credential` with `credential_type` to restrict which credential types are shown in the UI:

```yaml
params:
  - name: credentials
    type: credential
    credential_type: bearer        # only Bearer credentials shown in picker
    configurable: true
    description: API token for authentication
```

Supported `credential_type` values: `bearer`, `basic`, `header`, `oauth2`, `tls`, `ssh`.

When the user configures the probe, the UI shows a filtered dropdown of matching credentials from the credentials store. If no matching credential exists, a link to "Create one" takes them to Settings > Credentials with the type pre-selected.

In the probe script, the resolved credential data is available as `ctx.params.credentials`:

```js
// Bearer credential → { token: "eyJh..." }
if (ctx.params.credentials) {
  headers['Authorization'] = 'Bearer ' + ctx.params.credentials.token
}

// Basic credential → { username: "admin", password: "secret" }
if (ctx.params.credentials) {
  var encoded = btoa(ctx.params.credentials.username + ':' + ctx.params.credentials.password)
  headers['Authorization'] = 'Basic ' + encoded
}

// Header credential → { headerName: "X-API-Key", headerValue: "abc123" }
if (ctx.params.credentials) {
  headers[ctx.params.credentials.headerName] = ctx.params.credentials.headerValue
}
```

Credentials are encrypted at rest (AES-256-GCM), delivered to agents via signed request, cached in memory only (5-min TTL), never written to disk. See [credentials-store.md](credentials-store.md) for details.

## Step 2: Write check.js

The script must define a `check(ctx)` function:

```js
function check(ctx) {
  // Use sandbox APIs via ctx
  const res = ctx.tcp.connect(ctx.params.host, ctx.params.port || 6379)

  if (!res.ok) {
    return { state: 'ERROR', message: res.message, responseMs: res.elapsed }
  }

  return {
    state: 'OK',
    message: 'Redis responding',
    responseMs: res.elapsed,
    streamValues: {
      responseMs: { state: 'OK', value: '' + res.elapsed }
    }
  }
}
```

### Available APIs

| API | What it does | Example |
|-----|-------------|---------|
| `ctx.http.get(url)` | HTTP GET | `ctx.http.get('http://host/health')` |
| `ctx.http.post(url, body)` | HTTP POST | `ctx.http.post(url, '{}', headers)` |
| `ctx.tcp.connect(host, port)` | TCP port check | `ctx.tcp.connect('db', 5432)` |
| `ctx.udp.send(host, port, data)` | UDP send/receive | `ctx.udp.send('dns', 53, 'ping')` |
| `ctx.socket.send(path, data)` | Unix socket raw | `ctx.socket.send('/var/run/redis.sock', 'PING\r\n')` |
| `ctx.socket.http(path, uri)` | Unix socket HTTP | `ctx.socket.http('/var/run/docker.sock', '/containers/json')` |
| `ctx.shell.run(command)` | Shell command | `ctx.shell.run('redis-cli ping')` |
| `ctx.host.cpu()` | Host CPU metrics | `ctx.host.cpu().get('utilizationPercent')` |
| `ctx.host.memory()` | Host memory metrics | `ctx.host.memory().get('usedPercent')` |
| `ctx.host.disks()` | Host disk metrics | `ctx.host.disks()[0].get('usedPercent')` |
| `ctx.host.uptime()` | Host uptime | `ctx.host.uptime().get('seconds')` |
| `ctx.log.push(path, lines)` | Attach log lines to a tree path | `ctx.log.push('keycloak', [line1, line2])` |
| `ctx.log.ref(path, uri)` | Point a tree path at an external log source | `ctx.log.ref('keycloak', 'docker://keycloak-1')` |
| `ctx.log.log(msg)` | Debug line (streamed to action dialog) | `ctx.log.log('starting scan')` |
| `ctx.action.add(path)` | Declare an action is available at this path | `ctx.action.add(prefix + '/restart')` |

See [probe-sandbox.md](probe-sandbox.md) for full API reference.

### Return value

```js
{
  state: 'OK',                    // required: 'OK', 'WARNING', or 'ERROR'
  message: 'Redis responding',    // required: human-readable status
  responseMs: 42,                 // optional: override auto-measured time
  streamValues: { ... },          // optional: per-path metrics for charts
  scriptResult: { services: [] }  // optional: discovered sub-services
}
```

### streamValues

Additional metrics stored as time-series alongside the primary state. Each key is a path, each value is `{ state, value }`. All values are strings.

```js
streamValues: {
  '': { state: 'OK', value: '62.5' },                 // primary value (shown on probe row)
  'used': { state: 'OK', value: '52428800' },          // leaf value
  'total': { state: 'OK', value: '83886080' },         // leaf value
  'swap/percent': { state: 'OK', value: '2.1' },       // nested under "swap" group
  'swap/total': { state: 'OK', value: '4294967296' },   // nested under "swap" group
  'core/1': { state: 'OK', value: '45.2' },            // dynamic: core 1
  'core/2': { state: 'OK', value: '38.7' },            // dynamic: core 2
}
```

**Key rules:**
- `''` (empty) = primary value. Shown on the probe row. Not displayed in the expanded tree.
- Paths with `/` create a hierarchy: `swap/percent` renders under a collapsible `swap` group.
- Use `\/` to escape slashes that are part of a name (e.g. mount paths): `Library\/Developer\/CoreSimulator/percent` renders as group `Library/Developer/CoreSimulator` with child `percent`.
- Each path gets its own time-series history and sparkline chart.

### output (probe.yml)

The `output` section in `probe.yml` tells the frontend **how to display** each stream value. It serves three purposes:

1. **Type** — how to format the value (percent, bytes, number, etc.)
2. **Label** — display name instead of the raw key
3. **i18n** — translations per locale

```yaml
output:
  # Simple leaf value
  - path: used
    type: bytes
    label: Used
    i18n: { de: Belegt, fr: Utilisé }

  # Group node (no value, just a label for the collapsible section)
  - path: swap
    type: group
    label: Swap
    i18n: { de: Auslagerung }

  # Nested value under a group
  - path: swap/percent
    type: percent
    label: Usage

  # Dynamic pattern — {n} matches any value in that path segment
  - path: "core/{n}"
    type: percent
    label: "Core {n}"
    i18n: { de: "Kern {n}" }

  # Dynamic pattern for disk mounts
  - path: "{disk}/percent"
    type: percent
    label: Usage
  - path: "{disk}/used"
    type: bytes
    label: Used
```

#### Pattern matching

Patterns use `{name}` placeholders that match any path segment:

| Pattern | Matches | Captures |
|---------|---------|----------|
| `used` | `used` | — |
| `swap/percent` | `swap/percent` | — |
| `core/{n}` | `core/1`, `core/2`, `core/15` | `n=1`, `n=2`, `n=15` |
| `{disk}/percent` | `root/percent`, `data/percent` | `disk=root`, `disk=data` |

Captured values are substituted into the `label` and `i18n` strings. So `"Core {n}"` with `n=3` becomes `"Core 3"`. In German: `"Kern {n}"` → `"Kern 3"`.

#### Matching resolution order

For both labels and types, the frontend matches in this order:

1. **Full path** against each output pattern (e.g. `root/percent` matches `{mount}/percent`)
2. **Leaf segment** against the leaf of each pattern (e.g. `percent` matches the `percent` in `{mount}/percent`)
3. **Key name inference** as final fallback (e.g. key ending in `Bytes` → bytes type)

This means you don't need to declare every possible dynamic prefix. A single `{mount}/percent` entry with `type: percent` and `label: Usage` will format the `percent` child under any mount point group.

#### Escaped slashes in stream keys

Stream value keys use `/` as the hierarchy separator. If a value name itself contains `/` (like a file path), escape it with `\/`:

```js
// In check.js:
var key = mount.replace(/\//g, '\\/')   // /Library/Dev → Library\/Dev
sv[key + '/percent'] = { state: 'OK', value: '' + pct }
```

The tree builder treats `\/` as a literal slash in the display label, not a hierarchy split. So `Library\/Developer\/CoreSimulator/percent` renders as group `Library/Developer/CoreSimulator` with child `percent`.

#### Types

| Type | Formatting | Storage | UI |
|------|-----------|---------|-----|
| `state` | As-is | Every tick, aggregated | Uptime timeline |
| `number` | 2 decimals | Every tick, aggregated | Line chart |
| `percent` | 1 decimal + `%` | Every tick, aggregated | Line chart (0-100) |
| `bytes` | Auto KB/MB/GB | Every tick, aggregated | Line chart |
| `log` | As-is | Every tick, raw only | Log viewer |
| `label` | As-is | On change only | Change timeline |
| `group` | — | Not a value | Collapsible section header (can take `icon`) |
| `action` | — | Not a value | Button (see [Actions](#actions)) |
| `color` | Hex or `h,s,b` | Every tick, raw | Color swatch |
| `string` | As-is | On change only | Plain text |
| `duration` | Seconds | Every tick, aggregated | Human-formatted time span |
| `timestamp` | ms epoch | On change only | Relative time ("3m ago") |
| `location` | `lat,lon` | On change only | Inline mini-map |

If no output entry matches a stream value path, the frontend falls back to inferring the type from the key name (`*Bytes` → bytes, `*percent` → percent).

#### Locale resolution

The frontend picks the label in this order:
1. `i18n[browserLocale]` (e.g. `i18n.de` for a German browser)
2. `label` (English default)
3. Raw key name (fallback)

### Templated paths

Probes that discover instances at runtime emit stream values at dynamic paths — e.g. one entry per container, light, or backend. To keep the `output:` section compact, use `{var}` placeholders instead of listing every concrete path:

```yaml
output:
  - path: "{location}/{group}/{type}/{light}"
    type: group
    label: "{light}"
    icon: lightbulb
  - path: "{location}/{group}/{type}/{light}/power"
    type: state
    label: Power
  - path: "{location}/{group}/{type}/{light}/brightness"
    type: percent
    label: Brightness
```

Any path segment in curly braces matches any value. The captured value can be referenced in `label`, `i18n`, and layout bindings (see below). Templated paths also define the shape of the tree — every `{var}` introduces a hierarchy level.

In `check.js`, emit the concrete paths:

```js
var prefix = esc(locationName) + '/' + esc(groupName) + '/' + type + '/' + esc(lightName)
sv[prefix + '/power']      = { state: 'OK', value: isOn ? 'on' : 'off' }
sv[prefix + '/brightness'] = { state: 'OK', value: '' + pct }
```

Slashes that are part of a name (mount points, labels containing `/`) must be escaped with `\\/` — see the [Escaped slashes](#escaped-slashes-in-stream-keys) section above.

### Actions

Actions are operator-triggered operations attached to a stream-value path — "Turn On" on a light, "Restart" on a container, "Flush Cache" on a service. They show up inline in the probe tree next to the thing they act on.

Declaring an action takes three pieces:

#### 1. Output entry with `type: action`

```yaml
output:
  - path: "{location}/{group}/{type}/{light}/on"
    type: action
    label: "Turn On"

  - path: "{location}/{group}/{type}/{light}/setColor"
    type: action
    label: "Set Color"
    params:
      - name: hue
        type: number
        label: Hue
        min: 0
        max: 360
        default: 0
        widget: hue-slider
      - name: brightness
        type: number
        label: Brightness
        min: 1
        max: 100
        default: 100
        widget: slider
```

Simple actions (no params) render as a single button. Actions with `params:` render a form when clicked; values are passed to the action script as `ctx.params.<paramName>`.

**Supported widgets:** `slider`, `hue-slider`, `kelvin-slider`, `color-picker`, `text`, `select`. Each widget takes type-appropriate extras (`min`/`max` for sliders, `options` for `select`).

For **array params** (repeated groups — e.g. a color per strip zone), size the array from a stream value:

```yaml
- name: zones
  type: array
  size: { from: zoneCount }    # read from ctx.num('zoneCount') at form-open time
  item:
    type: color
    widget: color-picker
```

#### 2. `presets:` — one-click form fills (optional)

Presets are named form-fillers. Each preset has a short JS generator that runs with a mini-context (`ctx.num(path)`, `ctx.get(path)`) and returns an object matching the param shape:

```yaml
- path: "{location}/{group}/{type}/{light}/setZoneColors"
  type: action
  label: "Set Zone Colors"
  params: [...]
  presets:
    - id: rainbow
      name: Rainbow
      description: Evenly-spaced hues across the strip
      generator: |
        var n = ctx.num('zoneCount') || 16
        var zones = []
        for (var i = 0; i < n; i++) zones.push({ hue: Math.round(360 * i / n), saturation: 100, brightness: 100 })
        return { zones: zones }
```

Clicking a preset chip replaces the current form values with the generator's return object. `ctx.num` / `ctx.get` read the probe's latest stream values at that path (relative to the action's parent).

#### 3. `ctx.action.add(path)` in `check.js`

During `check(ctx)`, call `ctx.action.add()` for every action that is currently available — the frontend uses this to know whether to render the button for any given instance. Omit actions that don't apply (e.g. if a container is already stopped, don't add its "stop" action):

```js
function check(ctx) {
  // ... build streamValues ...
  for (var i = 0; i < lights.length; i++) {
    var prefix = esc(loc) + '/' + esc(group) + '/' + type + '/' + esc(lights[i].label)
    ctx.action.add(prefix + '/on')
    ctx.action.add(prefix + '/off')
    ctx.action.add(prefix + '/setColor')
    if (type === 'strip' || type === 'matrix') {
      ctx.action.add(prefix + '/setZoneColors')
    }
  }
  return { state: 'OK', streamValues: sv }
}
```

#### 4. `actionScripts:` mapping + handler files

Each action's leaf name (the last path segment — `on`, `off`, `setColor`) maps to a script file in the probe folder:

```yaml
actionScripts:
  on: action-on.js
  off: action-off.js
  setColor: action-setColor.js
```

Action scripts define `action(ctx)` (not `check(ctx)`) and return the same shape as a probe check — `{ state, message, ... }`:

```js
// action-on.js
function action(ctx) {
  var light = ctx.params.contextLeaf || ctx.params.container
  var token = ctx.params.token

  ctx.log.log('Turning on: ' + light)

  var res = ctx.http.put(
    'https://api.lifx.com/v1/lights/label:' + encodeURIComponent(light) + '/state',
    JSON.stringify({ power: 'on' }),
    { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' }
  )

  if (!res.ok) return { state: 'ERROR', message: 'HTTP ' + res.status }
  return { state: 'OK', message: light + ' turned on' }
}
```

Action scripts get the same sandbox as probes — `ctx.http`, `ctx.tcp`, `ctx.socket`, `ctx.shell`, `ctx.params`, plus:

- `ctx.params.contextLeaf` — the captured `{var}` closest to the action path (e.g. the light label for `{location}/{group}/{type}/{light}/on`). Use this to identify the instance being acted on.
- `ctx.params.<probeParam>` — all probe-level params (tokens, credentials, etc.) — merged with the user-submitted action form values.
- `ctx.log.log(msg)` — stream a line to the action dialog as the script runs (visible live while the action is executing).

### Tree-attached logs

Probes can attach log lines to any node in their stream tree — the frontend renders a "logs" button next to the leaf that opens an inline log viewer. Two flavors:

**`ctx.log.push(path, lines)`** — push lines you already have (from an HTTP response, a parsed file, an API call). The server appends them to a log file keyed by `probe://<agent>/<probeName>/<path>`. Repeated pushes accumulate.

```js
var res = ctx.http.get(base + '/logs?limit=200')
if (res.ok) {
  ctx.log.push(prefix + '/recent', res.body.split('\n'))
}
```

**`ctx.log.ref(path, uri)`** — the log content isn't in the probe; it lives elsewhere. Point the tree node at a log-source URI and the frontend will tail that source directly:

```js
ctx.log.ref(prefix, 'docker://' + containerName)
ctx.log.ref(prefix + '/journal', 'journald://' + unitName)
ctx.log.ref(prefix + '/file', 'file:///var/log/' + service + '.log')
```

Supported schemes are handled by catalog log sources (`catalog/logsources/{docker,file,journald}/source.{yml,js}`) — any JS-scripted scheme can be added without Java changes.

`ctx.log.log(msg)` is separate — it's a **debug stream** surfaced live in the probe/action run dialog, not persisted to the tree. Use it for "what is this probe doing right now", not structured log output.

### Dashboard layout (tiles)

By default, expanding a probe group shows its children as `key: value` rows. For probes with lots of dynamic instances (per-container, per-light, per-core), declare a `layout:` section to render each instance as a grid of tiles instead.

```yaml
layout:
  # Root-level summary tiles (always shown at top of the probe)
  - tile: 1x1
    widget: value
    path: "on"
    label: "On"

  # Per-instance tiles — applied once per matching {var} expansion
  - tile: 1x1
    widget: value
    path: "{location}/{group}/{type}/{light}/power"
    label: Power
    group: "{location}/{group}/{type}/{light}"

  - tile: 1x1
    widget: gauge
    path: "{location}/{group}/{type}/{light}/brightness"
    label: Brightness
    max: 1
    group: "{location}/{group}/{type}/{light}"

  # Only color lamps have a /color leaf — type-specific tiles skip automatically
  # when the concrete path isn't emitted.
  - tile: 1x1
    widget: color
    path: "{location}/{group}/color/{light}/color"
    label: Color
    group: "{location}/{group}/color/{light}"

  # Glob matcher — pulls all zones into one multi-segment strip
  - tile: 4x1
    widget: multizone
    paths: "{location}/{group}/strip/{light}/zones/*/color"
    label: Zones
    group: "{location}/{group}/strip/{light}"
```

**Fields:**

- `tile` — grid span, `<cols>x<rows>`. The panel is **4 units wide**; a span wider than that is
  clamped. Canonical sizes: `1x1` `2x1` `1x2` `2x2` `3x1` `3x2` `4x1` `4x2`; the shipped
  catalog also uses `4x3`.
- `widget` — renderer. **⚠️ There are two renderers, and they accept different widget names
  from the same `layout:` block.**

  | | Probe card (the board) | 3D topology view |
  |---|---|---|
  | Renders | the board people look at | the plate / topology visualisation |
  | Widget count | 10 | 33 |

  | Works in | Widgets |
  |---|---|
  | **Both** | `value` `gauge` `chart` `bar` `bars` |
  | **Probe card only** | `color` `grid` `image` `list` `multizone` |
  | **Topology view only** | `action` `badge` `cake` `chart-billboard` `compass` `delta` `flame` `fluid-tank` `heatmap` `hourglass` `log` `matrix-rain` `node` `odometer` `orbital` `oscilloscope` `paper-stack` `progress-circle` `radar` `split-flap` `split-flap-board` `stacked-bars-tower` `text` `thermometer` `ticker-tape` `tray` `uptime-strip` `vu-meter` |

  🚨 **A widget the probe card doesn't know renders NOTHING — silently.** The card's renderer
  has no fallback branch, so a tile naming `flame` or `odometer` produces an empty cell with
  no error, no warning, no log line. If a probe's
  tiles are for the board people actually look at, **stay inside the five that work in both**
  unless you specifically want a card-only widget.

  Per-widget fields are listed in `references/widgets.md`. The shipped `demo-widgets` probe
  exercises them — note its own description says it is for verifying the **topology view**
  pipeline, which is why most of its tiles are topology-only.

### scriptResult (for service discovery)

Probes that discover sub-services (like status pages) return a tree:

```js
scriptResult: {
  services: [
    {
      name: 'API',
      probes: [
        { name: 'Status', status: 'OK', message: 'operational' },
        { name: 'Latency', status: 'WARNING', message: 'degraded' }
      ]
    }
  ]
}
```

## Examples

### HTTP JSON endpoint with field checks

```js
function check(ctx) {
  const res = ctx.http.get('http://' + ctx.params.host + ':' + ctx.params.port + '/api/status')
  if (!res.ok) return { state: 'ERROR', message: 'HTTP ' + res.status }

  const data = JSON.parse(res.body)
  const state = data.healthy ? 'OK' : 'ERROR'

  return {
    state: state,
    message: data.version || data.status,
    responseMs: res.elapsed,
    streamValues: {
      responseMs: { state: 'OK', value: '' + res.elapsed },
      activeConnections: { state: 'OK', value: '' + (data.connections || 0) }
    }
  }
}
```

### Docker container via Unix socket

```js
function check(ctx) {
  const sock = ctx.params.docker_socket || '/var/run/docker.sock'
  const res = ctx.socket.http(sock, '/containers/' + ctx.params.container + '/json')

  if (!res.ok) return { state: 'ERROR', message: 'Container not found' }

  const c = JSON.parse(res.body)
  const running = c.State && c.State.Running

  return {
    state: running ? 'OK' : 'ERROR',
    message: running ? 'Up ' + c.State.Status : 'Not running',
    streamValues: {
      state: { state: running ? 'OK' : 'ERROR', value: c.State.Status }
    }
  }
}
```

### HAProxy stats via Unix socket

```js
function check(ctx) {
  const res = ctx.socket.send(ctx.params.socket_path || '/var/run/haproxy.sock', 'show stat\n')
  if (!res.ok) return { state: 'ERROR', message: res.message }

  const lines = res.response.split('\n').filter(function(l) { return l && !l.startsWith('#') })
  var errors = 0
  var total = 0

  lines.forEach(function(line) {
    var fields = line.split(',')
    if (fields[17]) { // status field
      total++
      if (fields[17] !== 'UP' && fields[17] !== 'OPEN') errors++
    }
  })

  return {
    state: errors > 0 ? 'WARNING' : 'OK',
    message: errors + '/' + total + ' backends degraded',
    streamValues: {
      backends: { state: 'OK', value: '' + total },
      errors: { state: errors > 0 ? 'WARNING' : 'OK', value: '' + errors }
    }
  }
}
```

### Host system metrics (ctx.host)

The `ctx.host` API exposes the agent's host machine metrics — CPU, memory, disk, uptime. Works cross-platform (Linux, macOS) without needing `ctx.shell`. Values are cached for 5 seconds so multiple probes in the same cycle don't re-collect.

Returns Java Maps — use `.get('key')` to access properties, `.length` and `[i]` for lists.

```js
// CPU probe with per-core breakdown
function check(ctx) {
  var cpu = ctx.host.cpu()
  var util = cpu.get('utilizationPercent') || 0
  var sv = {}
  sv[''] = { state: 'OK', value: '' + util }
  sv['overall'] = { state: 'OK', value: '' + util }

  var la = cpu.get('loadAverage')
  if (la) sv['loadAverage'] = { state: 'OK', value: '' + la }

  var perCore = cpu.get('perCore')
  if (perCore) {
    for (var i = 0; i < perCore.length; i++) {
      var cu = perCore[i].get('utilizationPercent')
      if (cu != null) sv['core/' + i] = { state: 'OK', value: '' + cu }
    }
  }

  return { state: 'OK', message: util + '%', streamValues: sv }
}
```

#### ctx.host.cpu() fields

| Field | Type | Description |
|-------|------|-------------|
| `cores` | int | Number of CPU cores |
| `utilizationPercent` | double | Overall CPU usage (0-100) |
| `loadAverage` | double | System load average |
| `load1m`, `load5m`, `load15m` | double | Load averages (Linux only) |
| `perCore` | List | Per-core data, each with `utilizationPercent` (Linux only) |

#### ctx.host.memory() fields

| Field | Type | Description |
|-------|------|-------------|
| `usedPercent` | double | Memory usage (0-100) |
| `usedBytes` | long | Used memory in bytes |
| `totalBytes` | long | Total memory in bytes |
| `swapUsedPercent` | double | Swap usage (Linux only) |
| `swapTotalBytes` | long | Swap total (Linux only) |

#### ctx.host.disks() — returns a list

Each entry:

| Field | Type | Description |
|-------|------|-------------|
| `mount` | string | Mount point (e.g. "/", "/data") |
| `name` | string | Device name |
| `usedPercent` | double | Disk usage (0-100) |
| `usedBytes` | long | Used space in bytes |
| `totalBytes` | long | Total space in bytes |

#### ctx.host.uptime() fields

| Field | Type | Description |
|-------|------|-------------|
| `seconds` | double | System uptime in seconds |
| `jvmUptimeMs` | long | Agent JVM uptime in milliseconds |

## Thresholds

Probes always return raw values with `state: 'OK'`. The server evaluates thresholds separately based on rules in `infrastructure.yml`:

```yaml
thresholds:
  - match:
      probe: system-memory
    warn: 80
    error: 90
  - match:
      probe: system-disk
    warn: 85
    error: 95
  - match:
      probe: http-endpoint
      agent: prod-web-01
    field: responseMs
    warn: 500
    error: 2000
```

One threshold per probe identity. No threshold = informational (always OK). The `match` section filters by `probe` (catalog ID) and optionally `agent` name.

Probe types can declare suggested defaults in their `probe.yml`:

```yaml
suggestedThresholds:
  warn: 80
  error: 90
```

These serve as templates — the admin can accept or customize them.

## Step 3: Deploy

1. Copy the probe folder to the server's config path: `config-path/probes/my-probe/`
2. The server detects the change via file watcher
3. Agents sync the catalog within 3 seconds
4. Add the probe to `infrastructure.yml`:

```yaml
probes:
  - name: Redis
    probe: redis-check
    target: tcp://redis.internal:6379
    agent: my-agent
```

Or use the admin UI: Infrastructure → select service → Add Probe → pick from catalog.

## Tips

- Keep scripts simple — most probes are 10-20 lines
- Use semantic param types (`hostname`, `port`) — enables dependency tracking
- Return `streamValues` for anything you want charted over time
- Test with fixed params first, then make them configurable
- The `check.js` runs in a fresh context each time — no state between executions
- Statement limit is 50,000 — more than enough for any probe, prevents infinite loops
