# Setup

## 1. Point the skills at your server

```bash
export STATUS_URL=https://status.example.com   # no trailing slash
export STATUS_API_KEY=twk_…
```

Put these in your shell profile, or in a `~/.config/status/env` you source, so they survive
across sessions.

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

## 5. Optional — the MCP server

If you would rather have tools than curl, Status ships `mcp/status_server.py` (15 tools). It
reads the same `STATUS_URL` and `STATUS_API_KEY`. Add it to your MCP config:

```json
{
  "mcpServers": {
    "status": {
      "command": "python3",
      "args": ["/path/to/status_server.py"],
      "env": { "STATUS_URL": "https://status.example.com", "STATUS_API_KEY": "twk_…" }
    }
  }
}
```

It is read-only apart from incidents; probe authoring stays on the REST API.
