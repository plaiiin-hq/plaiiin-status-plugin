# Setting up a Status board the right way

The order below matters. Decisions 1–3 are cheap now and expensive later.

## 0. The premise

**You declare what you have; Status works out what to check.** If you find yourself
hand-writing a probe for a Postgres or a Traefik, you have probably skipped step 2 — the
service-type catalog already knows how to check those.

## 1. Model the estate before writing any probe

Sketch `projects → apps → services → hosts` first, on paper if necessary.

- A **project** becomes a tab. Group by business concern, not by machine. "Trading Platform"
  is a project; `app-01` is not.
- An **app** is what a user would name if it broke. A **service** is a process of that app on
  a host.
- A **host** is a machine. Its own health (CPU, memory, disk, Docker) hangs off the host, not
  off any app.

The two trees are separate on purpose: probes live at `Agents / <host> / <probe>`, and
projects merely `ref` into that. Get the physical tree right and the tabs are cheap to
rearrange later.

## 2. Use service types — do not hand-write probes

Put a `type:` on a service and Status generates its probes:

```yaml
services:
  - name: Database
    type: postgres
    vars: { port: 5432 }
```

`postgres.yml` in the built-in catalog declares:

```yaml
name: PostgreSQL
icon: database
category: datastore
params:
  - { key: port, label: Port, default: "5432" }
probes:
  - name: Connection
    type: TCP_CONNECT
    port: ${port}
```

`${port}` is substituted from `vars`. **22 built-in types ship:**

`postgres` · `traefik` · `keycloak` · `grafana` · `jenkins` · `spring-boot` · `github-actions`
· `dockerhub` · `statuspage` · `vercel-status` · and the third-party status pages
(`anthropic-status`, `bitbucket-status`, `cloudflare-status`, `confluence-status`,
`digitalocean-status`, `github-status`, `google-cloud-status`, `google-workspace-status`,
`jira-status`, `npm-status`, `openai-status`, `reddit-status`).

### 🚨 Check the type actually loaded

`ServiceTypeCatalog` logs a load failure and carries on, so **a type that fails to parse is
simply absent** — and a `type:` naming an absent type generates no probes, with no error. On
the board that looks exactly like a service you never configured.

Always confirm before trusting a type:

```bash
curl -s -H "X-API-Key: $STATUS_API_KEY" "$STATUS_URL/api/infrastructure/types" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)), 'types loaded')"
```

That number should match the count of types your server ships. If a `type:` you set does
nothing, check this list first — before checking your config.

Deployments built before **2026-08-27** shipped 22 types of which **7 never loaded**
(`postgres`, `spring-boot`, `jenkins`, `grafana`, `github-actions`, `google-cloud-status`,
`google-workspace-status`) — including `postgres`, so the obvious first thing to try silently
did nothing. If your server reports 15, you are on such a build: upgrade, or write the probes
by hand until you do.

Custom types live beside the built-ins in the config path, so a type you write once is reusable
across every service of that kind. **Write a type before you write the same probe twice.**

## 3. Decide agent approval before installing any agent

Registration is **open** — an agent self-registers on first start. Everything after that
(heartbeats, commands) requires the agent to be *approved* and to sign requests with its
Ed25519 key.

`autoApproveAgents` defaults to **`false`**. That is the safe default: an unknown machine
cannot join your board by pointing an agent at it. Turn it on only for a trusted network, and
know that you did.

Approve from the admin UI, or `POST /api/agents/{name}/approve`.

## 4. Agent or no agent?

| Situation | Use |
|---|---|
| Nothing installed on the box | `target:` — leaves the agent null, so the **server** runs the check |
| Agent installed on the box | `host:`/`port:` decomposed form, or an explicit `agent:` |

🚨 The decomposed `host:`/`port:` form binds the probe to **an agent named after the host**. On
a host with no agent, that agent does not exist and the probe never runs — no result, no
error. On an agentless host, always `target:`.

An agent is required for anything that must run *on* the machine: real SSL expiry, Docker
container state, disk/CPU/memory, log tailing. A server-side JS probe silently degrades to a
plain HTTP check (see trap 4).

Installing an agent needs shell access **on that host**, using the agent installer from your
Status distribution. You do not need shell on the Status server itself — everything else in
this guide is API or admin UI.

## 5. Turn on `agentProbes` once

```yaml
agentProbes:
  enabled: true
  probes: [system-cpu, system-memory, system-disk, system-location]
  params:
    system-disk: { warn: 85, error: 95 }
```

Every approved agent now runs these with no per-host configuration. This is the cheapest
uniform coverage you will ever get; do it before adding hosts, not after.

## 6. Name probes as if you cannot rename them

The probe **name is the scheduler's reload key**:

- Change a probe's config but keep its name → the change **silently does nothing**.
- Change the name → it re-registers fresh, but its history starts over and it lingers on the
  board as a ghost until you delete it.

Nothing warns you at naming time. Name for what the check *does* ("Web Reachable"), never for
what you wish it did ("SSL Certificate") — see trap 4.

## 7. A sensible first set for a small estate

Per host, via `agentProbes`: `system-cpu`, `system-memory`, `system-disk`,
`docker-services` (if it runs containers).

Per public endpoint: `http-endpoint` — it records `responseMs`, so it doubles as your latency
probe. Give every public URL one.

Per certificate: `ssl-certificate` — **needs an agent** to genuinely check expiry.

Per datastore: the matching service type (`postgres`, …) rather than a hand-rolled TCP probe.

Third parties you actually depend on: add them under `dependencies:` with a `consumers:` list,
so an upstream outage visibly attaches to the apps it degrades rather than looking like your
fault.

## 8. Set thresholds once, centrally

```yaml
thresholds:
  - match: { probe: system-memory }
    warn: 80
    error: 90
  - match: { probe: system-disk }
    field: usedPercent
    warn: 85
    error: 95
```

Better than per-probe params because it applies estate-wide and lives in one place.

## 9. Verify before you believe it

Every step above can fail silently. After the first save:

```bash
K="X-API-Key: $STATUS_API_KEY"
curl -s -H "$K" "$STATUS_URL/api/tree"                    # do the refs resolve?
curl -s -H "$K" "$STATUS_URL/api/probes/history/list"     # 🚨 no history = NEVER RAN
curl -s -H "$K" "$STATUS_URL/api/status"                  # anything not OK?
```

The history check is the one people skip, and it is the only way to see a probe that was
configured, looks present in the tree, and has never executed once.

## The rule that governs all of it

**Never ship a red that cannot go green.** A permanently-failing probe — one needing shell on
a read-only agent, or checking something you will not fix — trains everyone to ignore red,
which destroys the only thing a status board is for.
