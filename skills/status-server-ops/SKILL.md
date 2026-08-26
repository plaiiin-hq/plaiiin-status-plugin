---
name: status-server-ops
description: Use when modelling infrastructure, adding or changing probes, wiring project tabs, or debugging a probe on a Plaiiin Status server — especially when a probe reads green, empty or absent and you need to know whether it is actually running. Covers infrastructure.yml, the probe catalog, applying config without dropping sessions, and five wiring mistakes that fail as SILENCE rather than as errors.
---

# Operating a Plaiiin Status server

Status is infrastructure-first: you declare what you have, and Status works out what to
check. This skill covers authoring that declaration and getting changes live.

> **Two rules dominate everything below.**
>
> 1. **Most wiring mistakes here fail as silence, not as errors.** A misrouted probe never
>    runs; a mistyped `ref` renders an empty node; a server-side JS probe silently degrades
>    to a plain HTTP check. All three look like health. **Verify, don't assume** — see
>    *Verifying* at the end, and do it every time.
> 2. **Never restart the container to apply a config change.** It drops every logged-in
>    session and everyone has to sign in again. Use the file-watcher instead.

## Reference files

Read these on demand — they are the authoritative detail, not summaries.

| File | Covers |
|---|---|
| `references/infrastructure-yml.md` | **Every top-level section**, field by field: `hosts`, `projects`, `dependencies`, `sites` (floor plans), `thresholds`, `defaults`, agent policies. |
| `references/writing-probes.md` | The full probe-authoring guide: `probe.yml`, `check.js`, the sandbox APIs, `streamValues`, templated paths, actions, tree-attached logs, `scriptResult`, thresholds, worked examples. |
| `references/widgets.md` | All 33 dashboard widgets and their fields, by category, plus tile spans. |
| `references/probe-sandbox.md` | The sandbox contract and the full param-type table. |
| `references/probes.md` | Probe kinds, local vs remote, how binding works. |
| `references/credentials-store.md` | Credential types (`bearer`, `basic`, `header`, `oauth2`, `tls`, `ssh`) and wiring them into probes. |
| `references/icons.md` · `references/notifications.md` | Icon set; Telegram/webhook notification config. |
| `references/probe-active-folder.md` · `references/probe-vs-command.md` | Active-folder mechanics; when to write a command instead of a probe. |
| `references/infrastructure-model.md` | The model in prose — hosts, host-agents, agent security, agent policies. |

## The model

```
Project
  └── App
        └── Service ──── runs on ──── Host
              └── Probe (from the catalog, or custom)

Dependency (third-party, no host)
  └── StatusNode (from a JS mapper script)
```

| Entity | What it is |
|---|---|
| **Project** | A business-concern grouping that becomes a tab. "Trading Platform", "Infrastructure". |
| **App** | A deployable unit users care about. Belongs to a project, contains services. |
| **Host** | A machine. Has an address and optional labels (provider, location, os). Rolls up from its services, and carries host-level probes of its own (Docker, CPU, memory, disk). |
| **Service** | A running process of an app, on a host. Status derives from its probes. |
| **Dependency** | An external third party (GitHub, Docker Hub, Cloudflare) with a `consumers` list naming which apps degrade with it. |
| **Probe** | The actual check. `HTTP_HEALTH`, `HTTP_JSON`, `TCP_CONNECT`, `DOCKER`, `SCRIPT`, `MAPPED_JSON`. |

Two independent trees exist and it matters which one you are talking about:

- **`Agents / <host> / <probe name>`** — the physical tree, built from `hosts:`. This is
  where probes actually live and where history is keyed.
- **`projects:`** — a logical view that does **not** own anything. It `ref`s into the
  physical tree by path string. A project tab is a set of pointers.

## `infrastructure.yml`

