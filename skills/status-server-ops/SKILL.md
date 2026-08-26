---
name: status-server-ops
description: Use when setting up, modelling or operating a Plaiiin Status server — declaring hosts/projects/services, using SERVICE TYPES to auto-generate probes, writing custom probes and actions, and designing what a probe SHOWS: dashboard layout, tiles, widgets (gauge, chart, bar, value) and custom SVG infographics. Also for project tabs, dependencies, sites/floor-plans, thresholds, agent policies and alerting — and when a probe reads green, empty or absent and you need to know whether it is actually running. Covers reading and writing infrastructure.yml over the API, its fields one by one, the check.js sandbox, the Probe IDE, and six wiring mistakes that fail as SILENCE rather than as errors.
---

# Operating a Plaiiin Status server

Status is infrastructure-first: you declare what you have, and Status works out what to
check. Everything here is done over the **API or the admin UI** — you never need shell access
to the Status server, and you never restart it. (Installing an *agent* does need shell on the
host being monitored — that is the one exception, and it is a one-time step per machine.)

> **Two rules dominate everything below.**
>
> 1. **Most wiring mistakes here fail as silence, not as errors.** A misrouted probe never
>    runs; a mistyped `ref` renders an empty node; a layout tile whose path was never emitted
>    is skipped without complaint. All three look like health. **Verify, don't assume** — see
>    *Verifying* at the end, and do it every time.
> 2. **Never restart the server to apply a change.** It drops every logged-in session, and it
>    is never necessary — saving config reloads the scheduler in the same call.

## Setup

```bash
export STATUS_URL=https://status.example.com
export STATUS_API_KEY=twk_…
```

## Ask the server what it supports

```bash
curl -s -H "X-API-Key: $STATUS_API_KEY" "$STATUS_URL/api/capabilities"
```

Returns probe types, states, param and output types, the widget lists per renderer (with the
`both` set you should default to), tile sizes, the service-type catalog and every installed
probe id — read from **that** server, so it beats any list in these files if they disagree.
Do this before trusting documentation, including this skill.

## Reference files

Read these on demand — they are the authoritative detail, not summaries.

| File | Covers |
|---|---|
| `references/getting-started.md` | **Start here for a new board.** The right setup order, service types, agent approval, first probes, thresholds. |
| `references/infographics.md` | Custom SVG probe cards — `template.svg` + `bindings.yml`, the full binding vocabulary. |
| `references/infrastructure-yml.md` | **Every top-level section**, field by field: `hosts`, `projects`, `dependencies`, `sites` (floor plans), `thresholds`, `defaults`, agent policies. |
| `references/writing-probes.md` | The full probe-authoring guide: `probe.yml`, `check.js`, the sandbox APIs, `streamValues`, templated paths, actions, tree-attached logs, `scriptResult`, thresholds, worked examples. |
| `references/widgets.md` | **Which widgets render where** — the probe card knows 10, the topology view 33, only 5 overlap. Fields per widget, tile spans. |
| `references/probe-sandbox.md` | The sandbox contract and the full param-type table. |
| `references/probes.md` | Probe kinds, local vs remote, how binding works. |
| `references/credentials-store.md` | Credential types (`bearer`, `basic`, `header`, `oauth2`, `tls`, `ssh`) and wiring them into probes. |
| `references/notifications.md` | **Alerting** — Telegram bot, webhooks, routing. Read before assuming a red reaches anyone. |
| `references/icons.md` | The icon set for hosts, apps, services and types. |
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
| **Project** | A business-concern grouping that becomes a tab. |
| **App** | A deployable unit users care about. Belongs to a project, contains services. |
| **Host** | A machine. Has an address and optional labels. Rolls up from its services, and carries host-level probes of its own. |
| **Service** | A running process of an app, on a host. Status derives from its probes. |
| **Dependency** | An external third party, with a `consumers` list naming which apps degrade with it. |
| **Probe** | The actual check. `HTTP_HEALTH`, `HTTP_JSON`, `TCP_CONNECT`, `DOCKER`, `SCRIPT`, `MAPPED_JSON`. |

