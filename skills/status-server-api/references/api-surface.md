# Every API endpoint

Generated from the server source, so it reflects what exists rather than what was
written down. **🔒 marks endpoints behind a role gate** (`STATUS_ADMIN` / `INFRA_ADMIN`);
everything else needs only a valid key.

Ask a running server what it supports with `GET /api/capabilities` — that beats this file
if they ever disagree.


## Reading state

| Endpoint | |
|---|---|
| `GET /api/auth-config` | Auth discovery — always public so the mobile app knows how to authenticate |
| `GET /api/commands/result` | Get the latest structured result for a command |
| `GET /api/events` |  |
| `GET /api/global` | Global state — replaces GlobalModelAdvice |
| `GET /api/history` |  |
| `GET /api/history/{id}` |  |
| `POST /api/history/{id}/revert` |  |
| `GET /api/presence` |  |
| `POST /api/presence/ping` |  |
| `POST /api/probes/debug` | Toggle debug mode for a probe — enables ctx |
| `GET /api/probes/history` | Get history for a probe at a given resolution and path |
| `GET /api/probes/history/list` | List all probes with history data |
| `GET /api/probes/infographic` | Get infographic SVG + resolved patches for a probe |
| `GET /api/probes/result` | Get the latest structured result for a probe |
| `GET /api/probes/snapshot` | Get latest snapshot of all paths for a probe |
| `GET /api/status` |  |
| `GET /api/tree` | Path-based tree built from all probe names + history probes |
| `GET /api/untracked-issues` | Degraded probes in mapped projects — used by the topbar alert badge |

## Capabilities

| Endpoint | |
|---|---|
| `GET /api/capabilities` |  |

## Infrastructure config

| Endpoint | |
|---|---|
| `GET /api/infrastructure/config` | Current infrastructure config |
| `POST /api/infrastructure/config` | Save the config, reload the scheduler, record a history entry |
| `GET /api/infrastructure/hosts` | Host names, for pickers and for resolving where a probe would run |
| `GET /api/infrastructure/types` | Service types from the catalog, with their param metadata |

## Probe authoring (Probe IDE)

