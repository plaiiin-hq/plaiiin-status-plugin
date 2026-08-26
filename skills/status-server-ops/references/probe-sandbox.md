# Probe Sandbox

All probes are JavaScript scripts executed in a GraalVM sandbox on the agent. The sandbox provides network and system APIs as host objects — probes use whatever they need.

## Architecture

```
Server                              Agent
  infrastructure.yml                  ProbeSandbox (shared GraalVM Engine)
    → probe: github-status              → creates Context per execution
    → params resolved                   → binds ctx (http, tcp, udp, socket, exec, host, params)
    → scriptSource from catalog         → runs check(ctx)
    → sent in heartbeat assignment      → returns {state, message, responseMs, streamValues}
```

The server sends the JS source + resolved params in the heartbeat response. The agent runs the script in a sandboxed GraalVM context with a 50,000 statement limit. One shared `Engine` across all probes for JIT compilation reuse.

## Sandbox APIs

### ctx.http — HTTP/HTTPS Client

```js
// GET
const res = ctx.http.get('https://api.example.com/health')
const res = ctx.http.get('https://api.example.com/health', { 'Authorization': 'Bearer token' })

// POST
const res = ctx.http.post('https://api.example.com/data', '{"key":"val"}')
const res = ctx.http.post('https://api.example.com/data', '{"key":"val"}', { 'Content-Type': 'application/json' })

// Response
res.status   // 200
res.body     // response body string
res.ok       // true if 2xx
res.elapsed  // milliseconds
```

### ctx.tcp — TCP Connections

```js
// Check if a port is open
const res = ctx.tcp.connect('db.example.com', 5432)
const res = ctx.tcp.connect('db.example.com', 5432, 5)  // 5s timeout

// Response
res.ok       // true if connected
res.elapsed  // milliseconds
res.message  // "Connected to db.example.com:5432" or error
```

### ctx.udp — UDP Send/Receive

```js
const res = ctx.udp.send('dns.example.com', 53, 'ping')
const res = ctx.udp.send('dns.example.com', 53, 'ping', 5)  // 5s timeout

res.ok       // true if sent
res.elapsed  // milliseconds
res.reply    // response string (null if timeout)
```

### ctx.socket — Unix Domain Sockets

Covers Docker, PostgreSQL, Redis, HAProxy, systemd, and any service that exposes a Unix socket.

```js
// Raw send/receive
const res = ctx.socket.send('/var/run/haproxy.sock', 'show stat\n')
res.ok        // true
res.response  // response string
res.elapsed   // milliseconds

// HTTP over Unix socket (Docker API, containerd, etc.)
const res = ctx.socket.http('/var/run/docker.sock', '/containers/json')
const res = ctx.socket.http('/var/run/docker.sock', 'POST', '/containers/abc123/restart', null)

res.status    // 200
res.body      // JSON string
res.ok        // true if 2xx
res.elapsed   // milliseconds
```

Docker isn't special — it's just HTTP over a Unix socket. Any service with a socket API works the same way.

### ctx.shell — Command Execution

Gated by the agent's `readonly` flag. Disabled by default in production.

```js
const res = ctx.shell.run('df -h /')
const res = ctx.shell.run('systemctl is-active nginx', 5)  // 5s timeout

res.ok        // true if exit code 0
res.exitCode  // 0
res.stdout    // output
res.stderr    // error output
res.elapsed   // milliseconds
```

### ctx.host — Host System Metrics

Cross-platform access to the agent machine's CPU, memory, disk, and uptime. Uses JMX and filesystem APIs — no shell commands needed. Values are cached for 5 seconds.

Returns Java objects — use `.get('key')` for Maps, `.length` and `[i]` for Lists.

```js
// CPU
const cpu = ctx.host.cpu()
cpu.get('utilizationPercent')   // 24.7 (double, 0-100)
cpu.get('cores')                // 8
cpu.get('loadAverage')          // 3.2
cpu.get('load1m')               // 3.2 (Linux only)
cpu.get('perCore')              // List of Maps, each with 'utilizationPercent' (Linux only)

// Memory
const mem = ctx.host.memory()
mem.get('usedPercent')          // 64.9
mem.get('usedBytes')            // 9876543210
mem.get('totalBytes')           // 17179869184
mem.get('swapUsedPercent')      // 2.1 (Linux only)

// Disk — returns a List
const disks = ctx.host.disks()
disks.length                    // 3
disks[0].get('mount')           // "/"
disks[0].get('usedPercent')     // 45.2
disks[0].get('usedBytes')       // 120000000000
disks[0].get('totalBytes')      // 256000000000

// Uptime
const up = ctx.host.uptime()
up.get('seconds')               // 864000.5
up.get('jvmUptimeMs')           // 3600000
```

### ctx.log — Log Attachment

Three concerns, separate methods:

