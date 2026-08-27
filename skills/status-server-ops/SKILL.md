---
name: status-server-ops
description: Use when setting up, modelling or operating a Plaiiin Status server — declaring hosts/projects/services, using SERVICE TYPES to auto-generate probes, writing custom probes and actions, and designing what a probe SHOWS: dashboard layout, tiles, widgets (gauge, chart, bar, value) and custom SVG infographics. Also for project tabs, dependencies, sites/floor-plans, thresholds, agent policies and alerting — and when a probe reads green, empty or absent and you need to know whether it is actually running. Covers reading and writing infrastructure.yml over the API, its fields one by one, finding and removing abandoned history data, the check.js sandbox, the Probe IDE, and seven wiring mistakes that fail as SILENCE rather than as errors. Also covers the credentials store — how a probe authenticates to what it monitors. Your own API key lives in ~/.plaiiin/status-server/env; read that before asking anyone for one.
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

## API access — set once, never asked again

Both skills read `~/.plaiiin/status-server/env`. Put your server and key there and no session
needs to ask you for them. (This is *your* access to the API — not to be confused with the
**credentials store**, which holds the secrets probes use to reach the things they monitor.)

```bash
mkdir -p ~/.plaiiin/status-server && chmod 700 ~/.plaiiin/status-server
cat > ~/.plaiiin/status-server/env <<'EOF'
STATUS_URL=https://status.example.com
STATUS_API_KEY=twk_…
EOF
chmod 600 ~/.plaiiin/status-server/env
```

Load it in any shell:

```bash
set -a && . ~/.plaiiin/status-server/env && set +a
```

Environment variables of the same name win if already set, so a one-off override still works.
If the file is absent **and** the variables are unset, that is the only time you should be
asked for a key.

### Getting a key

| Route | How |
|---|---|
| **Admin UI** | Settings → **API keys** → *New key*. The raw key is shown **once** — copy it straight into the file above. |
| **API** (needs an existing key) | `POST /api/user/api-keys` with `{"name":"…"}` |

List or revoke yours with `GET /api/user/api-keys` and
`POST /api/user/api-keys/{id}/revoke`.

**A key inherits the roles of the user who minted it** — there is no per-key scoping. So the
account you are signed in as when you click *New key* decides what the key can do:

| Signed in as | Key can |
|---|---|
| an ordinary user | read state, read history, work with incidents |
| `STATUS_ADMIN` / `INFRA_ADMIN` | all of the above **plus** `/api/ide/**` — writing probe scripts that execute on every monitored host, and writing config |

Prefer a key minted by a non-admin account for anything ambient (dashboards, bots, a
long-running assistant session). Reach for an admin key only while authoring, and revoke it
after.


### Scoping a key to less than yourself

A key inherits its owner's roles by default. Pass `roles` to narrow it:

```bash
curl -s -X POST -H "$K" -H 'Content-Type: application/json' \
  -d '{"name":"dashboard","roles":["VIEWER","HISTORY_USER"]}' \
  "$STATUS_URL/api/user/api-keys"
```

Roles: `VIEWER` `HISTORY_USER` `HISTORY_CONFIG` `INCIDENT_RESPONDER` `INCIDENT_MANAGER`
`DRILL_RESPONDER` `DRILL_MANAGER` `PROBE_EDITOR` `STATUS_ADMIN` `INFRA_ADMIN`.

| Property | Behaviour |
|---|---|
| Omit `roles` | The key inherits everything you have — the historical default |
| Ask for a role you lack | Refused with `roles_not_held` and the list of what you do have |
| Owner loses a role later | Every key they minted loses it too, at the next request |
| A scoped key mints a key | Bounded by **its own** scope, not its owner's — it cannot climb out |

The intersection is computed per request rather than frozen at mint time, which is what makes
the last two rows true.

**Use this for anything ambient.** A key in a config file, a dashboard, a bot or a
long-running assistant session should be `VIEWER` + `HISTORY_USER`, not an admin key — an
admin key can `POST /api/ide/probe-save`, which executes JavaScript on every monitored host.
Keep an admin key for authoring sessions and revoke it after.