```yaml
hosts:
  - name: app-01.example.com
    address: app-01.example.com
    user: root
    labels: { provider: acme-cloud, location: "eu-central", os: Ubuntu 22.04 }
    probes:
      - name: SSH                       # catalog probe, decomposed form
        probe: tcp-port
        host: app-01.example.com
        port: 22

      - name: Web Reachable             # catalog probe, target form
        probe: http-endpoint
        target: https://example.com

      - name: SSL example.com
        probe: ssl-certificate
        target: https://example.com
        interval: 3600                  # seconds; default is the catalog's

      - name: Docker
        probe: docker-services

projects:
  - name: Public Site
    apps:
      - name: Web
        services:
          - name: API
            refs:
              - Agents / app-01.example.com / Web Reachable
              - Agents / app-01.example.com / Docker / web-api
```

`refs` are **whitespace-sensitive path strings** into the physical tree. They are matched,
not validated — see trap 2.

### Applying a change without a restart

The catalog watcher reloads infrastructure when a probe definition file is touched:

```bash
# 0. ALWAYS back up first
ssh $HOST 'cp /status/tower-config/infrastructure.yml \
             /status/tower-config/infrastructure.yml.bak-$(date +%Y%m%d-%H%M%S)'

# 1. validate locally BEFORE copying — a broken YAML reloads as nothing
python3 -c "import yaml,sys; yaml.safe_load(open('infrastructure.yml'))" && echo YAML-OK

# 2. copy, then poke the watcher
scp infrastructure.yml $HOST:/status/tower-config/infrastructure.yml
ssh $HOST 'touch /status/tower-config/probes/<any-probe-id>/probe.yml'

# 3. ~20s later, confirm it actually loaded
ssh $HOST 'docker logs --since 2m status 2>&1 | grep "Infrastructure loaded"'
```

### ⚠️ The watcher cannot change a probe in place

`ProbeScheduler.reload()` keys probes by id and does:

```java
if (existing != null && existing.getName().equals(pc.getName())) updated.put(id, existing);
```

It reuses the **old `Probe` object**. So a probe whose **name is unchanged while its config
changed keeps the old config**. Editing a `target:`, a `port:` or an `interval:` in place
does *nothing*, silently, and the board keeps showing the old check passing.

**Rename the probe** and it registers fresh. Never restart just for this.

### Ghost probes after a rename or delete

A renamed or deleted probe lingers on the board, by design: `/api/tree` unions scheduled
probes with history, so any name still in `historyStore.getAllLatest()` renders at its last
value even though nothing schedules it any more. Clear it without costing anyone a session:

```bash
curl -X POST -H "X-API-Key: $STATUS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"items":[{"name":"Agents / app-01.example.com / Old Probe Name","type":"probe"}]}' \
  "$STATUS_URL/api/admin/storage/delete"     # -> {"deleted":1}
```

## The probe catalog

Each catalog probe is a directory under `tower-config/probes/<id>/` holding `probe.yml`
(metadata, typed params, declared outputs, dashboard layout) and `check.js` (the check).
~40 ship in the box: HTTP/TCP/SSL, Docker, host metrics, databases (Postgres, MySQL, Redis,
Elasticsearch, RabbitMQ), CI (Jenkins, GitHub Actions), and a long tail of third-party
`*-status` pages.

**Param types:** `url` · `hostname` · `port` · `string` · `text` · `int` · `number` ·
`boolean` · `select` · `duration` · `percent` · `bytes` · `timestamp` · `color` · `location` ·
`state` · `label` · `group` · `action` · `credential`

**Sandbox APIs** available to `check.js`: `ctx.http.get` · `ctx.tcp.connect` ·
`ctx.socket.http` (Unix sockets) · `ctx.shell.run` · `ctx.exec` · `ctx.action.add` ·
`ctx.log` · `ctx.host` · `ctx.util` · `ctx.params`

**States:** `OK` · `WARNING` · `ERROR` · `UNKNOWN` — note it is `WARNING`, not `WARN`.

A check returns a state, a message, and a `streamValues` map keyed by the output paths
`probe.yml` declares:

```js
function check(ctx) {
  var res = ctx.http.get(ctx.params.url)
  var ok = res.ok, state = ok ? 'OK' : 'ERROR'
  return {
    state: state,
    message: 'HTTP ' + res.status,
    streamValues: {
      '':         { state: state, value: '' + res.elapsed },  // primary — drives the row sparkline
      statusCode: { state: state, value: '' + res.status },
      up:         { state: state, value: ok ? '1' : '0' }
    }
  }
}
```

The `''` (empty path) entry is the **primary** value and drives the inline sparkline on the
probe row. Omit it and the row renders flat. `http-endpoint` records `responseMs`, so it is a
genuine latency probe rather than up/down — give every public endpoint one.

Full contract, including templated `{var}` paths, actions, tree-attached logs and
`scriptResult` service discovery: `references/writing-probes.md`.

## 🚨 Five traps that fail as SILENCE

| # | Trap | Rule |
|---|---|---|
| 1 | **Decomposed `host:`/`port:` binds the probe to an agent named after the HOST.** `InfrastructureLoader` does `pc.setAgent(pd.getAgent() != null ? pd.getAgent() : hostName)`. On a host with **no agent installed**, the probe is assigned to an agent that does not exist and simply never runs — no result, no warning, no red. | On an agentless host every probe MUST use `target:` (including `target: tcp://host:port`). That leaves the agent null, so the **server** runs it. |
| 2 | **A project `ref` that misses resolves to an empty node.** `PathTree.resolve` returns null silently — you get a blank card, not an error. | Cross-check every `ref` against the **live** tree (`/api/tree`) before you call it done. Mind the spaces around the `/` separators. |
| 3 | **`docker-services` refs use the CONTAINER name, not `<stack>/<service>`.** The tree is built from `scriptResult.services`, whose entries are `{ name: rawName }`. The `<stack>/<service>` prefix exists only for `streamValues`, `ctx.action` and `ctx.log.ref`. | Ref them as `Agents / <host> / Docker / <containerName>` — e.g. `Agents / app-01.example.com / Docker / web-api`. |
| 4 | **The server has no JS sandbox** — it has 7 native checkers only (`DockerChecker`, `HttpHealthChecker`, `HttpJsonChecker`, `MappedJsonChecker`, `ScriptChecker`, `TcpConnectChecker`). Any JS catalog probe run **server-side** degrades to `HTTP_HEALTH`. An `ssl-certificate` probe will cheerfully report "HTTP 200" while checking no expiry whatsoever. | Name server-side probes for what they actually do — "Web Reachable", not "SSL Certificate". A real cert or Docker probe needs an **agent on the box**. |
| 5 | **Agents running `AGENT_READONLY=true` refuse shell.** A `SCRIPT` probe that needs a shell (e.g. `dns-resolve`) can only ever return "requires shell access" — a permanent red. | Never ship a red that cannot go green. It trains people to ignore red, which is the only thing a status board is for. |

## Verifying — do this, every time

```bash
# 1. state transitions since the reload (no line means "unchanged")
ssh $HOST 'docker logs --since 3m status 2>&1 | grep "state change"'

# 2. anything not OK
ssh $HOST 'docker logs --since 3m status 2>&1 | grep "state change" | grep -vE "=> OK"'

# 3. a probe with NO history file has never run — the trap-1 signature
ssh $HOST 'ls /var/lib/docker/volumes/status_status-data/_data/history | grep <name>'

# 4. best: read the real tree and confirm every ref resolved
curl -s -H "X-API-Key: $STATUS_API_KEY" "$STATUS_URL/api/tree"
```

A `(agent)` in a state-change line means an agent ran it; **its absence means the server
ran it**. That single word tells you whether trap 1 bit you.

## Config stays file-based

`infrastructure.yml` is not writable over the API, deliberately: `InfrastructureLoader.save()`
re-serialises from the Jackson object graph, which erases **every comment in the file** —
including any trap documentation you left for the next person.

The cost is that file edits skip the config-history audit trail (`recordAfterWrite` only
runs on the API path). Say so when you make one.

## See also

`status-server-api` — driving a running board from Claude: reading the tree, probe history,
incidents, and authoring probes over `/api/ide/*`.
