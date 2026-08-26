# Active Probes Folder

## Overview

Every probe that runs in the system has a working copy in the **active probes folder**:

```
{config-path}/probes/{probe-id}/
├── probe.yml      # definition (name, params, outputs, metadata)
└── check.js       # script source (executed by agents)
```

This folder is the single source of truth for what's deployed. Agents sync from it. The Probe IDE edits it. The catalog installs into it.

## Lifecycle

### Builtin → Installed (automatic)

On server startup, `CatalogService.autoInstallBuiltins()` copies every builtin probe from the classpath (`resources/catalog/probes/`) to the config folder. This ensures:

- Every probe has a working copy that can be edited
- Versioning works (installed copy tracks a specific version)
- "Reset to builtin" = re-copy from classpath

### Catalog Install (manual)

When a user clicks "Install" in the Probe Catalog UI:
1. Builtin definition is copied to `{config-path}/probes/{id}/`
2. `probe.yml` + `check.js` written
3. `CatalogService.reloadInstalled()` picks up the change
4. Agents receive it on next heartbeat via catalog sync

### IDE Create (from scratch)

When "New" is clicked in the Probe IDE:
1. `POST /admin/scripts/api/probe-create` with `{id: "my-probe"}`
2. Creates `{config-path}/probes/my-probe/` with default `check.js` + `probe.yml`
3. Appears in IDE sidebar immediately

### IDE Edit + Save

1. User edits script in Script tab and/or definition in Definition tab
2. Save writes:
   - `POST /admin/scripts/api/probe-save` → `{config-path}/probes/{id}/check.js`
   - `POST /admin/scripts/api/probe-definition` → `{config-path}/probes/{id}/probe.yml`
3. `CatalogService.reloadInstalled()` picks up changes
4. Agents receive updated script on next heartbeat

### Catalog Update

When a builtin has a newer version than the installed copy:
1. Shown in Probe Catalog UI as "Update available"
2. User clicks "Update"
3. Overwrites the installed copy with the newer builtin
4. User's edits are lost (by design — update = reset to latest builtin)

### Reset to Builtin

To revert a probe to its original builtin state:
1. Delete the folder: `rm -rf {config-path}/probes/{id}/`
2. Restart server (or call reload) — auto-install will recreate from builtin

## Agent Sync

Agents poll `GET /api/catalog/sync?hash={hash}`. If the hash changed (probe added/edited/removed), agents receive the full installed catalog with script sources. Each agent then compares against its local cache and updates.

The sync payload includes:
- `probe.yml` manifest fields (id, name, params, outputs)
- `check.js` script source (inline in the JSON)
- Content hash for change detection

## File Structure on Server

```
/status/config/                     # STATUS_CONFIG_PATH
├── probes/
│   ├── http-endpoint/
│   │   ├── probe.yml
│   │   └── check.js
│   ├── postgres-health/
│   │   ├── probe.yml
│   │   └── check.js
│   ├── test-sandbox/
│   │   ├── probe.yml
│   │   └── check.js
│   └── ... (38 probes total)
├── commands/
│   ├── docker-restart/
│   │   ├── command.yml
│   │   └── run.js
│   └── ...
├── infrastructure.yml
└── notifications.yml
```

## API Endpoints (Probe IDE)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/scripts/api/probes` | List installed probe definitions |
| GET | `/admin/scripts/api/probe-source?name={id}` | Get check.js source |
| GET | `/admin/scripts/api/probe-definition?id={id}` | Get probe.yml content |
| POST | `/admin/scripts/api/probe-save` | Save check.js |
| POST | `/admin/scripts/api/probe-definition` | Save probe.yml |
| POST | `/admin/scripts/api/probe-create` | Create new probe from scratch |
| POST | `/admin/scripts/api/test` | Run script locally (Main Server sandbox) |
| POST | `/admin/scripts/api/test-on-agent` | Queue test execution on agent |
| GET | `/admin/scripts/api/test-on-agent/{id}` | Poll agent execution result |

## Builtin Catalog (templates)

Builtins live in the classpath and are never modified at runtime:

```
resources/catalog/probes/{id}/
├── probe.yml
└── check.js
```

They serve as templates. `autoInstallBuiltins()` copies them to the config folder on first startup. Updates compare `updated` dates between builtin and installed versions.
