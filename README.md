# plaiiin-status (Claude Code plugin)

Skills for **operating a Plaiiin Status server** — the infrastructure-first monitoring
platform where you declare what you have and Status works out what to check.

## Skills

| Skill | Purpose |
|---|---|
| `status-server-ops` | Model infrastructure in `infrastructure.yml`, author catalog probes, apply config without dropping every session — and the five wiring mistakes that fail as **silence** rather than as errors. |
| `status-server-api` | Drive a running board from Claude: read the tree and probe history, triage what is red, open/resolve incidents, author probes over `/api/ide/*`. |

## Install

```
/plugin marketplace add plaiiin-hq/plaiiin-status-plugin
/plugin install plaiiin-status@plaiiin-status
```

## Setup

Two environment variables point the skills at your deployment:

```bash
export STATUS_URL=https://status.example.com
export STATUS_API_KEY=twk_…
```

See [`docs/setup.md`](docs/setup.md) for minting a key and choosing its roles — this
matters more than it looks, because a key with `INFRA_ADMIN` can write probe scripts that
execute on every monitored host.

## Why these skills exist

Status is easy to configure and unusually easy to configure *wrongly in a way that looks
fine*. A probe bound to a non-existent agent never runs and shows nothing. A project `ref`
with one wrong space renders an empty card. An `ssl-certificate` probe running server-side
degrades to a plain HTTP check and reports "HTTP 200" while checking no expiry at all.

None of those produce an error. All of them produce a board that looks healthy.

Both skills are built around that: they tell you what to verify, not just what to type.

## Staying current

This plugin changes with the product. **Enable auto-update** so you are not on a stale
version: `/plugin` → **Marketplaces** → `plaiiin-status` → **Enable auto-update** (or add
`"autoUpdate": true` to the `plaiiin-status` entry under `extraKnownMarketplaces` in
`~/.claude/settings.json`). A `SessionStart` hook reminds you if it is off.

Versioning is by git SHA — every push to `main` is a new version. Without auto-update,
pull manually:

```
/plugin marketplace update plaiiin-status
/plugin update plaiiin-status@plaiiin-status
```

## License

[Apache-2.0](LICENSE) — © 2026 Plaiiin.

This licenses **these skills**, not Plaiiin Status itself. No rights to the Status source,
binaries or trademarks are granted or implied.
