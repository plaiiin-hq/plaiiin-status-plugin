---
name: status-server-api
description: Use when reading or driving a running Plaiiin Status server from Claude — checking what is currently red, reading the probe tree or a probe's history, opening/resolving/commenting on incidents, or authoring probes over the REST API. Covers X-API-Key auth, the /api/** boundary that makes wrong paths look like a login redirect, and the role gate on probe authoring.
---

# Driving a live Status board

This skill is for talking to a **running** Status server. For modelling infrastructure and
authoring probe definitions in config, see `status-server-ops`.

## Setup

```bash
export STATUS_URL=https://status.example.com
export STATUS_API_KEY=twk_…          # Settings → API keys, or POST /api/user/api-keys
```

Every call carries the key as a header:

```bash
curl -s -H "X-API-Key: $STATUS_API_KEY" "$STATUS_URL/api/tree"
```

### ⚠️ The `/api/**` boundary — the confusing failure

`ApiKeyAuthFilter` is registered **only** on `securityMatcher("/api/**")`. A key presented
on any other path is not merely rejected — the request falls through to the browser
security chain and you get a **302 to the login form**, which reads like a broken key or a
down server. It is neither: it is the wrong path.

If a call redirects to `/app/login`, check the path before you check the key.

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

## Optional: the MCP server

Status ships an MCP server (`mcp/status_server.py`, 15 tools) if you would rather have tools
than curl. It reads `STATUS_URL` and `STATUS_API_KEY` from the environment.

| Group | Tools |
|---|---|
| State | `get_system_status`, `get_service_tree`, `get_server_info`, `list_probes`, `get_probe_history`, `get_recent_events`, `get_untracked_issues` |
| Incidents | `list_incidents`, `get_incident`, `create_incident`, `resolve_incident`, `add_incident_comment` |
| Other | `list_drills`, `list_users`, `get_my_identity` |

It is **read-only apart from incidents** — it deliberately does not expose probe authoring
even though the REST API does. For authoring, use `/api/ide/*` directly.

## See also

`status-server-ops` — the infrastructure model, probe catalog authoring, applying config
changes without dropping sessions, and the five wiring traps that fail as silence.
