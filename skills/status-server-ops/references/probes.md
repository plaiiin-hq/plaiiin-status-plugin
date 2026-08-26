# Probes

A probe is the atomic unit of monitoring. It produces **stream results** — one or more `/`-keyed values per execution. Every probe lives at the leaf of the tree: `Project → App → Service → Probe`.

## Probe Result: Stream Results

A probe execution produces a set of path-keyed values:

```
path         — "/" separated hierarchy (empty = primary value)
timestamp    — nanosecond epoch (BIGINT)
state        — OK, WARNING, ERROR, UNKNOWN
value        — the measurement (string-encoded)
```

The **primary value** (path = "") is used for tree display, alerts, and aggregation. Sub-paths carry additional detail, each with its own time-series in the same SQLite file.

### Example: Host CPU probe

```
""              → 2.3    (percent, primary — used for tree dot and alerts)
overall         → 2.3    (percent)
core/0          → 4.1    (percent)
core/1          → 1.2    (percent)
core/2          → 0.8    (percent)
core/3          → 3.5    (percent)
load/1m         → 0.35   (number)
load/5m         → 0.28   (number)
load/15m        → 0.22   (number)
```

### Example: Docker container probe

```
""              → running  (state, primary)
state           → Up 2 hours
cpu             → 0.4      (percent)
memory/percent  → 3.7      (percent)
memory/used     → 301234567  (bytes)
memory/limit    → 8127750144 (bytes)
network/rx      → 12582912   (bytes)
network/tx      → 3145728    (bytes)
image           → plaiiin/private:status (label)
```

### Example: HTTP Health probe

```
""              → OK     (state, primary)
responseMs      → 128    (number)
statusCode      → 200    (number)
```

All paths are stored in the same SQLite file, indexed by `(path, ts)`. The chart UI offers a path picker when multiple paths exist.

## Data Types

The `dataType` determines what `value` means, how it's aggregated, and how the UI renders it.

| dataType | value example | Aggregation | UI | History |
|----------|--------------|-------------|-----|---------|
| `state` | `running`, `HTTP 200` | worst state, ok/total count | Status dot, uptime timeline | Candle pyramid (5s→1m→1h→1d) |
| `number` | `128` (response ms) | min/max/avg/last/count | Line chart | Candle pyramid |
| `percent` | `2.3` (CPU %) | min/max/avg/last/count | Line chart (0-100 scale) | Candle pyramid |
| `bytes` | `301234567` (memory) | min/max/avg/last/count | Line chart (auto KB/MB/GB/TB) | Candle pyramid |
| `log` | `INFO Starting up...` | none | Log viewer | Raw only (no pyramid) |
| `label` | `plaiiin/private:status` | last value | Change timeline | Change-only (write on value change, not every tick) |

Default `dataType` if not specified: `state` for all probe types.

Note: `bytes` stores raw byte counts; the UI auto-formats to human-readable units (KB/MB/GB/TB) for display and chart axes. `label` is useful for tracking version changes, image tags, config values — anything that rarely changes but you want to know when it did.

## Probe Types (execution method)

| Type | What it does | Parameters | Returns |
|------|-------------|------------|---------|
| `HTTP_HEALTH` | GET request, check status code | `url`, `headers` | state: OK if 2xx, ERROR otherwise. value: `HTTP {code}` |
| `HTTP_JSON` | GET request, evaluate JsonPath expressions | `url`, `headers`, `checks[]` | state: worst of all checks. value: first failing check message |
| `TCP_CONNECT` | Open TCP socket | `host`, `port` | state: OK if connected. value: `Connected to {host}:{port}` |
| `MAPPED_JSON` | GET request + JS script | `url`, `headers`, `script` | state: worst of script tree. value: summary. **children**: service→probe tree |
| `SCRIPT` | Run shell command | `command` | state: OK (exit 0), WARNING (exit 1), ERROR (exit 2+). value: stdout |

### MAPPED_JSON Detail

The JS script must return:

```js
{
    services: [
        {
            name: "Service Name",
            probes: [
                { name: "Probe Name", status: "OK", message: "optional detail" },
                { name: "Another", status: "WARNING", message: "degraded" }
            ]
        }
    ]
}
```

The `services` array becomes child service→probe nodes in the tree, replacing the wrapper service. This is how external status pages, Jenkins jobs, and Grafana alerts expand into the tree structure.

## Probe Reach (where it can run)