| Endpoint | |
|---|---|
| `POST /api/ide/command-create` 🔒 | Create a new command from scratch |
| `GET /api/ide/command-definition` 🔒 | Get command definition YAML |
| `POST /api/ide/command-definition` 🔒 | Save command definition YAML |
| `POST /api/ide/command-save` 🔒 | Save command script (run |
| `GET /api/ide/command-source` 🔒 | Get script source for a command definition |
| `GET /api/ide/commands` 🔒 | List installed command definitions |
| `GET /api/ide/list` 🔒 | List all scripts with their custom builtin flag |
| `GET /api/ide/probe-bindings` 🔒 | Get infographic bindings YAML for a probe |
| `POST /api/ide/probe-bindings` 🔒 | Save infographic bindings YAML |
| `POST /api/ide/probe-create` 🔒 | Create a new probe from scratch |
| `GET /api/ide/probe-definition` 🔒 | Get probe definition YAML |
| `POST /api/ide/probe-definition` 🔒 | Save probe definition YAML |
| `POST /api/ide/probe-dev` 🔒 | Keep old probe-dev endpoint for backward compat |
| `POST /api/ide/probe-save` 🔒 | Save probe script (check |
| `GET /api/ide/probe-source` 🔒 | Get script source for a probe definition by catalog ID |
| `GET /api/ide/probe-svg` 🔒 | Get infographic SVG templates (light + dark) for a probe |
| `POST /api/ide/probe-svg` 🔒 | Save infographic SVG templates (light + optional dark) |
| `GET /api/ide/probes` 🔒 | List installed probe definitions from the catalog (the editable probe types, not running instances) |
| `POST /api/ide/save` 🔒 | Save a custom legacy script |
| `GET /api/ide/script/{name}` 🔒 | Get script source |
| `POST /api/ide/test` 🔒 | Test-run: fetch URL, run script, return result tree |
| `POST /api/ide/test-on-agent` 🔒 | Queue a test-probe execution on a specific agent |
| `GET /api/ide/test-on-agent/{id}` 🔒 | Poll for test-probe result |
| `POST /api/ide/toggle-dev` 🔒 | Toggle dev flag on a probe or command manifest |

## Probe catalog

| Endpoint | |
|---|---|
| `GET /api/catalog` | Full catalog state — installed + available from built-in |
| `POST /api/catalog/install/{id}` | Install a probe command from the built-in catalog |
| `GET /api/catalog/sync` | Agent catalog sync — returns installed entries + hash |
| `POST /api/catalog/uninstall/{id}` | Uninstall a probe command — removes from installed folder |
| `POST /api/catalog/update/{id}` | Update an installed entry to the latest built-in version |

## Agents

Registration, heartbeat, approval and command dispatch for the per-host agent. **Registration
is open** — an agent self-registers — but everything after that requires the agent to be
approved and to sign requests with its Ed25519 key. `autoApproveAgents` defaults to `false`;
approve deliberately. Agents also fetch probe credentials here, over a signed request.

| Endpoint | |
|---|---|
| `GET /api/agents` | List all agents (admin) — parses heartbeat data and maps to UI-friendly field names |
| `POST /api/agents/action` | Trigger a probe action on the agent that runs the probe |
| `GET /api/agents/action/{executionId}` | Poll action execution status + streamed log entries |
| `POST /api/agents/register` | Agent registers itself on first startup |
| `POST /api/agents/{name}/approve` | Approve a pending agent (admin) |
| `POST /api/agents/{name}/command-complete` | Agent reports command execution completion with results |
| `POST /api/agents/{name}/command-result` | Agent returns the result of a command (e |
| `POST /api/agents/{name}/command-stream` | Agent streams a command execution log entry (line-by-line) |
| `POST /api/agents/{name}/docker/{action}` | Send a Docker control command to an agent (restart stop start) |
| `POST /api/agents/{name}/heartbeat` | Agent pushes host metrics and container inventory |
| `PUT /api/agents/{name}/labels` | Set server-side labels for an agent (admin) |
| `GET /api/agents/{name}/log-entries` | Read log entries by canonical URI |
| `POST /api/agents/{name}/log-stream` | Agent pushes log stream batches |
| `DELETE /api/agents/{name}/log-subscriptions` | Remove a log subscription (admin) |
| `GET /api/agents/{name}/log-subscriptions` | Get log subscriptions for an agent (admin) |
| `POST /api/agents/{name}/log-subscriptions` | Add or toggle a log subscription (admin) |
| `GET /api/agents/{name}/logs` | List all log sources for an agent |
| `POST /api/agents/{name}/logs` | Request logs from an agent for a specific container |
| `GET /api/agents/{name}/logs/{source}` | Read raw log lines for an agent+source |
| `GET /api/agents/{name}/logs/{source}/parsed` | Read parsed structured log entries |
| `POST /api/agents/{name}/probe-results` | Agent posts probe execution results |
| `POST /api/agents/{name}/probe-stream` | Agent streams probe debug log entries |
| `POST /api/agents/{name}/reject` | Reject remove an agent (admin) |
| `POST /api/agents/{name}/retention` | Set log retention for an agent (admin) |

## Sites & floor plans

Read-only views of the `sites:` section of `infrastructure.yml` — geographic placement and
drawn floors, plus the one thing the config editor cannot do: uploading and serving the floor
**images**. Editing sites themselves goes through the infrastructure config, same YAML.

| Endpoint | |
|---|---|
| `GET /api/sites` |  |
| `POST /api/sites/images` |  |
| `GET /api/sites/images/{filename:.+}` |  |
| `GET /api/sites/{name}` |  |

## Topology layouts

Saved arrangements of the 3D topology view — the plate visualisation, not the probe board.
Layouts are named; one is active at a time.

| Endpoint | |
|---|---|
| `GET /api/topology/layouts` |  |
| `POST /api/topology/layouts/activate/{name}` | Switch the active layout (persisted, so GET returns it next time) |
| `DELETE /api/topology/layouts/{name}` | Remove a layout (including the default one) |
| `PUT /api/topology/layouts/{name}` | Replace the named layout's pinned list |

## Drills

Scheduled practice alerts that ask responders to acknowledge, with a leaderboard of who
answered and how fast. `GET /api/drills/active` is what the nav badge polls.

| Endpoint | |
|---|---|
| `GET /api/drills` |  |
| `GET /api/drills/active` | Active drill only — polled by the nav badge |
| `GET /api/drills/config` |  |
| `POST /api/drills/config` |  |
| `POST /api/drills/trigger` |  |
| `POST /api/drills/{id}/accept` |  |
| `POST /api/drills/{id}/close` |  |

## Workflows

User-defined record types with a state machine — the system that replaced legacy incidents. A
*type* declares fields, nodes (states) and edges (transitions); an *instance* is one record
moving through it. `GET /api/workflows/types` lists what exists, `POST /api/workflows/{type}`
creates a record, and `POST /api/workflows/{type}/{id}/transitions` moves it along an edge.

An edge may carry `requireFields`, `requireRole` and a `when` expression. ⚠️ `when` is a **hard
gate** in this implementation: a transition whose condition is false is refused with
`when_condition_false`, not allowed through with a warning.

| Endpoint | |
|---|---|
| `GET /api/workflows` |  |
| `PUT /api/workflows` |  |
| `GET /api/workflows/attachable` | Types that declare { |
| `GET /api/workflows/field-types` | The field-type definitions this server resolved, for the SPA |
| `GET /api/workflows/types` |  |
| `GET /api/workflows/types/{id}` |  |
| `PUT /api/workflows/types/{id}` |  |
| `GET /api/workflows/{type}` |  |
| `POST /api/workflows/{type}` |  |
| `DELETE /api/workflows/{type}/{id}` |  |
| `GET /api/workflows/{type}/{id}` |  |
| `POST /api/workflows/{type}/{id}/actions/{actionId}` |  |
| `GET /api/workflows/{type}/{id}/archived` |  |
| `POST /api/workflows/{type}/{id}/attach` |  |
| `DELETE /api/workflows/{type}/{id}/attach/{refKind}/{refId}` |  |
| `POST /api/workflows/{type}/{id}/comments` |  |
| `POST /api/workflows/{type}/{id}/fields/{fieldName}/files` |  |
| `DELETE /api/workflows/{type}/{id}/fields/{fieldName}/files/{filename:.+}` |  |
| `GET /api/workflows/{type}/{id}/fields/{fieldName}/files/{filename:.+}` |  |
| `GET /api/workflows/{type}/{id}/fields/{fieldName}/files/{filename:.+}/thumbnail` |  |
| `POST /api/workflows/{type}/{id}/references` | Attach a reference (e |
| `DELETE /api/workflows/{type}/{id}/references/{kind}` | Remove a reference from an instance's { |
| `POST /api/workflows/{type}/{id}/transitions` |  |
| `POST /api/workflows/{type}/{id}/unarchive` |  |

## Messaging

In-app conversations, including the surface a chat assistant uses to talk to operators.

| Endpoint | |
|---|---|
| `GET /api/messages/conversations` |  |
| `POST /api/messages/conversations/start` |  |
| `GET /api/messages/conversations/{id}` |  |
| `POST /api/messages/conversations/{id}` |  |
| `POST /api/messages/conversations/{id}/read` |  |
| `POST /api/messages/conversations/{id}/typing` | Notify that the current user is typing in a conversation |
| `POST /api/messages/page` | Send an urgent page to a user |
| `POST /api/messages/page/{conversationId}/respond` | Respond to a page with an ETA |
| `GET /api/messages/unread-count` |  |
| `GET /api/messages/users` | List all users available for messaging (any authenticated user can call this) |

## Notifications

| Endpoint | |
|---|---|
| `DELETE /api/push/register` | Unregister APNs device token — fire-and-forget |
| `POST /api/push/register` | Register APNs device token — proxied to Push relay |
| `POST /api/telegram/webhook` | Receives Telegram Bot API webhook updates |

## Identity & roles

What the active identity backend can do, so a client can hide what it does not support, plus
TOTP/MFA enrolment. Roles themselves come from the identity provider — the server maps them onto
`STATUS_ADMIN`, `INFRA_ADMIN`, `PROBE_EDITOR`, `VIEWER` and the rest. See *Getting a key* in
`status-server-ops` for how a key inherits and can narrow them.

| Endpoint | |
|---|---|
| `GET /api/iam/capabilities` |  |
| `DELETE /api/iam/mfa/totp` | Removes TOTP from the authenticated user's account |
| `POST /api/iam/mfa/totp/confirm` | Confirms enrollment by verifying the first code from the authenticator app |
| `POST /api/iam/mfa/totp/enroll` | Begins TOTP enrollment |

## Your account

| Endpoint | |
|---|---|
| `POST /api/user/account/delete` |  |
| `GET /api/user/api-keys` |  |
| `POST /api/user/api-keys` |  |
| `POST /api/user/api-keys/{id}/revoke` |  |
| `GET /api/user/page-prefs` |  |
| `POST /api/user/page-prefs` |  |
| `GET /api/user/profile` | Current user profile and roles |
| `GET /api/user/schedules` |  |
| `POST /api/user/schedules` |  |
| `POST /api/user/schedules/timezone` |  |
| `DELETE /api/user/schedules/{id}` |  |
| `POST /api/user/test-email` |  |
| `POST /api/user/update-email` |  |
| `POST /api/user/update-name` |  |
| `POST /api/user/update-password` |  |
| `POST /api/user/update-phone` |  |

## Administration

Server info, users and roles, notification config, retention presets, and the storage tools —
including `/api/admin/storage/stale` and `/api/admin/storage/cleanup`, covered in
`status-server-ops`.

| Endpoint | |
|---|---|
| `GET /api/admin/agents/{name}/commands` | Catalog commands the runtime menu offers for this agent |
| `GET /api/admin/agents/{name}/configured-instances` | Configured command instances for an agent — operator presets from { |
| `GET /api/admin/agents/{name}/execution/{execId}` | Get execution log entries + result for a running completed command |
| `POST /api/admin/agents/{name}/run-script` | Queue a catalog command for execution on the named agent |
| `GET /api/admin/credentials` |  |
| `POST /api/admin/credentials` |  |
| `DELETE /api/admin/credentials/{id}` |  |
| `GET /api/admin/credentials/{id}` |  |
| `PUT /api/admin/credentials/{id}` |  |
| `GET /api/admin/credentials/{id}/log` |  |
| `GET /api/admin/notifications` |  |
| `POST /api/admin/notifications/{section}` |  |
| `POST /api/admin/notifications/{section}/toggle` |  |
| `GET /api/admin/retention-presets` |  |
| `POST /api/admin/retention-presets` |  |
| `DELETE /api/admin/retention-presets/{name}` |  |
| `GET /api/admin/server-info` |  |
| `GET /api/admin/storage` |  |
| `POST /api/admin/storage/cleanup` | Delete abandoned series |
| `POST /api/admin/storage/delete` |  |
| `GET /api/admin/storage/stale` | History series that look abandoned: nothing has written to them for { |
| `GET /api/admin/users` |  |
| `DELETE /api/admin/users/{userId}` |  |
| `POST /api/admin/users/{userId}/roles` |  |