```js
// 1. Tree-attached log lines — appended under probe://<agent>/<probe>/<path>
//    Renders as an inline log viewer on the matching tree leaf.
ctx.log.push('recent', ['line 1', 'line 2'])

// 2. Tree-attached log reference — point a leaf at an external source
//    (handled by catalog log sources: docker://, file://, journald://, ...).
ctx.log.ref('keycloak', 'docker://portal-keycloak-1')

// 3. Debug stream — live-forwarded to the run dialog, not persisted to the tree.
//    Useful inside actions to narrate progress.
ctx.log.log('Restarting container ' + name)
```

Multiple `push()` calls to the same path accumulate. Multiple `ref()` calls overwrite (last wins). Paths without an explicit `ctx.log.*` entry don't get the "logs" button.

### ctx.action — Action Declaration

```js
ctx.action.add('{prefix}/restart')   // declare an action as currently available
```

The path must match an `output` entry with `type: action` in `probe.yml`. Actions not added during the current `check()` are hidden — use this to suppress actions that don't apply (e.g. "stop" on an already-stopped container).

Action execution runs a separate script (`actionScripts:` mapping in `probe.yml`) that defines `function action(ctx)` with the same sandbox. Handlers get `ctx.params.contextLeaf` — the captured value closest to the action path. See [writing-probes.md § Actions](writing-probes.md#actions).

### ctx.params — Probe Parameters

The resolved parameter values declared in `probe.yml`, merged with values from `infrastructure.yml`.

```js
ctx.params.host       // "db.example.com"
ctx.params.port       // 5432
ctx.params.url        // "https://api.example.com/health"
ctx.params.timeout    // 10
```

## Return Value

The `check(ctx)` function must return:

```js
{
  state: 'OK',              // 'OK', 'WARNING', or 'ERROR'
  message: 'HTTP 200',      // human-readable status
  responseMs: 42,            // optional, defaults to elapsed time
  streamValues: {            // optional, per-path metrics for history/charts
    responseMs: { state: 'OK', value: '42' },
    statusCode: { state: 'OK', value: '200' }
  },
  scriptResult: {            // optional, for probes that discover sub-services
    services: [
      { name: 'API', probes: [{ name: 'Status', status: 'OK', message: 'operational' }] }
    ]
  }
}
```

## Resource Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| Statement limit | 50,000 | Prevents infinite loops |
| Host access | Explicit only (@HostAccess.Export) | Only sandbox APIs exposed |
| Native access | Disabled | No JNI, no file system |
| Thread creation | Disabled | Single-threaded execution |
| Context lifetime | Per-execution | Created, run, destroyed — no state leaks |

The shared `Engine` caches compiled code across executions. Context creation is ~5ms. Network I/O dominates total execution time.

## Param Types

Parameter types in `probe.yml` carry semantic meaning beyond just validation:

| Type | Example | Semantic Use |
|------|---------|-------------|
| `hostname` | `db.example.com` | Host dependency tracking, topology graphs |
| `port` | `5432` | Service port mapping |
| `url` | `https://api.example.com/health` | Endpoint dependency tracking |
| `string` | `my-container` | Generic text |
| `int` | `10` | Numeric configuration |
| `map` | `{Authorization: Bearer ...}` | Key-value pairs (headers, labels) |
| `credential` | `acme-cloud-prod` | Reference to credentials store entry. Add `credential_type` to restrict: `bearer`, `basic`, `header`, `oauth2`, `tls`, `ssh` |

The system can index all probes by `hostname` params to answer "what's monitoring this host?" or build dependency graphs. Credential params are resolved server-side and delivered encrypted to agents — the probe script sees the decrypted credential data in `ctx.params.credentials`.

## Output Types

Stream values declared in the `output` section of `probe.yml` use these types:

| Type | Value | Storage | UI |
|------|-------|---------|-----|
| `state` | `OK`, `running` | Every tick, aggregated (ok/total) | Uptime timeline, status dots |
| `number` | `128` | Every tick, aggregated (min/max/avg) | Line chart |
| `percent` | `62.5` | Every tick, aggregated | Line chart, 0-100 scale |
| `bytes` | `301234567` | Every tick, aggregated | Line chart, auto KB/MB/GB/TB |
| `log` | `INFO Starting up` | Every tick, raw only | Log viewer |
| `label` | `nginx:1.25` | On change only (dedup) | Change timeline |
| `group` | — (not a value) | — | Collapsible tree node (accepts `icon`) |
| `action` | — (declared via `ctx.action.add`) | — | Operator-triggered button — see [writing-probes.md § Actions](writing-probes.md#actions) |
| `color` | `#ff8800` or `H,S,B` | Every tick, raw | Color swatch |
| `string` | `v2.14.3` | On change only | Plain text |
| `duration` | `3540` (seconds) | Every tick, aggregated | Human-formatted time span |
| `timestamp` | `1712849200000` (ms) | On change only | Relative time ("3m ago") |
| `location` | `47.5,11.3` (lat,lon) | On change only | Inline mini-map preview |

All values are strings in the stream. The type determines rendering, aggregation, and storage behavior.

`bytes` stores raw byte counts — the UI auto-formats for display. `label` only writes a new history entry when the value differs from the previous one, making it efficient for tracking versions, image tags, config values.