| Reach | Description | Agent assignment | Examples |
|-------|------------|-----------------|----------|
| **Remote** | Checks a network endpoint — configurable target | Any agent, user picks | HTTP health on `app-02.example.com:9820`, TCP connect |
| **Fixed** | Checks a hardcoded URL — no target config | Any agent, user picks | GitHub Status, Cloudflare Status |
| **Local** | Reads from the agent's own host | Must be the local agent | Docker socket, `/proc`, container logs, local files |

The `agent` field on the probe (or inherited from app/service) determines which agent runs it.

## Probe Configuration

### New format: `probe:` + `target:`

```yaml
probes:
  - name: Health              # display name
    probe: http-health        # executor ID from catalog
    target: http://host:8080/health   # protocol URI
    agent: app-01.example.com    # which agent runs this
    interval: 60              # seconds (default: 60)

  - name: SSH
    probe: tcp-connect
    target: tcp://host:22

  - name: Components
    probe: mapped-json
    target: https://githubstatus.com/api/v2/summary.json
    script: statuspage
```

The `probe:` field is the executor ID (matches a catalog entry). The `target:` field is a protocol URI — the scheme indicates the transport, not the probe type. Multiple probe types can use the same protocol (e.g. `http-health` and `http-json` both take `http://` targets).

### Legacy format (still supported)

```yaml
probes:
  - name: Health
    type: HTTP_HEALTH
    url: http://host:8080/health
    host: host.example.com    # for TCP_CONNECT
    port: 8080                # for TCP_CONNECT
```

The legacy `type:` + `url:`/`host:`/`port:` format is still parsed for backward compatibility but should not be used for new probes.

## Probe Catalog

Probe definitions live in a three-layer system:

### 1. Built-in catalog

Shipped inside the server, read-only — you cannot edit these, only install or
override them. List what your server has with `GET /api/ide/probes`. Contains definitions for standard probe types:

```
catalog/
  probes/
    http-health/probe.yml
    tcp-connect/probe.yml
    http-json/probe.yml
    mapped-json/probe.yml
  commands/
    docker-restart/command.yml
    docker-stop/command.yml
    docker-start/command.yml
```

### 2. Installed catalog (`config-path/probes/`, `config-path/commands/`)

User-enabled definitions. When a user "enables" a probe from the catalog, its definition is copied here. This folder is watched for changes — updates are pushed to agents immediately.

Custom probes can be added by dropping a folder with `probe.yml` + optional `check.js`:

```
probes/
  my-custom-check/
    probe.yml       # manifest with id, name, params
    check.js        # JS executor (sandboxed GraalVM)
```

### 3. Catalog sync

- Server watches the installed folder for changes
- Agents poll `/api/catalog/sync?hash=X` every 3 seconds
- If the hash changed, agents pull the full catalog and hot-reload executors
- Built-in Java executors always take precedence over script-based ones

### Probe definition format (`probe.yml`)

```yaml
id: http-health
name: HTTP Health Check
description: Checks that an HTTP endpoint returns a 2xx status code
updated: 2026-04-05

changelog:
  - date: 2026-04-05
    note: Initial release

params:
  - name: target
    type: url
    required: true
    description: HTTP(S) endpoint to check

  - name: timeout
    type: int
    default: 10
    configurable: true
    description: Request timeout in seconds
```

Parameter modes:
- **required** — user must provide (e.g. target for tcp-connect)
- **configurable** — has a default, user can override (e.g. timeout)
- **fixed** — baked into the probe, shown but not editable (e.g. docker-hub-status target)

### Version updates

When the server ships a newer built-in version than what's installed, the admin UI shows "update available" with changelog entries since the installed version. Updates are opt-in — the user reviews changes and accepts or skips.

## Pluggable Executors (Agent)

Probe execution on the agent uses a registry pattern:

```
agent/probe/ProbeExecutor.java     — interface: type() + execute()
agent/probe/HttpHealthProbe.java   — @Component, type() = "HTTP_HEALTH"
agent/probe/TcpConnectProbe.java   — @Component, type() = "TCP_CONNECT"
agent/probe/HttpJsonProbe.java     — @Component, type() = "HTTP_JSON"
agent/probe/MappedJsonProbe.java   — @Component, type() = "MAPPED_JSON"
```

Spring autowires all `ProbeExecutor` implementations into `ProbeRunner` as `List<ProbeExecutor>`. Adding a new built-in probe type is just writing a class — no touching ProbeRunner.

Script-based probes from the catalog are loaded as `ScriptProbeExecutor` instances by `CatalogSyncService`. They use the same `ProbeExecutor` interface.

## Pluggable Commands (Agent)

Same pattern for commands:

```
agent/command/CommandExecutor.java      — interface: type() + execute()
agent/command/DockerControlCommand.java — restart/stop/start
agent/command/LogsCommand.java          — fetch container logs
agent/command/ScriptCommand.java        — manifest script execution
```

Spring autowires all `CommandExecutor` implementations into `HeartbeatService`.

From type catalog (auto-generated):

```yaml
# In infrastructure.yml — service references a type
services:
  - type: spring-boot
    port: 8080
    path: /actuator/health

# The type definition (builtin/types/spring-boot.yml) generates the probes:
probes:
  - name: Health
    type: HTTP_JSON
    url: http://${host}:${port}${path}
    checks:
      - path: $.status
        op: "=="
        value: "UP"
  - name: Reachable
    type: TCP_CONNECT
    port: ${port}
```

## Agent-Pushed Probes (current implementation)

These are not yet real `ProbeConfig` entries — they're synthesized from agent heartbeat data:

| Probe | Source | dataType | Where created |
|-------|--------|----------|--------------|
| Container Status | `heartbeat.containers[].state` | `state` | `StatusTree.buildHostNode()` |
| Container CPU | `heartbeat.containerStats[].cpuPercent` | `percent` | `StatusTree.buildHostNode()` |
| Container Memory | `heartbeat.containerStats[].memoryPercent` | `percent` | `StatusTree.buildHostNode()` |
| Container Image | `heartbeat.containers[].image` | `label` | `StatusTree.buildHostNode()` |
| Host CPU | `heartbeat.host.cpu.utilizationPercent` | `percent` | `StatusTree.buildHostNode()` |
| Host Memory | `heartbeat.host.memory.usedPercent` | `percent` | `StatusTree.buildHostNode()` |
| Host Disk | `heartbeat.host.disks[0].usedPercent` | `percent` | `StatusTree.buildHostNode()` |

History for these is written by `AgentMetricsHistoryWriter` (into `ProbeHistoryStore`), but they bypass `ProbeScheduler` and can't be individually configured or alerted on.

**Target architecture**: these become real probes assigned to the local agent, flowing through the same pipeline as all other probes.

## Retention Presets

Control how long probe history is kept at each resolution:

```yaml
# Builtin
standard:   { 5s: 7d, 1m: 30d, 1h: 1y, 1d: forever }
compact:    { 5s: 24h, 1m: 7d, 1h: 90d }
logs:       { 5s: 50mb }
none:       {}

# Custom (in config/retention-presets.yml)
my-preset:  { 5s: 3d, 1m: 14d, 1h: 6m }
```

A probe references a preset by name: `retention: standard`. Inline overrides also possible.

## History Storage

Each probe gets its own SQLite file (WAL mode, readers never blocked):

```
history/{sanitized-probe-name}.db
  ├── r_5s  (ts INTEGER, path TEXT, state TEXT, value TEXT)   — raw ticks
  ├── r_1m  (ts INTEGER, path TEXT, state TEXT, value TEXT)   — 1-minute candles
  ├── r_1h  (ts INTEGER, path TEXT, state TEXT, value TEXT)   — 1-hour candles
  └── r_1d  (ts INTEGER, path TEXT, state TEXT, value TEXT)   — 1-day candles

Indexes: (path, ts) on each table
```

- All timestamps are epoch **nanoseconds**. API returns epoch milliseconds for JS.
- `path = ""` is the primary value. Sub-paths like `cpu/core/0` are additional series.
- Aggregation only runs on the primary path (candle pyramid).
- Sub-paths are stored raw at 5s resolution, pruned by retention preset.
- One SQLite file per probe — all paths in the same file.

Aggregated values for numeric types: `"min max avg lastValue count"`.
Aggregated values for state types: `"okCount totalCount"`.

### API

```
GET /api/probes/history?probe={name}&path={path}&resolution=5s&limit=500
GET /api/probes/snapshot?probe={name}     — latest value for each path
GET /api/probes/history/list              — all probes with history
```

## Alert Integration

Probe state transitions trigger alerts:

```
OK → WARNING      → warning notification
OK → ERROR        → error notification
WARNING → ERROR   → escalation notification
ERROR/WARNING → OK → recovery notification (includes outage duration)
```

Probes tracked in an open incident skip standard alerts (incident-aware alerting).

## Chart UI

Click any probe in the dashboard → chart panel with:
- Line chart for numeric/percent/bytes probes
- Resolution picker: 5s / 1m / 1h / 1d
- Non-OK data points highlighted as colored dots
- API: `GET /api/probes/history?probe={name}&resolution=5s&limit=500`