⚠️ Servers built before 2026-08-27 have no `roles` column; a `roles` list is ignored there and
the key inherits everything. Check with `GET /api/user/api-keys` — scoped keys report their
`roles`.

⚠️ **If a key returns `401 {"error":"User not found"}`**, the key itself is fine — the account
that owns it no longer resolves in the identity directory. That happens when the directory is
re-imported and user ids change. Mint a fresh key as a current user; revoking and re-issuing
against the old account will not help.

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
| `references/credentials-store.md` | **Probe secrets** — the six credential types, encryption, agent delivery, admin API, audit log. |
| `references/notifications.md` | **Alerting** — Telegram bot, webhooks, routing. Read before assuming a red reaches anyone. |
| `references/icons.md` | The icon set for hosts, apps, services and types. |
| `references/probe-active-folder.md` · `references/probe-vs-command.md` | Active-folder mechanics; when to write a command instead of a probe. |
| `references/infrastructure-model.md` | The model in prose — hosts, host-agents, agent security, agent policies. |
| `status-server-api` → `references/api-surface.md` | **Every endpoint** (172) grouped by area — workflows, sites, drills, agents, IAM, topology and the rest. |

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
set -a && . ~/.plaiiin/status-server/env && set +a   # STATUS_URL + STATUS_API_KEY
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

### ✅ Editing without losing anything

`POST /api/infrastructure/config` goes through the object model and **loses comments and any
field the model does not know**. To make a surgical edit, use the raw path instead — what you
send is what lands on disk:

```bash
curl -s -H "$K" "$STATUS_URL/api/infrastructure/config/raw" -o infra.yml
#   … edit infra.yml — comments, ordering and formatting all survive …
curl -s -X POST -H "$K" -H 'Content-Type: text/plain; charset=utf-8' \
     --data-binary @infra.yml "$STATUS_URL/api/infrastructure/config/raw"
```

The YAML is parsed first as a guard: a body that does not parse is refused with
`invalid_yaml` and the file is left untouched. `?dryRun=true` works here too, and the response
carries the same `refs`/`agents`/`warnings` report.

**Prefer this for any edit to a file a human wrote.** Use the object endpoint when you are
generating a config wholesale and there is nothing to preserve.

⚠️ Older builds have no `/config/raw`; a `404` means you are on one, and the object endpoint is
your only option there.

> ⚠️ **The object endpoint's write is a full round-trip, and the round-trip is lossy.** You `GET` the whole
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

### 🚨 Templated paths do NOT give you one card per instance

This is the decision to get right BEFORE writing the probe, because getting it wrong costs N×
the requests and the only symptom is a bill nobody sees.

| You want | Use | Result |
|---|---|---|
| One card **per instance** on the tab | **`scriptResult.services`** | Each entry becomes its own service node with its probes as children — a card each |
| One card with a **group per instance** inside it | **templated `streamValues` paths** | Groups render inside the single probe's card |

A templated `{var}` path is a level of the tree **inside one probe's card**. Those child nodes
are NOT addressable from `projects:` and `/api/tree` shows only the probe node — so a project
`ref` cannot reach them, and no amount of config splits them into cards.

`scriptResult.services` is what does that, and it is not exotic: **`docker-services` uses it for
every container.** One probe, one fetch, a node per container that a `ref` can address.

```js
return {
  state: 'OK',
  message: rows.length + ' cantons',
  scriptResult: {
    services: rows.map(r => ({
      name: r.canton,
      probes: [
        { name: '7 days',  status: 'OK', message: '' + r.d7 },
        { name: '30 days', status: 'OK', message: '' + r.d30 }
      ]
    }))
  }
}
```

Wire it with ONE service whose single probe returns the children — `StatusTree` expands them
(`AgentController.convertScriptServices` builds the nodes):

```yaml
- name: Cantons
  services:
    - name: Cantons
      type: custom
      probes:
        - name: Cantons
          probe: feuerinfo-cantons
          agent: feuerinfo.ch
```

