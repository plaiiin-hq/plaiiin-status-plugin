# Setup

## 1. Point the skills at your server

Put them in `~/.plaiiin/status-server/env` — the location both skills read, so no session ever
has to ask you for a key:

```bash
mkdir -p ~/.plaiiin/status-server && chmod 700 ~/.plaiiin/status-server
cat > ~/.plaiiin/status-server/env <<'EOF'
STATUS_URL=https://status.example.com   # no trailing slash
STATUS_API_KEY=twk_…
EOF
chmod 600 ~/.plaiiin/status-server/env
```

Load it in a shell with `set -a && . ~/.plaiiin/status-server/env && set +a`. Exported
variables of the same name take precedence, so a one-off override still works.

## 2. Mint an API key

In the SPA: **Settings → API keys → New key**. Over the API:

```bash
curl -s -X POST -H "X-API-Key: $EXISTING_KEY" -H 'Content-Type: application/json' \
  -d '{"name":"claude-readonly"}' "$STATUS_URL/api/user/api-keys"
```

Keys inherit the roles of the user that minted them. **This is the decision that matters.**

## 3. Choose the roles deliberately

| Key kind | Roles | Can do | Use for |
|---|---|---|---|
| **Read** | none beyond authenticated | `/api/tree`, `/api/status`, `/api/probes/history`, incidents | Dashboards, bots, ambient Claude sessions, CI checks |
| **Admin** | `STATUS_ADMIN` or `INFRA_ADMIN` | Everything above **plus `/api/ide/**`** | Deliberate probe-authoring sessions only |

`POST /api/ide/probe-save` writes `check.js` into the probe catalog, and the agents on every
monitored host then execute it. An admin key is therefore code execution on your whole
estate — not just read access to a board.

Default to a **read key**. Reach for an admin key when you are actually authoring, and
rotate it afterwards.

> **Deployments older than 2026-08-26:** `/api/ide/**` carried no authorization beyond
> "authenticated", so any valid key could write executable probe scripts. Upgrade, then
> rotate every key that existed before the upgrade.

## 4. Verify

```bash
curl -s -H "X-API-Key: $STATUS_API_KEY" "$STATUS_URL/api/status" | head -c 400
```

A **302 to `/app/login`** does not mean a bad key — it usually means the path is outside
`/api/**`, which is the only prefix the API-key filter is registered on. Check the path
first.

## 5. MCP server — not currently distributed

Status has an internal MCP server (15 tools over the same REST API) built for its chat
responder. It is **not part of this plugin and is not currently shipped to customers** — if
you want tools rather than curl, ask your Plaiiin contact.

Everything in `status-server-api` works over plain HTTP, so nothing here depends on it.