Two independent trees exist and it matters which one you mean:

- **`Agents / <host> / <probe name>`** — the physical tree, built from `hosts:`. Probes
  actually live here and history is keyed here.
- **`projects:`** — a logical view that owns nothing. It `ref`s into the physical tree by path
  string. A project tab is a set of pointers.

## Changing configuration

`infrastructure.yml` declares hosts, projects, dependencies, sites, thresholds and agent
policies — see `references/infrastructure-yml.md` for every field.

Config is **fully scriptable**:

```bash
K="X-API-Key: $STATUS_API_KEY"

curl -s -H "$K" "$STATUS_URL/api/infrastructure/config" > infra.json   # read
#   … edit infra.json …
curl -s -X POST -H "$K" -H 'Content-Type: application/json' \
     -d @infra.json "$STATUS_URL/api/infrastructure/config"            # write
```

A successful write does three things in one call: saves, calls `probeScheduler.reload()` so
the change is live immediately, and records a config-history entry. **No restart, no file
access, no waiting.**

```jsonc
{ "status": "ok", "message": "Configuration saved and reloaded" }
```

Failures come back as real status codes — `409` if the config path is not writable, `400` if
the save failed — with `{"error": {"code", "message"}}`. So `response.ok` means what it says
on this endpoint.

Two companions worth knowing:

| Endpoint | Gives you |
|---|---|
| `GET /api/infrastructure/types` | The service-type catalog with param metadata — what `type:` values exist |
| `GET /api/infrastructure/hosts` | Host names, for resolving where a probe would run |

All of it requires `STATUS_ADMIN` or `INFRA_ADMIN`. Humans can equally use the admin UI at
`/admin/infrastructure`, which drives the same endpoints.

> ⚠️ **A write is a full round-trip, and the round-trip is lossy.** You `GET` the whole
> config, edit it, and `POST` the whole thing back — and the save re-serialises from the
> object graph. That **strips every comment**, and drops any field the model does not
> represent. Keep notes about your setup somewhere that survives a save, and prefer editing
> the smallest thing you can rather than round-tripping a config you did not author.

### ✅ Dry-run it first

```bash
curl -s -X POST -H "$K" -H 'Content-Type: application/json' \
     -d @infra.json "$STATUS_URL/api/infrastructure/config?dryRun=true"
```

Writes nothing, reloads nothing, records no history — and answers the questions that
otherwise only production can:

```jsonc
{
  "status": "ok_with_warnings",
  "dryRun": true,
  "probes": { "wouldGenerate": 54 },
  "refs":   { "resolved": 61, "missed": ["Public Site / Web / API -> Agents / app-01 / Web Reachabl"] },
  "agents": { "bound": 12, "unknown": ["SSH -> agent 'app-03.example.com'"] },
  "warnings": ["1 project ref(s) resolve to nothing and will render as empty nodes. …"]
}
```

**Do this before every config change.** A missed ref and a phantom agent are traps 1 and 2,
and this is the only way to see them without applying the change to a live board first.

> ⚠️ **The save does not refuse a broken config.** It applies whatever you send. It now
> *reports* what went wrong — the same `refs`/`agents`/`warnings` block as the dry run, with
> `status: "ok_with_warnings"` — but it does not stop. **Read the response**; `"ok"` alone
> means the write landed, not that the result works.
>
> On builds before 2026-08-27 the response was `"Configuration saved and reloaded"` and
> nothing else, whatever the outcome. If that is all you get back, verify manually via
> *Verifying* at the end.

> 💡 **Older deployments:** before 2026-08-27 these lived at `/admin/infrastructure/api/config`
> and were unreachable with an API key (a routing bug returned a 302 to the login form).
> If `/api/infrastructure/config` 404s, you are on an older build — use the admin UI.

### ⚠️ Renaming vs editing a probe

`ProbeScheduler.reload()` keys probes by id and reuses the existing `Probe` object when the
name is unchanged:

```java
if (existing != null && existing.getName().equals(pc.getName())) updated.put(id, existing);
```

So a probe whose **name is unchanged while its config changed keeps the old config**. Editing
a `target:`, `port:` or `interval:` in place does nothing, silently, and the board keeps
showing the old check passing. **Rename the probe** and it registers fresh.

### Ghost probes after a rename or delete

A renamed or deleted probe lingers, by design: `/api/tree` unions scheduled probes with
history, so a name still in the history store renders at its last value even though nothing
schedules it. Clear it:

```bash
curl -X POST -H "X-API-Key: $STATUS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"items":[{"name":"Agents / app-01.example.com / Old Probe Name","type":"probe"}]}' \
  "$STATUS_URL/api/admin/storage/delete"     # -> {"deleted":1}
```

## Service types — let Status write the probes

**This is the product's premise, and the thing most setups skip.** Put a `type:` on a service
and its probes are generated for you:

```yaml
services:
  - name: Database
    type: postgres
    vars: { port: 5432 }        # substituted into the type's ${port} placeholders
```

**22 built-in types** ship — `postgres` `traefik` `keycloak` `grafana` `jenkins`
`spring-boot` `github-actions` `dockerhub` `statuspage` `vercel-status`, plus third-party
status pages (`anthropic-status`, `cloudflare-status`, `github-status`, `jira-status`,
`openai-status`, …). List what a server actually has with `GET /api/infrastructure/types`.

Custom types sit beside the built-ins and are reusable across every service of that kind.
**Write a type before you write the same probe twice.** Hand-written probes are the escape
hatch, not the default. Full setup order: `references/getting-started.md`.

🚨 **A type that fails to parse is silently absent**, and a `type:` naming an absent type
generates nothing — no probes, no error, indistinguishable from a service you never
configured. Confirm with `GET /api/infrastructure/types` before assuming your config is
wrong. Builds before 2026-08-27 loaded only 15 of 22, `postgres` among the missing.

## Templated paths — one probe, N instances

A `{var}` in an `output:` path matches any segment, and **every `{var}` introduces a level of
the tree**:

```yaml
output:
  - path: "{host}/{container}"          type: group   label: "{container}"
  - path: "{host}/{container}/cpu"      type: percent label: CPU
```

`check.js` emits the concrete paths; the captured values are referenceable in `label`, `i18n`
and in layout `group:` bindings. This is how one probe covers every container, disk or light
without listing them.

⚠️ **A `/` inside a name must be escaped `\\/`** — an unescaped mount point like
`/var/lib` silently becomes extra tree levels instead of one node.

## Actions — buttons on the board

A probe can attach operator actions to a stream path: Restart, Turn On, Flush Cache. They
render inline in the tree next to the thing they act on, and they can take typed parameters
with real input widgets.

```yaml
output:
  - path: "{host}/{container}/restart"
    type: action
    label: Restart

  - path: "{light}/setColor"
    type: action
    label: Set Color
    params:
      - { name: hue, type: number, label: Hue, min: 0, max: 360, widget: hue-slider }
```

Declare it in `output:` with `type: action`, register it in `check.js` with `ctx.action.add`,
and handle the invocation. This is what turns a read-only board into a control panel — see
*Actions* in `references/writing-probes.md` for the three-part contract.

## Dashboards — designing what a probe SHOWS

A probe's **`layout:`** block in `probe.yml` decides how its values render. Without one, an
expanded probe is plain `key: value` rows. With one, each value becomes a tile.

```yaml
layout:
  - tile: 1x1
    widget: gauge          # card-safe; see references/widgets.md
    path: usedPercent      # a stream path this probe emits
    label: Disk
    max: 100
  - tile: 2x1
    widget: chart
    path: responseMs
    label: Response Time
    group: "{host}"        # bind to a {var} expansion; omit for root-level summary tiles
```

**Three rules decide whether a tile appears at all:**