**A real session got this wrong**, concluded from one `/api/tree` walk that per-instance cards
were impossible, and shipped 26 probes fetching the same JSON — then filed the "missing" fan-out
primitive as a feature request. It had been there all along, in the probe the same board was
already running. If you are about to report that the platform cannot produce N cards from one
fetch: it can, and this is how.

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

⚠️ **`test-on-agent` requires the script SOURCE inline** — `{id, agent, params}` alone returns
`{"error":"agent and source required"}`. There is no way to say "run the installed probe on that
agent"; you must read the source and hand it straight back. Two consequences: reading
`probe-source?name=<id>` first is a required step, not an optional one, and what you test is a
COPY — if it has drifted from what is deployed, you are testing the wrong artefact.

⚠️ **An IDE write can return `{"status":"ok"}` and persist nothing.** During a server restart the
write path accepts and drops. `probe-create` and `probe-definition` both returned `ok` while
`probe-definition?id=…` read back `{"error":"Definition not found"}` — which reads exactly like
"probe authoring is broken on this build" and is not. **Always read back after writing**, and if a
write vanishes, check whether the server is healthy before concluding the API is a no-op.

### 🚨 Never put a changing value in a node name

A node's **name is its identity** — history is keyed by the full path. So a group named after
its own contents starts a brand-new history series every time that content count changes:

```js
// ✗ forks history on every added router
services.push({ name: 'HTTP Routers (' + routers.length + ')', probes: p })

// ✓ stable identity
services.push({ name: 'HTTP Routers', probes: p })
```

The orphaned series are the small cost. The real one is that **a chart can never show more
than the period since the count last changed** — add a container and the graph resets to
empty. The count is redundant anyway: the children are right there.

Same rule for anything else that moves — a timestamp, a version, a percentage, a hostname
that might be renamed. Put it in the value or the message, never in the name.

## Storage — finding and removing abandoned history

Every probe stream gets its own history series, and they accumulate. Series belonging to
nothing are easy to create by accident: rename a probe, or name a group node after something
that changes, and the old series is orphaned forever.

```bash
# what is abandoned?
curl -s -H "$K" "$STATUS_URL/api/admin/storage/stale?days=30"

# remove it — DRY RUN by default, returns the same report either way
curl -s -X POST -H "$K" "$STATUS_URL/api/admin/storage/cleanup?days=30&dryRun=false"
```

```jsonc
{ "olderThanDays": 30, "staleCount": 162, "staleBytes": 484702208,
  "totalSeries": 897, "totalBytes": 3203792896, "dryRun": true, "deleted": 0,
  "series": [ { "name": "…", "bytes": 12478464, "lastWritten": "…", "ageDays": 137 } ] }
```

**Stale means two things at once**: nothing has written to the series for `days`, **and** no
scheduled probe claims it. Either test alone is wrong — probes publish runtime children that
no config declares (a node per container, per route) and those are live; and a probe on a long
interval is quiet, not abandoned.

The same control is in the admin UI under **Storage** — set a day threshold, *Scan*, then
delete. `GET /api/admin/storage` lists every series with its size if you want to prune by hand
instead; `POST /api/admin/storage/delete` removes named ones.

Cleanup requires `STATUS_ADMIN` or `INFRA_ADMIN`, and **is not reversible** — take a copy of
the history directory first if the data might matter.

## Secrets — how a probe authenticates to what it monitors

Probes that check an authenticated endpoint do **not** carry the secret in `infrastructure.yml`.
Secrets live in an encrypted credentials store and are referenced by name:

```yaml
probes:
  - name: Server Status
    probe: http-endpoint
    target: https://api.example.com/v1/servers
    credentials: acme-prod          # <- a name, never the secret
```

**Six credential types**, each strongly typed:

| Type | Fields | For |
|---|---|---|
| `bearer` | `token` | REST APIs |
| `basic` | `username`, `password` | Internal services, Jenkins, databases |
| `header` | `headerName`, `headerValue` | APIs with a custom auth header |
| `oauth2` | `clientId`, `clientSecret`, `tokenUrl`, `scope` | ⚠️ **storage only — see below** |
| `tls` | `certPem`, `keyPem`, `caPem?` | Mutual TLS / client certificates |
| `ssh` | `privateKey`, `passphrase?`, `username` | Remote command execution |

Manage them in **Settings ▸ Credentials**, or over the API (needs `INFRA_ADMIN`/`STATUS_ADMIN`):

| | |
|---|---|
| `GET /api/admin/credentials` | List — **metadata only**, no secrets |
| `POST /api/admin/credentials` | Create `{name, type, data:{…}}` |
| `PUT`/`DELETE /api/admin/credentials/{id}` | Update / remove |
| `GET /api/admin/credentials/{id}/log` | Who accessed it, and when |

Reads return **masked** values (`eyJh****…****gIs`) — a stored secret cannot be retrieved
through the API, only used.

### ⚠️ `oauth2` is stored, not redeemed

Nothing in the platform exchanges an `oauth2` credential for a token. It is injected into
`ctx.params.credentials` exactly as stored — `{clientId, clientSecret, tokenUrl, scope}` — so a
probe must perform the `client_credentials` exchange itself with `ctx.http.post`.

That is workable but rarely wise, because **the sandbox has no state between runs**. There is
nowhere to cache a token, so a probe on a 60s interval performs ~1,440 token exchanges a day.
Many identity providers rate-limit or bill that, and the extra round-trip inflates
`responseMs`, which is otherwise a genuine latency signal.

**Prefer a `bearer` credential** with a token you rotate out of band, unless the token's
lifetime is too short for that to be practical. If you do hand-roll the exchange, use a long
`interval:` and accept the latency skew.

### Authoring a probe that takes one

Declare a `credential` param and read it from `ctx`:

```yaml
params:
  - name: credentials
    type: credential
    credential_type: bearer     # restricts which stored credentials are offered
    configurable: true
```

```js
var headers = {}
if (ctx.params.credentials) {
  if (ctx.params.credentials.token) {
    headers['Authorization'] = 'Bearer ' + ctx.params.credentials.token
  } else if (ctx.params.credentials.headerName) {
    headers[ctx.params.credentials.headerName] = ctx.params.credentials.headerValue
  }
}
var res = ctx.http.get(ctx.params.url, headers)
```

### How the secret reaches an agent

The server sends only the credential **name** in the probe assignment. The agent then fetches
the value over an Ed25519-signed request, holds it in memory with a 5-minute TTL, and **never
writes it to disk**. Every access is recorded in the audit log.

🚨 **`STATUS_CREDENTIALS_KEY` must be set in production.** It is the AES-256-GCM master key
(PBKDF2-SHA256, 600k iterations) for the credentials database. Without it the server falls
back to a **dev key** and merely logs a warning — meaning your stored secrets are encrypted
with a value that is not secret. Check for `STATUS_CREDENTIALS_KEY not set` in the startup log.

Full detail: `references/credentials-store.md`.

## 🚨 Seven traps that fail as SILENCE

