---
name: status-server-api
description: Use when reading or driving a running Plaiiin Status server from Claude — checking what is currently red, reading the probe tree or a probe's history, opening/resolving/commenting on incidents, or authoring probes and their dashboard layouts (widgets, tiles) over the REST API. Covers X-API-Key auth, the /api/** boundary that makes wrong paths look like a login redirect, and the role gate on probe authoring. Also covers the credentials store — how a probe authenticates to what it monitors. Your own API key lives in ~/.plaiiin/status-server/env; read that before asking anyone for one.
---

# Driving a live Status board

This skill is for talking to a **running** Status server. For modelling infrastructure and
authoring probe definitions in config, see `status-server-ops`.

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

### ⚠️ The `/api/**` boundary — the confusing failure

`ApiKeyAuthFilter` is registered **only** on `securityMatcher("/api/**")`. A key presented
on any other path is not merely rejected — the request falls through to the browser
security chain and you get a **302 to the login form**, which reads like a broken key or a
down server. It is neither: it is the wrong path.

If a call redirects to `/app/login`, check the path before you check the key.

Every JSON endpoint lives under `/api/**` — that invariant holds codebase-wide as of
2026-08-27. On older builds a few served JSON from outside it (notably the infrastructure
config, at `/admin/infrastructure/api/config`) and were unreachable with a key.

## Reference files

| File | Covers |
|---|---|
| `references/api-surface.md` | **Every endpoint** (172), grouped by area, generated from the server source, with 🔒 marking the role-gated ones. Start here to find something. |
| `references/api-endpoints.md` | Hand-written detail on the main endpoints — params and response shapes. |
| `references/endpoints.md` | The wider surface, including admin and agent routes. |

The tables below are the working subset; the references are authoritative.

## Start here: `GET /api/capabilities`

One request returns every vocabulary you need to write a valid config, read from **this**
server rather than from documentation that may not match it:

```bash
curl -s -H "$K" "$STATUS_URL/api/capabilities"
```

| Key | Contains |
|---|---|
| `probeTypes` · `probeStates` · `dataTypes` | `HTTP_HEALTH`…`MAPPED_JSON`; `OK`/`WARNING`/`ERROR`/`UNKNOWN`; history types |
| `paramTypes` · `outputTypes` | Read from the installed catalog, so they describe what this server actually has |
| `widgets` | `card` · `plate` · **`both`** · `cardOnly` · `plateOnly` — see the note below |
| `tileSizes` · `panelWidthUnits` | Canonical spans; the panel is 4 units wide |
| `serviceTypes` | Which `type:` values exist — **check here first** if a `type:` seems to do nothing |
| `probeCatalog` | Every installed probe id |

⚠️ **Use `widgets.both`** for tiles on the probe card. A widget the card cannot render
produces an empty cell, silently — the response says so too.

If this endpoint 404s you are on a build from before 2026-08-27.

## Reading state

| Endpoint | Use |
|---|---|
| `GET /api/status` | Overall rollup — start here for "is anything wrong". |
| `GET /api/tree` | The **full** probe tree. The authoritative view: use it to confirm a `ref` actually resolved and a probe actually ran. |
| `GET /api/global` | Tab list / global SPA state. |
| `GET /api/hosts` | Hosts and their labels. |
| `GET /api/events` | Recent state transitions. |
| `GET /api/probes/history?probe=<name>&resolution=5s` | Time series for one probe. Resolutions step up (`5s`, `1m`, …) — ask for the coarsest that answers the question. |
| `GET /api/probes/history/list` | Which probes have history at all. **A probe with no history has never run** — that is the trap-1 signature from `status-server-ops`. |
| `GET /api/probes/snapshot` | Current values in one shot. |
| `GET /api/untracked-issues` | Things failing that no incident covers yet — the natural triage queue. |
| `GET /api/types` · `GET /api/active` · `GET /api/presence` | Probe types, active checks, who is online. |
| `GET /api/infrastructure/config` | The whole declared infrastructure — hosts, projects, dependencies, thresholds. |
| `GET /api/infrastructure/types` · `GET /api/infrastructure/hosts` | Service-type catalog with param metadata; host names. |

Probe names in the tree are **whitespace-sensitive path strings**:
`Agents / app-01.example.com / Web Reachable`. Copy them from `/api/tree` rather than
retyping — a near-miss returns empty, not an error.

## Incidents