| Rule | Consequence |
|---|---|
| `path` must be a path the probe actually emits in `streamValues` | A tile whose path was never emitted is **skipped silently** — no error, no empty tile |
| The `''` (empty) path is the **primary** value | It drives the inline sparkline on the probe row; omit it and the row renders flat |
| `group` binds a tile to a `{var}` expansion | Each concrete instance gets its own tile grid. Root-level summary tiles must omit `group` |

Skip-silently is deliberate — it lets one layout serve heterogeneous instances. It also means
a typo in `path` looks exactly like "this instance doesn't have that value".

### Two ways to edit a layout

| Route | How |
|---|---|
| **Probe IDE** (`/ide`) | The plate editor: pick a widget from the category strip, drop it on the grid, fill its typed fields. The intended path for a human. |
| **API** | `GET /api/ide/probe-definition?id=<probe>` → edit the YAML → `POST /api/ide/probe-definition` with `{id, definition}`. `POST /api/ide/probe-save` writes `check.js`; `POST /api/ide/probe-svg` writes the infographic. |

Both need `STATUS_ADMIN` or `INFRA_ADMIN` — see `status-server-api` for why that gate matters.

### ⚠️ The widget vocabulary — two renderers, different names

The same `layout:` block feeds two renderers that accept **different widget names**:

| Works in | Widgets |
|---|---|
| **Both** — default to these | `value` `gauge` `chart` `bar` `bars` |
| **Probe card only** | `color` `grid` `image` `list` `multizone` |
| **Topology view only** | `action` `badge` `cake` `chart-billboard` `compass` `delta` `flame` `fluid-tank` `heatmap` `hourglass` `log` `matrix-rain` `node` `odometer` `orbital` `oscilloscope` `paper-stack` `progress-circle` `radar` `split-flap` `split-flap-board` `stacked-bars-tower` `text` `thermometer` `ticker-tape` `tray` `uptime-strip` `vu-meter` |

**The panel is 4 units wide** — a wider span is clamped. Sizes: `1x1` `2x1` `1x2` `2x2` `3x1`
`3x2` `4x1` `4x2` (the catalog also uses `4x3`).

Each widget takes its own fields beyond `path`/`label` — `chart` has
`style: blocky|smooth|ridge`, `badge` has `shape: pill|hex|shield|stamp`. **Full field list
per widget, and which renderer each belongs to: `references/widgets.md`.**

For an operational board, pick what makes a bad number obvious: `gauge` for a bounded ratio,
`chart` where the trend is the story, `value` when the number speaks for itself. Note
`uptime-strip` — the obvious pick for pass/fail history — is topology-only; on a card use a
`chart` of a 0/1 stream instead.

Only 11 of ~45 shipped probes define a `layout:` at all. Plain key/value rows are a fine
default; add a layout when a probe emits enough values that rows stop being readable.

### Or draw the card yourself

For a designed, single-purpose card — a bar, a needle, a fill level, anything the widget set
cannot draw — use an **infographic**: `template.svg` with `id`s on the live parts, plus a
`bindings.yml` mapping values onto them via `map` / `scale` / `threshold`. No build, no
registry, live over `POST /api/ide/probe-svg`. Only 1 of ~45 shipped probes uses this, so it
is where the headroom is. Full vocabulary: `references/infographics.md`.

## The probe catalog

Each catalog probe is a directory holding `probe.yml` (metadata, typed params, declared
outputs, dashboard layout) and `check.js` (the check). ~40 ship in the box: HTTP/TCP/SSL,
Docker, host metrics, databases, CI, and a long tail of third-party `*-status` pages. List
what is installed with `GET /api/ide/probes`.

**Param types:** `url` · `hostname` · `port` · `string` · `text` · `int` · `number` ·
`boolean` · `select` · `duration` · `percent` · `bytes` · `timestamp` · `color` · `location` ·
`state` · `label` · `group` · `action` · `credential`