| # | Trap | Rule |
|---|---|---|
| 1 | **Decomposed `host:`/`port:` binds the probe to an agent named after the HOST.** On a host with **no agent installed**, the probe is assigned to an agent that does not exist and simply never runs — no result, no warning, no red. | On an agentless host every probe MUST use `target:` (including `target: tcp://host:port`). That leaves the agent null, so the **server** runs it. |
| 2 | **A project `ref` that misses resolves to an empty node** — the resolver returns null silently. You get a blank card, not an error. | Cross-check every `ref` against the live `/api/tree`. Mind the spaces around the `/` separators. |
| 3 | **A probe's runtime children hang off the HOST, not off the probe.** `docker-services` publishes one node per container via `scriptResult.services`, and those land at `Agents / <host> / <containerName>` — **not** under the probe's own name. Refs written as `Agents / <host> / Docker / <container>` match nothing and render empty. (The `<stack>/<service>` form is a `streamValues` path, used by `ctx.action` and `ctx.log.ref` — never a ref.) | Copy the exact path from `/api/tree`. Never assemble a ref by hand from the probe name. |
| 4 | **The server has no JS sandbox** — 7 native checkers only. Any JS catalog probe run **server-side** degrades to `HTTP_HEALTH`. An `ssl-certificate` probe will report "HTTP 200" while checking no expiry whatsoever. | Name server-side probes for what they do — "Web Reachable", not "SSL Certificate". A real cert or Docker probe needs an **agent on the box**. ⚠️ **Any HTTP target field in the config entry (`target:` OR `url:`) hands the probe to the server**, even with `agent:` set. For a CUSTOM JS probe the symptom is a hard `No script source for probe`, because the server has no copy of your script. Give the config entry only `name`/`probe`/`agent`/`params`, and put the URL in the probe.yml param's `default:` — that is what makes it run on the agent. |
| 5 | **A widget the probe card does not know renders NOTHING.** The card's renderer has no fallback branch, so a tile naming a topology-only widget (`flame`, `odometer`, `uptime-strip`, …) produces an empty cell — no error, no warning, no log line. Same for a `path` the probe never emits. | Keep board tiles inside `value` `gauge` `chart` `bar` `bars` unless you deliberately want a card-only widget. See the vocabulary table above. |
| 6 | **A redeploy can overwrite config and the probe catalog.** If your deployment ships `infrastructure.yml` and the probe directory — most do, and some sync the probe folder with `--delete` — then a change made over the API or in the Probe IDE survives exactly until the next deploy, then vanishes with no error. It looks like the server "reverted" or lost your write. | Find out what your deployment ships before relying on an API change. Whatever it ships is the source of truth; put lasting changes there. See *Where a change actually lives* below. |
| 7 | **An agent running `AGENT_READONLY=true` refuses shell.** A `SCRIPT` probe needing a shell can only ever return "requires shell access" — a permanent red. | Never ship a red that cannot go green. It trains people to ignore red, which is the only thing a status board is for. |

## Where a change actually lives

A live edit and a deployed file are not two views of one thing. **If your deployment ships a
file, that file wins the moment someone deploys.**

| Change | Live immediately | Survives a redeploy |
|---|---|---|
| `POST /api/infrastructure/config` | ✅ | ❌ **if** your deployment ships `infrastructure.yml` |
| Probe authored in the IDE (`probe-save`, `probe-definition`) | ✅ | ❌ **if** it ships the probe directory — especially when synced with `--delete` |
| Credential in the store | ✅ | ✅ — separate database, not usually shipped |
| Probe history | ✅ | ✅ — a data volume |

So the working loop is: **iterate over the API, then persist the result wherever your
deployment reads from.** A probe that exists only in the IDE is one deploy from gone, and the
symptom is `No script source for probe` — the config still references a probe id whose folder
no longer exists.

If a change "keeps reverting", look for a deployment before you suspect the server.

### ⛔ Do NOT deploy to apply a config or probe change

The API already applied it, live, without dropping a session. The repo commit is for surviving
the **next** deploy — it is not what makes the change take effect, and deploying to "publish" it
is both unnecessary and actively harmful:

| | |
|---|---|
| A deploy **restarts the server** | Every logged-in session drops, and the board loses its in-memory latest-result map |
| A deploy **overwrites live config from the repo** | If the repo is behind your API changes, the deploy silently reverts them |

A session did exactly that: applied config over the API, committed an *earlier* shape to the
repo, then ran a deploy "to publish it" — and watched the deploy copy the older repo config over
its own live work. It then spent an hour blaming the server for "losing writes".

**Deploy only for a change the API cannot express**: server code, the Dockerfile, compose. For
`infrastructure.yml` and probes the sequence is API first, commit second, deploy never.

## Verifying — do this, every time

All of it over the API. No shell, no log files.

```bash
set -a && . ~/.plaiiin/status-server/env && set +a   # STATUS_URL + STATUS_API_KEY
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