```bash
# list
curl -s -H "X-API-Key: $STATUS_API_KEY" "$STATUS_URL/api/incidents"

# open
curl -s -X POST -H "X-API-Key: $STATUS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"title":"Checkout latency elevated","severity":"minor"}' \
  "$STATUS_URL/api/incidents"

# comment
curl -s -X POST -H "X-API-Key: $STATUS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"content":"Traced to the payments upstream.","type":"comment"}' \
  "$STATUS_URL/api/incidents/<id>/comments"

# resolve
curl -s -X POST -H "X-API-Key: $STATUS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"summary":"Upstream recovered; p99 back under 400ms."}' \
  "$STATUS_URL/api/incidents/<id>/resolve"
```

Severities follow the usual status-page vocabulary (`minor`, `major`, …). Prefer opening an
incident over letting a red sit unexplained — an unexplained red is how people learn to
ignore red.

## Writing configuration

`POST /api/infrastructure/config` with the full config object. It saves, reloads the scheduler
and records a history entry in one call — `200 {"status":"ok"}`, or `409`/`400` with
`{"error": {"code", "message"}}`. Requires `STATUS_ADMIN` or `INFRA_ADMIN`.

Add `?dryRun=true` to get the same report **without writing anything** — refs resolved and
missed, probes bound to agents that do not exist, how many probes the config would generate.
Do that before every change.

⚠️ A real save does not refuse a broken config; it applies it and reports the problems
alongside `status: "ok_with_warnings"`. Read the response body, not just the status code.
Details and the lossy round-trip caveat: `status-server-ops`.

## Probe authoring over the API

The Probe IDE's backend is fully scriptable under `/api/ide/*`:

| Endpoint | Use |
|---|---|
| `GET /api/ide/probes` · `GET /api/ide/list` | What is installed. |
| `GET /api/ide/probe-source` · `GET /api/ide/probe-definition` | Read a probe's `check.js` / `probe.yml`. |
| `POST /api/ide/probe-create` | New catalog probe. |
| `POST /api/ide/probe-save` · `POST /api/ide/probe-definition` | Write `check.js` / `probe.yml`. |
| `POST /api/ide/test` | Run a script server-side against sample params. |
| `POST /api/ide/test-on-agent` → `GET /api/ide/test-on-agent/{id}` | Run it **on a real agent** and poll the result. Async: the POST returns an id. |
| `GET/POST /api/ide/probe-bindings` | Which hosts a probe is bound to. |
| `GET/POST /api/ide/probe-svg` | The probe's infographic. |
| `GET/POST /api/ide/command-*` | The same surface for agent commands. |

To change what a probe **displays** rather than what it checks, edit the `layout:` block in
its definition: `GET /api/ide/probe-definition?id=<probe>` → edit → `POST` it back. The widget
vocabulary and each widget's fields are in the `status-server-ops` skill
(`references/widgets.md`).

**Always `test-on-agent` before `probe-save`.** A script that passes `test` server-side can
still fail on an agent — the server has no JS sandbox and silently degrades unsandboxed
probes to a plain HTTP check (trap 4 in `status-server-ops`).

### 🔐 These endpoints are role-gated, and that gate matters

`/api/ide/**` requires **`STATUS_ADMIN` or `INFRA_ADMIN`**. This is deliberate and it is not
bureaucracy: `POST /api/ide/probe-save` writes `check.js` into the catalog, and **the agents
on every host then execute it**. An API key that can reach these endpoints can run arbitrary
code on every machine the board monitors.

| Practice | Why |
|---|---|
| Mint a **separate, read-only key** for dashboards, bots and anything ambient | Read keys cannot reach `/api/ide/**` at all |
| Reserve admin-role keys for deliberate authoring sessions, and rotate them | The blast radius is every agent, not just the board |
| Never paste an admin key into a shared config, CI variable or chat | Same reason |

> **If your deployment predates 2026-08-26**, `/api/ide/**` carried no authorization beyond
> "authenticated", so *any* valid key could write executable probe scripts. Upgrade, then
> rotate every key that existed before the upgrade.

## Config is not writable over the API

`infrastructure.yml` cannot be written through the API by design — saving re-serialises the
file and erases every comment in it. Edit the file, then trigger the catalog watcher. See
`status-server-ops` → *Applying a change without a restart*.

## MCP server — not currently distributed

Status has an internal MCP server (15 tools: state, incidents, drills/users) built for its
chat responder. It is **not part of this plugin and not currently shipped to customers**, and
it is read-only apart from incidents. Everything below the *Setup* section works over plain
HTTP, so nothing in this skill depends on it. Ask your Plaiiin contact if you want it.

## See also

`status-server-ops` — the infrastructure model, probe catalog authoring, applying config
changes without dropping sessions, and the five wiring traps that fail as silence.