**Sandbox APIs** for `check.js`: `ctx.http.get` · `ctx.tcp.connect` · `ctx.socket.http` (Unix
sockets) · `ctx.shell.run` · `ctx.exec` · `ctx.action.add` · `ctx.log` · `ctx.host` ·
`ctx.util` · `ctx.params`

**States:** `OK` · `WARNING` · `ERROR` · `UNKNOWN` — it is `WARNING`, not `WARN`.

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

`http-endpoint` records `responseMs`, so it is a genuine latency probe rather than up/down —
give every public endpoint one. Full contract, including templated `{var}` paths, actions,
tree-attached logs and `scriptResult` service discovery: `references/writing-probes.md`.

**Test before you save:** `POST /api/ide/test` runs a script server-side;
`POST /api/ide/test-on-agent` runs it on a real agent and returns an id to poll at
`GET /api/ide/test-on-agent/{id}`. Always do the agent one — see trap 4.

## 🚨 Six traps that fail as SILENCE

| # | Trap | Rule |
|---|---|---|
| 1 | **Decomposed `host:`/`port:` binds the probe to an agent named after the HOST.** On a host with **no agent installed**, the probe is assigned to an agent that does not exist and simply never runs — no result, no warning, no red. | On an agentless host every probe MUST use `target:` (including `target: tcp://host:port`). That leaves the agent null, so the **server** runs it. |
| 2 | **A project `ref` that misses resolves to an empty node** — the resolver returns null silently. You get a blank card, not an error. | Cross-check every `ref` against the live `/api/tree`. Mind the spaces around the `/` separators. |
| 3 | **`docker-services` refs use the CONTAINER name, not `<stack>/<service>`.** The `<stack>/<service>` prefix exists only for `streamValues`, `ctx.action` and `ctx.log.ref`. | Ref them as `Agents / <host> / Docker / <containerName>`. |
| 4 | **The server has no JS sandbox** — 7 native checkers only. Any JS catalog probe run **server-side** degrades to `HTTP_HEALTH`. An `ssl-certificate` probe will report "HTTP 200" while checking no expiry whatsoever. | Name server-side probes for what they do — "Web Reachable", not "SSL Certificate". A real cert or Docker probe needs an **agent on the box**. |
| 5 | **A widget the probe card does not know renders NOTHING.** the card's renderer has no fallback branch, so a tile naming a topology-only widget (`flame`, `odometer`, `uptime-strip`, …) produces an empty cell — no error, no warning, no log line. Same for a `path` the probe never emits. | Keep board tiles inside `value` `gauge` `chart` `bar` `bars` unless you deliberately want a card-only widget. See the vocabulary table above. |
| 6 | **An agent running `AGENT_READONLY=true` refuses shell.** A `SCRIPT` probe needing a shell can only ever return "requires shell access" — a permanent red. | Never ship a red that cannot go green. It trains people to ignore red, which is the only thing a status board is for. |

## Verifying — do this, every time

All of it over the API. No shell, no log files.

```bash
K="X-API-Key: $STATUS_API_KEY"

# 1. anything not OK right now
curl -s -H "$K" "$STATUS_URL/api/status"

# 2. the authoritative tree — confirms a ref resolved and a probe exists where you think
curl -s -H "$K" "$STATUS_URL/api/tree"

# 3. 🚨 the trap-1 signature: a probe with NO history has NEVER run
curl -s -H "$K" "$STATUS_URL/api/probes/history/list"

# 4. recent state transitions
curl -s -H "$K" "$STATUS_URL/api/events"

# 5. one probe's series, to confirm it is producing values
curl -s -H "$K" "$STATUS_URL/api/probes/history?probe=<name>&resolution=5s"

# 6. failing things no incident covers yet — the triage queue
curl -s -H "$K" "$STATUS_URL/api/untracked-issues"
```

Step 3 is the one people skip. A probe can appear in the tree, look configured, and have
never executed once — that is trap 1, and the absence of a history entry is how you see it.

## See also

`status-server-api` — driving a live board: read surfaces, probe history, incidents, and the
role gate on `/api/ide/**`.
