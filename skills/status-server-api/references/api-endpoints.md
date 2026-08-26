# Status Server API Endpoints

## Health & Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/status` | Overall system status |
| GET | `/api/tree` | Service tree structure |
| GET | `/api/auth-config` | Auth configuration |
| GET | `/api/events` | SSE event stream |

## Probes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/probes/history` | Probe history for a specific probe |
| GET | `/api/probes/snapshot` | Current probe snapshot |
| GET | `/api/probes/history/list` | List all probe history files |

## Untracked Issues

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/untracked-issues` | List untracked issues |

## SPA API

The SPA frontend (`/app`) is replacing the Thymeleaf server-rendered pages.
Thymeleaf routes listed below will be removed once the SPA migration is complete
(except for email templates).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user/profile` | Current user profile |
| GET | `/api/global` | Global app state |

## Agents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents/register` | Register a new agent |
| POST | `/api/agents/{name}/heartbeat` | Agent heartbeat (returns pending commands) |
| POST | `/api/agents/{name}/command-result` | Submit command result |
| POST | `/api/agents/{name}/approve` | Approve pending agent |
| POST | `/api/agents/{name}/reject` | Reject pending agent |
| POST | `/api/agents/{name}/probe-results` | Submit probe results |
| POST | `/api/agents/{name}/docker/{action}` | Docker container action |
| POST | `/api/agents/{name}/retention` | Set log retention policy |

### Agent Log Streaming

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agents/{name}/logs` | Submit log batch |
| POST | `/api/agents/{name}/log-stream` | Stream log lines |
| POST | `/api/agents/{name}/command-stream` | Stream command output |
| POST | `/api/agents/{name}/command-complete` | Signal command completion |
| GET | `/api/agents/{name}/log-subscriptions` | Get log subscriptions |
| POST | `/api/agents/{name}/log-subscriptions` | Add log subscription |
| DELETE | `/api/agents/{name}/log-subscriptions` | Remove log subscription |
| GET | `/api/agents/{name}/logs` | Get stored logs |
| GET | `/api/agents/{name}/logs/{source}` | Get logs by source |
| GET | `/api/agents/{name}/logs/{source}/parsed` | Get parsed/structured logs |

## Telegram

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/telegram/webhook` | Telegram bot webhook |

## Auth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/login` | Login page |
| POST | `/login` | Authenticate |
| GET | `/login/totp` | TOTP verification page |
| POST | `/login/totp` | Verify TOTP code |
| GET | `/register` | Registration page |
| POST | `/register` | Create account |

## Account (`/account`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/account` | Account settings page |
| POST | `/account/update-email` | Change email |
| POST | `/account/update-password` | Change password |
| POST | `/account/delete` | Delete account |
| POST | `/account/test-email` | Send test email |

### API Keys

| Method | Path | Description |
|--------|------|-------------|
| POST | `/account/api-keys/create` | Create API key |
| POST | `/account/api-keys/revoke` | Revoke API key |

### TOTP

| Method | Path | Description |
|--------|------|-------------|
| POST | `/account/totp/setup` | Start TOTP setup |
| POST | `/account/totp/confirm` | Confirm TOTP setup |
| POST | `/account/totp/disable` | Disable TOTP |

### Email Digest

| Method | Path | Description |
|--------|------|-------------|
| POST | `/account/digest/add` | Add digest subscription |
| POST | `/account/digest/remove` | Remove digest subscription |
| POST | `/account/digest/timezone` | Set digest timezone |

### Notifications

| Method | Path | Description |
|--------|------|-------------|
| POST | `/account/notifications/preferences` | Update notification preferences |
| POST | `/account/notifications/telegram/link` | Link Telegram account |
| GET | `/account/notifications/telegram/status` | Check Telegram link status |
| POST | `/account/notifications/telegram/unlink` | Unlink Telegram account |
| POST | `/account/notifications/telegram/test` | Send test Telegram message |
| POST | `/account/notifications/sms/save` | Save SMS number |
| POST | `/account/notifications/sms/remove` | Remove SMS number |
| POST | `/account/notifications/sms/test` | Send test SMS |

## Admin (`/admin`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/reload` | Reload configuration |

### User Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users` | List users |
| POST | `/admin/users/{userId}/roles` | Update user roles |
| POST | `/admin/users/{userId}/delete` | Delete user |

### Agent Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/agents` | Agent admin page |
| POST | `/admin/agents/{name}/approve` | Approve agent |
| POST | `/admin/agents/{name}/reject` | Reject agent |
| POST | `/admin/agents/{name}/logs` | Request logs from agent |
| POST | `/admin/agents/{name}/stream-toggle` | Toggle log streaming |
| POST | `/admin/agents/{name}/add-log-source` | Add log source |
| POST | `/admin/agents/{name}/retention` | Set retention policy |
| POST | `/admin/agents/{name}/docker/{action}` | Docker action |
| POST | `/admin/agents/{name}/run-script` | Execute script on agent (body: `{commandId, params}`) |
| GET | `/admin/agents/{name}/commands` | Catalog manifest — all commands the agent has installed |
| GET | `/admin/agents/{name}/configured-instances` | Command *instances* (operator presets) configured for this agent |
| GET | `/admin/agents/{name}/execution/{execId}` | Get execution details |

### Notification Rules

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/notifications` | Notification rules page |
| POST | `/admin/notifications/save` | Save notification rule |
| POST | `/admin/notifications/toggle` | Enable/disable rule |
| POST | `/admin/notifications/reload` | Reload notification config |
| POST | `/admin/notifications/telegram/set-webhook` | Set Telegram webhook URL |

### Infrastructure Editor

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/infrastructure` | Infrastructure editor page |
| GET | `/admin/infrastructure/api/config` | Get infrastructure config |
| GET | `/admin/infrastructure/api/types` | Get service types |
| GET | `/admin/infrastructure/api/hosts` | Get hosts |
| POST | `/admin/infrastructure/api/config` | Save infrastructure config |

### Script Playground

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/scripts` | Script playground page |
| GET | `/admin/scripts/api/list` | List scripts |
| GET | `/admin/scripts/api/{name}` | Get script by name |
| POST | `/admin/scripts/api/test` | Test/run script |
| POST | `/admin/scripts/api/save` | Save script |

## Drills

| Method | Path | Description |
|--------|------|-------------|
| GET | `/drills` | Drills page |
| POST | `/drills/{id}/accept` | Accept/acknowledge drill |
| POST | `/drills/trigger` | Trigger a drill |
| POST | `/drills/config` | Update drill config |
| GET | `/drills/api/active` | Get active drill |

## Logs Viewer

| Method | Path | Description |
|--------|------|-------------|
| GET | `/logs/{agentName}` | Log viewer page |
| GET | `/logs/{agentName}/fetch` | Fetch log data |

## History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/history` | History index page |
| GET | `/history/{filename}` | Download history file |

## Dashboard / SPA

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard (redirects or renders) |
| GET | `/project/{project}` | Project-scoped dashboard |
| GET | `/hosts` | Hosts view |
| GET | `/app/**` | SPA catch-all (serves index.html) |

---

> **Migration note:** Thymeleaf server-rendered pages (auth, account, admin, drills,
> incidents web views, logs viewer, history) are being replaced by the SPA frontend
> at `/app`. Thymeleaf will remain only for email templates.
