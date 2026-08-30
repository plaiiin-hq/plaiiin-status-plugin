---
title: Probe Plugin Format
summary: The complete authoring contract for a Plaiiin Status probe plugin — every file the package may ship, every key probe.yml may carry, and what each one does on the success and failure paths.
audience: probe authors and agents driving a Plaiiin Status server
# source_of_truth paths are in the Status server repository, quoted so a claim
# can be traced by anyone who has it.
source_of_truth:
  - Status-Server/src/main/java/com/plaiiin/status/catalog/CatalogEntry.java
  - Status-Server/src/main/java/com/plaiiin/status/catalog/CatalogService.java
  - Status-Server/src/main/java/com/plaiiin/status/agent/AgentController.java
  - Status-Server/src/main/resources/catalog/probes/
  - Status-Frontend/docs/rendering-pipeline.md
  - Status-Server/docs/data-model.md
verified: 2026-08-28
---

# Probe Plugin Format

A **probe plugin** is one directory that teaches a Plaiiin Status agent to check one kind
of thing and teaches the frontend how to display the result. This document is the
authoring contract for that directory.

## Quick answers

| Question | Answer | Where |
|---|---|---|
| What is the minimum viable plugin? | 2 files — `probe.yml` with an `id:`, and `check.js` defining `function check(ctx)` | [Package layout](#package-layout--files-a-plugin-may-ship) |
| Which filenames are magic? | `probe.yml`, `check.js`, `run.js`, `detect.js`, `icon.svg`, `action-*.js`, `infographic/template.svg`, `infographic/template-dark.svg`, `infographic/bindings.yml` | [Package layout](#package-layout--files-a-plugin-may-ship) |
| Why did my plugin not appear at all? | `probe.yml` has no `id:` — `CatalogService.java:514-515` returns null and both loaders skip it with no log line | [Fails silently → F1](#fails-silently--symptom-cause-fix) |
| How do I label a value in the tree? | An `output:` entry whose `path:` matches the stream key, carrying `label:` | [output:](#output--declaring-what-a-probe-emits) |
| How do I add a button? | 4 pieces: `type: action` in `output:`, `ctx.action.add(path)` in `check.js`, `action-<leaf>.js`, and a stored probe result | [Action scripts](#action-scripts--turning-a-declaration-into-a-button) |
| Is `dangerous: true` a permission check? | No. `POST /api/agents/action` has no `@PreAuthorize`; `dangerous` is styling plus a prompt | [Action scripts](#action-scripts--turning-a-declaration-into-a-button) |
| How does a probe get a secret? | A param **value** of `"credential:<name>"` in `infrastructure.yml`; the sandbox receives the raw secret string | [params:](#params--declaring-configuration-inputs) |
| One probe reporting N things — how? | `streamValues` with `{var}` paths for measurements; `scriptResult.services[]` for third-party statuses | [Fan-out](#fan-out--streamvalues-vs-scriptresultservices) |
| How long until an edit reaches an agent? | Up to ~60 s: server detection (500 ms watch debounce or 30 s poll) + heartbeat (default 30 s) | [Install and sync](#install-and-sync--how-a-plugin-reaches-an-agent) |
| Does `detect.js` do anything? | No. Loaded and stored, zero callers anywhere | [detect.js](#detectjs--declared-loaded-never-executed) |
| Complete field schema in one block? | Yes, at the end of this document | [Field schema](#field-schema--machine-readable) |

## Scope and neighbouring documents

This document owns the **authoring contract**: what files a plugin ships, what keys
`probe.yml` accepts, and what each key does. Six neighbouring documents own adjacent
territory; consult them rather than expecting this document to cover their ground.

| Document | Owns | Read it for |
|---|---|---|
| [Rendering Pipeline](rendering-pipeline.md) | values → tree → card → tiles/rows → widget → 2D/3D | The widget catalogue, the 4-unit tile clamp, how Scalable Vector Graphics (SVG) infographic bindings are applied |
| the server's data model | series identity and keys, storage, rollups, write-ahead log, retention | What each fan-out mechanism writes to storage and for how long |
| [writing-probes.md](writing-probes.md) | how to *write* `check.js` | Sandbox application programming interface (API) usage, worked script examples, thresholds |
| [probe-sandbox.md](probe-sandbox.md) | full `ctx.*` reference | Every sandbox call signature |
| [probe-active-folder.md](probe-active-folder.md) | the `{config-path}/probes/` working copy | Probe integrated development environment (IDE) endpoints, reset-to-builtin |
| [credentials-store.md](credentials-store.md) | credential types, encryption, admin API | Creating and rotating credentials |
| [probe-vs-command.md](probe-vs-command.md) | probe versus command | Deciding to ship a command instead of a probe |

Everything in this document was read out of the code and the 44 plugins shipped in
`Status-Server/src/main/resources/catalog/probes/` on 2026-08-28. Every count stated is
measured, not estimated.

---

## Package layout — files a plugin may ship

A probe plugin is one directory. The directory name is **not** the plugin identity —
`probe.yml`'s `id:` is, because `CatalogService.java:419` keys the catalog map by
`entry.id()`.

```
probes/my-probe/
├── probe.yml            ← required
├── check.js             ← required in practice
├── detect.js            ← optional, inert
├── icon.svg             ← optional
├── action-<name>.js     ← optional, one file per action
└── infographic/
    ├── template.svg     ← optional
    ├── template-dark.svg
    └── bindings.yml
```

| File | Loader | Field it populates | If absent |
|---|---|---|---|
| `probe.yml` | `CatalogService.java:512` | every scalar field | directory is skipped — `loadFileEntries` only enters directories whose manifest exists (`CatalogService.java:449-450`) |
| `check.js` | `CatalogService.java:344-352`, `:456-462` | `scriptSource` | the agent has no script to execute for that probe |
| `run.js` | same loop, tried **after** `check.js` | `scriptSource` | nothing — a directory holding only `run.js` still works; first match wins |
| `detect.js` | `CatalogService.java:356-364`, `:471-474` | `detectSource` | nothing changes; `detectSource` is never executed |
| `icon.svg` | `CatalogService.java:366-373`, `:465-468` | `iconSvg` | the Lucide icon name in `icon:` is used instead |
| `action-*.js` | `CatalogService.java:396-417`, `:492` | `actionScripts["<name>"]` | the button still renders; clicking it returns `No action script found for: <name>` |
| `infographic/template.svg` | `CatalogService.java:375-394` | `svgTemplate` | `hasInfographic()` is false and no infographic tab appears |
| `infographic/template-dark.svg` | `CatalogService.java:383-386` | `svgTemplateDark` | the light template is served in both themes |
| `infographic/bindings.yml` | `CatalogService.java:387-391` | `bindingsYaml` | the SVG renders static — no probe values are patched into it |

Any other file in the directory is ignored by both loaders.

Rules:

- If `check.js` and `run.js` both exist, then `check.js` wins — the loop breaks on first
  match (`CatalogService.java:344-352`).
- The action name is the filename with the `action-` prefix and the `.js` suffix removed,
  verbatim — underscores and further hyphens are kept.
  `action-prune_keep_latest.js` → action name `prune_keep_latest`
  (`CatalogService.java:495`).
- If `infographic/template.svg` is absent but `bindings.yml` is present, then the whole
  infographic is skipped — `withInfographic` is only called inside the
  `svgResource.exists()` branch (`CatalogService.java:380`).
- If a plugin ships `template.svg` only, then dark-theme support must be done inside the
  SVG. `http-endpoint/infographic/template.svg:9-15` does exactly that with a
  `@media (prefers-color-scheme: dark)` block. Binding mechanics belong to
  [Rendering Pipeline](rendering-pipeline.md).

### Measured usage across the 44 shipped plugins

| File | Plugins | Which |
|---|---|---|
| `probe.yml` + `check.js` | 44 | all |
| `icon.svg` | 9 | docker-hub, docker-services, elasticsearch, github-actions, github-status, nginx-status, postgres-check, rabbitmq, redis |
| `action-*.js` | 3 (9 files) | lifx (5), docker-services (3), folder-watch (1) |
| `detect.js` | 4 | docker-services, postgres-check, redis, traefik |
| `infographic/` | 1 | http-endpoint — `template.svg` + `bindings.yml`, no dark template |

Smallest plugin: `anthropic-status/` — a 20-line `probe.yml` plus `check.js`.
Largest script: `traefik/check.js` at 676 lines.

---

## probe.yml — top-level keys

`probe.yml` is a YAML (YAML Ain't Markup Language) manifest parsed by
`CatalogService.parseManifest` (`CatalogService.java:512-592`) into the `CatalogEntry`
record (`CatalogEntry.java:9-31`).

| Key | Type | Required | Default | Effect | Failure path |
|---|---|---|---|---|---|
| `id` | string | yes | — | catalog map key, install directory, the value `infrastructure.yml` writes as `probe:` | if absent then `parseManifest` returns null and the plugin is dropped with no log line (`CatalogService.java:514-515`) |
| `name` | string | no | `null` | catalog card title, default probe instance name | if absent then the card title is blank |
| `description` | string | no | `null` | catalog card subtitle | none |
| `updated` | `YYYY-MM-DD` | no | `""` | drives "update available" | if not ISO-8601 then `checkUpdates`' string `compareTo` misorders changelog entries (`CatalogService.java:730-732`) |
| `icon` | Lucide icon name | no | `null` | icon on the catalog card and probe row | if the name is unknown then nothing renders |
| `category` | string | no | `""` | groups the plugin on the catalog screen (`AdminCatalogView.vue:56`) | `install()` drops the key — see [F2](#fails-silently--symptom-cause-fix) |
| `dev` | boolean | no | `false` | `true` excludes the plugin from agent delivery (`CatalogService.java:120-125`) | if `true` then no agent ever runs the probe |
| `shell` | `none` \| `optional` \| `required` | no | `none` | `required` demands a non-read-only agent | if `required` and the agent is read-only then the probe returns state ERROR, message "Probe requires shell access but agent is read-only" (`ProbeRunner.java:129-136`) |
| `changelog` | list of `{date, note}` | no | `[]` | "what's new" list on an available update | `date` is compared as a string |
| `params` | list of maps | no | `[]` | configuration inputs — see [params:](#params--declaring-configuration-inputs) | none |
| `output` | list of maps | no | `[]` | display metadata and action declarations — see [output:](#output--declaring-what-a-probe-emits) | if a stream path has no matching entry then the raw key is shown and the type is guessed from the key name |
| `layout` | list of tile maps | no | `null` | dashboard tiles — see [layout:](#layout--declaring-dashboard-tiles) | passed through verbatim; an unknown `widget:` renders an empty cell with no error |
| `plate` | map | no | `null` | 3D topology plate specification (`CatalogService.java:564-567`) | **0 of 44 shipped plugins use `plate:`** — the key is supported and unexercised |

Measured across the 44 shipped plugins: `id`/`name`/`description`/`updated`/`icon`/
`category`/`params`/`output` 44 each · `changelog` 36 · `layout` 11 · `shell` 6 (all
`required`) · `dev` 0 · `plate` 0.

### Keys that appear in shipped manifests but are never read

| Key | Plugins declaring it | Reality |
|---|---|---|
| `suggestedThresholds:` | 3 — host-metrics, system-cpu, system-memory | `parseManifest` never reads the key, and grepping Java, TypeScript and Vue finds zero references. Thresholds come only from `infrastructure.yml`. `writing-probes.md:726-734` documents `suggestedThresholds` as if it worked; it does not. |
| `actionScripts:` | 1 — lifx | `parseManifest` never reads the key. Action scripts are discovered purely from `action-*.js` filenames (`CatalogService.java:396-417`, `:492`). Deleting the lifx block changes nothing. |

---

## output: — declaring what a probe emits

An `output:` entry describes how to render **one stream path**, or declares **one action**.
An `output:` entry never produces data; `check.js` produces data by returning
`streamValues`. Each entry is parsed into `CatalogEntry.OutputSpec`
(`CatalogEntry.java:95-124`).

```yaml
output:
  - path: worstGapSec
    type: number
    label: Worst gap
    unit: s
    description: Seconds not covered on the worst feed this hour
```

| Field | Type | Default | Effect |
|---|---|---|---|
| `path` | string | `""` (`CatalogEntry.java:111`) | the stream key, or a `{var}` / `*` pattern. `""` is the primary value shown on the probe row |
| `type` | string | `state` (`CatalogEntry.java:112`) | selects the formatter and the storage class |
| `label` | string | `null` | display name; `{var}` captures are substituted into it |
| `unit` | string | `null` | suffix appended after a formatted number, e.g. `s`, `ms` |
| `description` | string | `null` | catalog screen only — never rendered in the probe tree |
| `icon` | Lucide icon name | `null` | icon on a `type: group` node |
| `i18n` | map of locale → label | `null` | internationalisation; overrides `label` when the browser locale matches |
| `confirm` | string | `null` | actions only — confirmation prompt text, with `{var}` substitution |
| `dangerous` | boolean | `false` (`CatalogEntry.java:119`) | actions only — destructive styling |
| `params` | list of maps | `null` | actions only — form fields shown before the action runs |
| `presets` | list of maps | `null` | actions only — named JavaScript generators that fill the form |

### Declaration order controls render order

`StreamTree.orderByOutputSpec` (`StreamTree.vue:107-131`) renders tree nodes in `output:`
declaration order, interleaving actions and values. Any stream path not matched by an
`output:` entry is appended after everything that was matched. `lifx/probe.yml:74-193`
exploits this by declaring the five actions before the display values, so the buttons sit
at the top of each light's group.

### Types

| `type` | Renders as | Storage | Notes |
|---|---|---|---|
| `state` | uptime timeline | aggregated | the default when `type:` is omitted |
| `number` | thousands-grouped digits, then `unit` | aggregated | `1'435'588`, not `1435588` |
| `compact` | `715k`, then `unit` | aggregated | 1 use — plaiiin-mirror |
| `percent` | value **×100**, 1 decimal, `%` | aggregated | emit a fraction — see [F5](#fails-silently--symptom-cause-fix) |
| `bytes` | automatic KB/MB/GB/TB | aggregated | `unit` is ignored |
| `duration` | `3h 12m` from a seconds value | aggregated | `unit` is ignored |
| `boolean` | Yes / No | aggregated | |
| `label` | as-is | on change only | discrete — change timeline, no sparkline |
| `string` | as-is | on change only | discrete |
| `timestamp` | relative time, e.g. "3m ago" | on change only | accepts milliseconds since epoch or ISO-8601 |
| `color` | colour swatch | raw | hex, or `h,s,b` |
| `location` | inline mini-map | on change only | `lat,lon` |
| `image` | inline image | — | 1 use — webcam |
| `mjpeg` | inline Motion JPEG stream | — | 1 use — webcam |
| `log` | log viewer | raw | |
| `group` | collapsible section header | not a value | accepts `icon` |
| `action` | button | not a value | see [Action scripts](#action-scripts--turning-a-declaration-into-a-button) |

Storage classes are the concern of the server's data model. The Storage column of the
output type table states only which class each `type` selects.

Measured across 219 `output:` entries in the 44 shipped plugins: `number` 80 · `state` 30 ·
`group` 20 · `bytes` 18 · `percent` 16 · `action` 14 · `string` 13 · `label` 12 ·
`duration` 5 · `timestamp` 3 · `color` 2 · one each of `hostname`, `text`, `compact`,
`location`, `image`, `mjpeg`. `hostname` and `text` are not real output types — no
formatter branch matches either, so both fall through to the numeric default.

### Path matching

`getOutputType`, `resolveLabel` and `resolveUnit` each run the same two-pass match
(`StreamTree.vue:291-303`, `:205-227`, `:309-320`):

1. The full stream path is matched against each `path:` pattern. `{var}` matches exactly
   one path segment and captures it. `*` matches exactly one path segment.
2. If pass 1 found nothing, the **leaf segment** of the stream path is matched against the
   leaf segment of each pattern.

Rules:

- If a pattern captures `{n}`, then `{n}` in `label` and in every `i18n` value is replaced
  by the captured segment. `label: "Core {n}"` with `n=3` renders `Core 3`.
- If two patterns match the same path, then the first in declaration order wins for type,
  label and unit.
- If only pass 2 matches, then one entry covers every prefix: `{mount}/percent` with
  `label: Usage` labels the `percent` child under every mount without enumerating mounts.
- If a leaf name is reused at two different depths, then pass 2 applies the wrong label to
  one of them. Disambiguate by declaring the full path.

`*` is a path-segment wildcard, **not** a regular-expression quantifier. `matchPattern`
escapes the pattern before re-expanding the two pattern constructs. `plaiiin-mirror/probe.yml:106-110`
records the incident: `coverage/*` once reached the regular expression raw, became a
quantified slash, and matched nothing for the entire life of that probe; `network-scan`'s
`*/ports` became `/^*\/ports$/`, which throws "nothing to repeat" — and because
`matchPattern` runs inside the `tree` computed property, that throw takes down the whole
stream tree, not one label.

### unit

`unit` is the suffix rendered after a numeric value. `CatalogEntry.java:88-93` records
that `unit` was accepted in `probe.yml` and **silently discarded** by `OutputSpec` for as
long as that record existed, so `worstGapSec` — declared `unit: s` — rendered as a bare
`5`. The same comment states the standing hazard: every place that hand-copies an
`OutputSpec` into a result map has to copy `unit` too, or `unit` is dropped again one
layer further out. Three such copy sites exist — `CatalogService.java:784`,
`StatusTree.java:797`, `StatusTree.java:924`. All three carry `unit` today. No test
enforces it.

Rules:

- If `type` is `number` or `compact`, then `unit` is appended (`StreamTree.vue:369-372`).
- If `type` is `bytes`, `percent` or `duration`, then the formatter supplies its own
  suffix and `unit` is ignored.

Measured: **1 of 44** plugins declares `unit` — plaiiin-mirror, 2 entries.

### label and i18n

Label resolution order is `i18n[locale]` → `label` → the raw stream key, where `locale` is
`navigator.language.split('-')[0]` (`StreamTree.vue:213-215`). Pattern captures are
substituted into the localised string as well, so `i18n: { de: "Kern {n}" }` with `n=3`
renders `Kern 3`.

Measured: **61 of 219** `output:` entries carry no `label:` and therefore render their raw
camelCase key. `plaiiin-mirror/probe.yml:34-38` documents this as the reason
`unacknowledgedSubscriptions` and `droppedTrades` appeared on a project page as
identifiers beside properly-named siblings. **1 of 44** plugins declares `i18n` —
system-location, 6 German entries.

---

## params: — declaring configuration inputs

A `params:` entry declares one configuration input for the probe. Each entry is parsed
into `CatalogEntry.ParamSpec` (`CatalogEntry.java:126-158`) and reaches `check.js` as
`ctx.params.<name>`.

| Field | YAML key | Default | Effect |
|---|---|---|---|
| `name` | `name` | — | the key under `ctx.params` |
| `type` | `type` | `string` (`CatalogEntry.java:149`) | semantic type; selects the form widget and enables host/endpoint dependency tracking |
| `required` | `required` | `false` | form validation |
| `fixed` | `fixed` | `false` | value is shown in the form but not editable |
| `configurable` | `configurable` | **`!fixed`** (`CatalogEntry.java:142`) | whether the field appears in the add/edit form at all |
| `defaultValue` | `default` | `null` | pre-filled into the probe assignment even if the operator never opens the form (`AgentController.java:706-712`) |
| `credentialType` | `credential_type` | `null` | intended to filter the credential picker — see [F3](#fails-silently--symptom-cause-fix) |
| `description` | `description` | `null` | form help text |
| `options` | `options` | `null` | allowed values for `type: select` |

`configurable` defaults to the inverse of `fixed`, which produces three usable modes:

| Mode | YAML | Form behaviour |
|---|---|---|
| Required | `required: true` | operator must supply a value |
| Configurable | `default: <value>` | pre-filled, editable |
| Fixed | `fixed: true` + `default: <value>` | shown, not editable |

`anthropic-status/probe.yml:13-17` is the canonical fixed-param plugin: its only param is
the vendor status-page Uniform Resource Locator (URL), marked `fixed: true`, so an
operator adds the probe and configures nothing.

Types in use across 78 params in the 44 shipped plugins: `url` 23 · `string` 15 ·
`number` 9 · `hostname` 8 · `credential` 7 · `port` 7 · `boolean` 4 · `int` 4 ·
`select` 1. Both `number` and `int` are in use; no coercion layer exists, so each reaches
the sandbox exactly as YAML parsed it.

### Credential parameters

The credential reference is a param **value** in `infrastructure.yml`, not a param type:

```yaml
agentProbes:
  - probe: lifx
    params:
      token: "credential:lifx-token"
```

`resolveCredentialRef` (`AgentController.java:76-98`) runs over the probe's `extraParams`
at assignment time and substitutes the **raw secret string**. `check.js` receives a
string, never a wrapper object:

| Credential type | Value delivered to `ctx.params.<name>` |
|---|---|
| Bearer | `token` |
| Basic | `username + ":" + password` — one string, not base64-encoded, not an object |
| Header | `headerValue` only — `headerName` is not delivered |
| OAuth2 | `clientSecret` only |
| TLS | `certPem` only — private key and certificate authority are not delivered |
| SSH | `privateKey` only |

Rules:

- If the credential name does not resolve, then `resolveCredentialRef` logs a warning and
  returns null, and `AgentController.java:721` omits the param entirely. `check.js` sees
  `undefined`, not an error.
- If a probe needs both halves of a Header or Basic credential, then the second half must
  come from a separate plain param — the resolver delivers one field.

Two shipped documents describe a credential shape that does not exist on this path.
`writing-probes.md:79-95` shows `ctx.params.credentials.token`, `.username` and
`.headerName`; no such object is ever constructed. `credentials-store.md:48-54` describes
the agent fetching `GET /api/agents/{name}/credentials/{credentialName}`; that endpoint
does not exist in the server, and substitution is entirely server-side.

---

## Action scripts — turning a declaration into a button

An action is an operator-triggered operation attached to a stream path. A working action
needs **4** pieces aligned. Three fail silently when missing; the fourth fails with an
error string in the run dialog.

| # | Piece | Location | If missing |
|---|---|---|---|
| 1 | an `output:` entry with `type: action` | `probe.yml` | no button renders |
| 2 | `ctx.action.add(path)` during `check(ctx)` | `check.js` | the button renders; the server refuses with `Action not declared by probe: <path>` (`AgentController.java:1096-1099`) |
| 3 | `action-<leaf>.js` | the plugin directory | the button renders; the server refuses with `No action script found for: <leaf>` (`AgentController.java:1119-1121`) |
| 4 | a stored result for the probe | runtime | the server refuses with `No result available for probe (action not validated)` (`AgentController.java:1100-1102`) |

`<leaf>` is the **last segment** of the action path. Action path
`{stack}/{service}/restart` requires the file `action-restart.js`
(`AgentController.java:1105-1108`).

### Dispatch sequence

`POST /api/agents/action` with body `{probe, action, userParams}`
(`AgentController.java:1059`) performs, in order:

1. Resolve the probe and the agent that owns it. If the probe is not assigned to an agent,
   then the request is refused (`AgentController.java:1089-1092`).
2. Validate the action path against the `actions` list stored on the probe's last result.
   That list comes from `ctx.action.add()` calls (`ProbeSandbox.java:145-149`). This
   validation is the only real gate (`AgentController.java:1094-1103`).
3. Look up the script by leaf name in `actionScripts` (`AgentController.java:1110-1122`).
4. Build the parameter map: catalog `default:` values, then `url` and `host`, then
   resolved credential references, then the operator's form values on top
   (`AgentController.java:1134-1158`).
5. Push a `probe-action` command over Server-Sent Events (SSE), falling back to the
   heartbeat queue if the SSE channel is not connected.

### Writing the handler

An action script defines `function action(ctx)` and returns the same shape as `check(ctx)`
— `{ state, message, ... }`. On the agent, `ProbeActionCommand.java:82` performs:

```java
String wrapped = scriptSource.replace("function action(", "function check(");
```

That is a literal string replacement. The handler must be spelled exactly
`function action(ctx)`. If the source says `function action (ctx)`,
`const action = (ctx) => …`, or anything else, then the replacement does not fire, the
sandbox finds no `check`, and the action returns `ERROR: … check is not defined`.

Three context params are injected, derived from the action path
(`ProbeActionCommand.java:66-73`). For action path
`home/office/color/Desk Lamp/setColor`:

| Param | Value |
|---|---|
| `ctx.params.container` | `home/office/color/Desk Lamp` — always named `container`, whatever the probe monitors |
| `ctx.params.contextLeaf` | `Desk Lamp` |
| `ctx.params.actionPath` | `home/office/color/Desk Lamp/setColor` |

If the action returns `streamValues`, then the server merges those into the cached probe
result immediately so the interface updates before the next tick
(`AgentController.java:604-625`), and the agent re-runs the probe to confirm
(`ProbeActionCommand.java:96-98`).

### confirm and dangerous

`confirm` and `dangerous` are fields of the **OutputSpec**, read by
`StreamTree.getActionMeta` (`StreamTree.vue:134-147`) and handed to the action dialog as
`confirm-message` and `dangerous` (`StreamTree.vue:581-582`). Pattern captures from the
matched path are substituted into `confirm` (`StreamTree.vue:140-144`), which is how
`docker-services/probe.yml:61` turns `confirm: "Restart {service} in stack {stack}?"` into
*"Restart api in stack portal?"*.

🚨 Neither field is a permission control. `POST /api/agents/action` carries **no**
`@PreAuthorize` annotation, so any authenticated principal can invoke any declared action.
The Docker control endpoint next to it, `POST /{name}/docker/{action}`, **is** role-gated
(`AgentController.java:894-895`). `dangerous: true` produces destructive styling and a
confirmation prompt in the browser, and nothing on the server.

Measured: `confirm` — 1 plugin, 6 entries (docker-services). `dangerous` — 2 plugins,
5 entries (docker-services 4, folder-watch 1).

### Action params and presets

`params` and `presets` on an action `output:` entry are pass-through
`List<Map<String,Object>>` (`CatalogEntry.java:98-99`).

| Concept | Contract |
|---|---|
| Scalar param | `{name, type, label, default, widget}`; widgets with a dedicated branch are `slider`, `hue-slider`, `kelvin-slider`, `color-picker` (`ParamField.vue:140-194`) |
| Unknown widget | falls through to a plain text or number input — including `select`, for which `ParamField.vue` has no branch |
| Array param | `type: array` plus `size: { from: <streamPath> }` or `size: { fixed: <n> }` (`ActionDialog.vue:17`) |
| Preset | `{id, name, description, generator}`; `generator` is JavaScript source evaluated as `new Function('ctx', source)` against live stream values (`ActionDialog.vue:75`) |

lifx is the only shipped plugin using either: 3 actions with `params`, 5 presets on
`setZoneColors`.

---

## layout: — declaring dashboard tiles

`layout:` is a list of tile maps, passed through to the frontend verbatim
(`CatalogService.java:551-559`, attached to results at `AgentController.java:869-871`).
`layout:` declares which values become tiles and how each tile is sized and grouped.

| Key | Type | Meaning |
|---|---|---|
| `tile` | `<cols>x<rows>` | grid span for the tile |
| `widget` | string | which renderer draws the tile |
| `path` | string | the stream path the tile reads, `{var}` patterns allowed |
| `paths` | string | a glob covering several stream paths, e.g. `core/*` |
| `label` | string | tile caption |
| `group` | string | the `{var}` prefix that repeats the tile once per discovered instance |
| `style` | string | variant for `widget: action` — `button`, `switch`, `knob`, `slider`, `lever` |
| `slots` | list | nested tiles for container widgets such as `tray` |
| `max` | number | full-scale value for `widget: gauge` |

```yaml
layout:
  - tile: 1x1
    widget: gauge
    path: "{location}/{group}/{type}/{light}/brightness"
    label: Brightness
    max: 1
    group: "{location}/{group}/{type}/{light}"
```

Rules:

- If a tile's concrete `path` is not emitted by `check.js` for a given instance, then that
  tile is skipped for that instance rather than rendered empty.
- If `widget:` names a renderer the target view does not know, then the cell renders
  **nothing** — no error, no warning, no log line.

The widget catalogue, the two-renderer split, and the 4-unit width clamp are owned by
[Rendering Pipeline](rendering-pipeline.md). Consult that
document before choosing a `widget:` value; `probe.yml` accepts any string.

Measured: **11 of 44** shipped plugins declare `layout:`.

---

## detect.js — declared, loaded, never executed

`detect.js` was intended for auto-discovery: given a host, report whether the probe's
subject is present and suggest parameters. Four plugins ship one — docker-services,
postgres-check, redis, traefik. The intended contract, read off `redis/detect.js`:

```js
function detect(ctx) {
  var result = ctx.tcp.connect(ctx.params.hostname || 'localhost', 6379, 2)
  return { available: result.connected, params: { port: 6379 } }
}
```

— return `{ available: boolean, params?: object }`.

**Nothing executes `detect.js`.** `detectSource` is loaded
(`CatalogService.java:356-364`, `:471-474`), written back on install
(`CatalogService.java:161-163`), and exposed through `hasDetect()`
(`CatalogEntry.java:70`). `hasDetect()` has zero callers across Status-Server,
Status-Agent and Status-Frontend, and `detectSource` has no reader outside
`CatalogService`. There is no discovery endpoint, no `detect` command type, and no
frontend caller.

Two independent confirmations that `detect.js` has never run:

| Evidence | Detail |
|---|---|
| `docker-services/detect.js:3` calls `ctx.exec('docker info')` | `ctx.exec` does not exist. The sandbox binds `ctx.shell` (`ProbeSandbox.java:98`). The call sits inside `try/catch`, so it would return `{available: false}` unconditionally if it ever ran. |
| `redis/detect.js:3` and `postgres-check/detect.js:3` read `ctx.params.hostname` | The assignment builder only populates `hostname` for probes that are already configured with a host, so discovery could not run before configuration. |

Ship a `detect.js` only as a forward-compatible declaration. Do not build behaviour on it.

---

## Fan-out — streamValues vs scriptResult.services

Both mechanisms let one probe execution report N things. The two are not interchangeable.

| Dimension | `streamValues` with `{var}` paths | `scriptResult.services[]` |
|---|---|---|
| What it produces | keys inside one probe's result (`ProbeSandbox.java:123-125`) | real `StatusNode` children of type `service` (`AgentController.java:638-668`) |
| Shape in the tree | groups and leaves inside the probe card | service → probe nodes beneath the probe |
| Per-item payload | any type, any depth | `name`, `status`, `message` only |
| Labels, units, icons | from `output:` | none — the `name` string is all there is |
| Actions | supported | not supported |
| History written | one series per path (`AgentController.java:793-807`) | state ordinal only, one series per child (`ProbeScheduler.java:370-386`) |
| Reference from `projects:` | resolves to a synthesized slice card via `buildProbeSlice` (`StatusTree.java:725-805`) | resolves by exact child-name walk and is cloned whole (`StatusTree.java:698-709`) |
| Requests per tick | 1 probe execution | 1 probe execution |

Retention and rollup behaviour for each series kind is owned by
the server's data model. The "History written" row of the fan-out comparison table
states only which series each mechanism creates.

### Choosing

| Situation | Use | Example |
|---|---|---|
| The items are measurements you want charted, labelled, unit-suffixed or actionable | `streamValues` with `{var}` paths | `docker-services` emits `{stack}/{service}/cpu`, `/memory`, `/state` plus per-service actions from one socket sweep |
| The items are third-party statuses with nothing to chart | `scriptResult.services[]` | a vendor status page's component list — real nodes that aggregate into the parent's status |

### The expensive mistake

Neither mechanism is the costly error. The costly error is declaring **N probe instances**
in `infrastructure.yml` where one fan-out probe would serve. N instances multiply the
request count against the same endpoint by N on every tick, and each instance carries its
own interval and timeout. If the data arrives in one call, emit it from one probe.

### Reference asymmetry

`buildProbeSlice` hand-copies the `OutputSpec` (`StatusTree.java:790-803`) and carries only
`path`, `type`, `label`, `unit`, `icon` and `i18n`. `buildProbeSlice` drops `confirm`,
`dangerous`, `params` and `presets`. So an action reached through a project-tab path
reference loses its confirmation prompt and its parameter form, while the same action on
the Systems page keeps both. `StatusTree.java:911-930` carries the same omission for the
legacy no-agent-result path.

---

## Install and sync — how a plugin reaches an agent

Status keeps the catalog in three layers (`CatalogService.java:20-29`):

| Layer | Location | Mutable |
|---|---|---|
| Built-in | `classpath:catalog/probes/*/probe.yml` | no — shipped inside the jar |
| Installed | `{config-path}/probes/<id>/` | yes — agents and the Probe IDE read this layer |
| Comparison | `getAvailableUpdates()` | compares the `updated` strings |

Sequence:

1. `autoInstallBuiltins()` (`CatalogService.java:89-106`) runs at startup and installs
   every built-in that has no installed copy.
2. `install()` (`CatalogService.java:136-193`) **re-serialises** the parsed entry through
   `toManifestMap()` (`CatalogService.java:745-802`) and writes the sidecar files. This is
   not a file copy — see [F2](#fails-silently--symptom-cause-fix) for what is lost.
3. Change detection runs on two tracks: a `WatchService` with a 500 ms debounce
   (`CatalogService.java:636-667`), plus a 30 s modification-time poll
   (`CatalogService.java:601-614`) because kqueue on macOS misses events.
4. The agent receives scripts inline in its heartbeat's probe assignments
   (`AgentController.buildProbeAssignments`, `:684-753`), which attach `scriptSource`,
   `actionScripts` and `shell` per assignment.

Timing rule: if a plugin file changes, then an agent sees it after the server's detection
lag (500 ms to 30 s) plus one heartbeat interval (`agent.heartbeat-interval`, default
**30 s**, `HeartbeatService.java:89`) — up to roughly 60 s.
`writing-probes.md:740` claims 3 seconds; that figure is stale.

`/api/catalog/sync` still exists (`CatalogController.java:61-72`) and returns
`getAllInstalled()`, which excludes `dev: true` entries. **The agent never calls it** — a
grep of Status-Agent finds only `register`, `heartbeat`, `command-*`, `log-stream`,
`probe-results` and `probe-stream`. `/api/catalog/sync` is also on the public filter chain
(`SecurityConfig.java:58`), so every installed probe's script source is readable without
authentication.

### Editing an installed plugin

| Action | Endpoint | Preserves comments and key order |
|---|---|---|
| Save `check.js` | `POST /api/ide/probe-save` (`ScriptPlaygroundController.java:379`) | not applicable |
| Save `probe.yml` | `POST /api/ide/probe-definition` (`ScriptPlaygroundController.java:413`) | **yes** — writes the string verbatim |
| Toggle `dev` | `POST /api/ide/toggle-dev` (`ScriptPlaygroundController.java:547`) | **no** — round-trips through a generic Map and strips every comment |
| Install / update | `POST /api/catalog/install/{id}` / `update/{id}` | **no** — see [F2](#fails-silently--symptom-cause-fix) |

There is no Probe IDE endpoint for `action-*.js`, `detect.js` or `icon.svg`. Those files
must be placed on the filesystem under `{config-path}/probes/<id>/`; they survive because
`loadFileEntries` rescans the directory on every reload.

---

## Fails silently — symptom, cause, fix

Each entry below fails without an error, an exception or a log line.

### F1 — the plugin does not appear in the catalog at all

| | |
|---|---|
| **Symptom** | The directory exists under `probes/`, the server logged no warning, and the plugin is absent from `/api/catalog` and from the Add Probe list. |
| **Cause** | `probe.yml` has no `id:` key. `parseManifest` returns null (`CatalogService.java:514-515`) and both loaders test `if (entry != null)` before storing, so the plugin is dropped without a log line. A duplicate `id:` in two directories has the same shape of failure — `target.put(entry.id(), …)` (`CatalogService.java:419`) means the last directory scanned silently wins. |
| **Fix** | Add `id:` to `probe.yml`. Make `id:` unique, and make it equal to the directory name — because `install()` writes to `probes/{id}/`, a directory named `foo/` containing `id: bar` produces two directories for one plugin. |

### F2 — category and credential_type vanish from the installed copy

| | |
|---|---|
| **Symptom** | Every plugin appears under "other" on the catalog screen, the credential picker is unfiltered, and hand-written comments in `probe.yml` are gone. |
| **Cause** | `toManifestMap` (`CatalogService.java:745-802`) writes `id`, `name`, `description`, `updated`, `icon`, `dev`, `shell`, `changelog`, `params`, `output`, `layout` and `plate`. `toManifestMap` does not write `category:`, and does not write `credential_type` inside a param (`CatalogService.java:763-774`). `autoInstallBuiltins()` runs `install()` on first startup, so the installed copy — the copy agents and admin screens read — has already lost both fields, plus all comments and the original key order. `plaiiin-mirror/probe.yml` carries roughly 40 lines of incident notes that do not survive one install. |
| **Fix** | Add `category` and `credential_type` to `toManifestMap`, or stop round-tripping on install. Until then: edit installed manifests through `POST /api/ide/probe-definition`, which writes the string verbatim (`ScriptPlaygroundController.java:413-430`), and avoid `POST /api/ide/toggle-dev`, which strips comments (`ScriptPlaygroundController.java:550-569`). |

### F3 — credential_type never filters the picker, and default never pre-fills

| | |
|---|---|
| **Symptom** | A param declared `credential_type: bearer` shows every credential of every type in the dropdown. A param declared `default: 6379` opens the Add Probe form empty. |
| **Cause** | Jackson serialises the record component names, so `/api/catalog` emits `credentialType` and `defaultValue`. `ProbeAddForm.vue:159` reads `p.credential_type` and `ProbeAddForm.vue:124` reads `p.default`. Snake case versus camel case — both reads are always `undefined`. `DefaultProbeForm.vue:78` reads `p.defaultValue` correctly, so the same plugin behaves differently in two forms. |
| **Fix** | Change the frontend reads to `credentialType` and `defaultValue`, or add `@JsonProperty` aliases on `ParamSpec`. Note that [F2](#fails-silently--symptom-cause-fix) strips `credential_type` from installed manifests as well — both must be fixed for the filter to work. |

### F4 — an action button that can never run

| | |
|---|---|
| **Symptom** | The button renders in the tree. Clicking it returns `Action not declared by probe` or `No action script found for`. |
| **Cause** | Only 1 of the 4 required pieces is present. `folder-watch/probe.yml:51-76` declares 3 actions, the directory ships 1 `action-*.js`, and `folder-watch/check.js` calls `ctx.action.add` **zero** times — so all 3 buttons are refused server-side. `host-metrics/probe.yml:90-121` goes further with 5 `widget: action` tiles in its topology tray, no `output:` entries and no scripts at all. |
| **Fix** | For every `type: action` entry, ship `action-<leaf>.js` and call `ctx.action.add(<path>)` inside `check(ctx)` for each instance where the action currently applies. |

### F5 — a percent value renders 100× too large

| | |
|---|---|
| **Symptom** | A gauge tile shows `14%` while the same value in the expanded tree shows `1450.0%`. |
| **Cause** | Two formatters disagree. `StreamTree.vue:364` is `(v * 100).toFixed(1) + '%'` — unconditional. `format.ts:90` is `(v <= 1 ? v * 100 : v).toFixed(0) + '%'` — tolerant of either scale. |
| **Fix** | Emit `percent` values as a **fraction** in the range 0–1. The catalog convention is the fraction: `system-memory/check.js:9` and `system-cpu/check.js:20` both divide by 100, and `docker-services/check.js:138-142` emits four-decimal ratios. `system-cpu/check.js:5` is the one outlier, emitting the `""` path as 0–100; it escapes notice only because the `""` path is never shown as a tree row. |

### F6 — the primary value charts response time instead of the declared metric

| | |
|---|---|
| **Symptom** | `output:` declares `- path: ""` with `type: bytes`, and the primary chart plots milliseconds. |
| **Cause** | `AgentController.java:799` seeds the history batch with `sv[""] = responseMs` (or the message, if no response time) **before** merging the script's own `streamValues` (`AgentController.java:801-806`). If `check.js` emits no `""` entry, the primary series silently becomes response time. |
| **Fix** | If `output:` declares `path: ""` as anything other than response time, then `check.js` must emit `streamValues['']` explicitly. A probe-supplied `""` entry wins, because the merge loop runs after the seed. |

### F7 — a layout tile renders an empty cell

| | |
|---|---|
| **Symptom** | A tile occupies its grid space and draws nothing. No console error, no log line. |
| **Cause** | `widget:` names a renderer the target view does not implement. The two views implement different widget sets and the chain has no fallback branch. |
| **Fix** | Choose a widget from the catalogue in [Rendering Pipeline](rendering-pipeline.md), and confirm it is implemented by the view the tile is meant for. |

### F8 — shell: optional has no effect

| | |
|---|---|
| **Symptom** | A plugin declares `shell: optional` expecting a degraded mode; behaviour is identical to omitting the key. |
| **Cause** | `ProbeRunner.java:131` tests `"required".equals(shellReq)` only. `wantsShell()` (`CatalogEntry.java:73`) has zero callers. Whether `ctx.shell` works is decided entirely by the agent's own `readonly` flag (`ProbeRunner.java:57`). |
| **Fix** | Use `shell: required` when the probe cannot work without a shell. Otherwise omit the key and have `check.js` handle a failing `ctx.shell.run` itself. |

### F9 — an action handler that is never wrapped

| | |
|---|---|
| **Symptom** | The action returns `ERROR: ReferenceError: check is not defined`. |
| **Cause** | `ProbeActionCommand.java:82` rewrites the source with a literal `replace("function action(", "function check(")`. Any other spelling of the declaration is not matched. |
| **Fix** | Declare the handler as exactly `function action(ctx)` — no space before the parenthesis, no arrow function, no export. |

---

## Worked example — minimal plugin

`anthropic-status/` is the smallest shipped plugin: 2 files, no host to configure, one
primary state value.

```yaml
# probes/anthropic-status/probe.yml
id: anthropic-status
name: Anthropic Status
description: Monitor Anthropic Claude API service status
updated: 2026-04-06
icon: brain
category: cloud

changelog:
  - date: 2026-04-06
    note: Initial release

params:
  - name: url
    type: url
    fixed: true
    default: https://status.anthropic.com/api/v2/summary.json
    description: Anthropic Status API (fixed)

output:
  - path: ""
    type: state
    description: Worst status across all components
```

## Worked example — full-surface plugin

`lifx/` is the only shipped plugin exercising `{var}` hierarchies, per-instance actions,
action `params`, `presets`, a `credential` param and per-instance `layout` tiles together.
The plugin is `probe.yml` (240 lines), `check.js`, and 5 `action-*.js` files.

```yaml
params:
  - name: token
    type: credential
    credential_type: bearer      # stripped from the installed copy — see F2
    required: true

output:
  - path: "{location}/{group}/{type}/{light}"
    type: group
    label: "{light}"
    icon: lightbulb
  - path: "{location}/{group}/{type}/{light}/setColor"
    type: action
    label: "Set Color"
    params:
      - { name: hue, type: number, label: Hue, min: 0, max: 360, default: 0, widget: hue-slider }
  - path: "{location}/{group}/{type}/{light}/brightness"
    type: percent
    label: Brightness

layout:
  - tile: 1x1
    widget: gauge
    path: "{location}/{group}/{type}/{light}/brightness"
    group: "{location}/{group}/{type}/{light}"
    max: 1
```

`lifx/check.js` emits the concrete paths and calls
`ctx.action.add(prefix + '/setColor')` per light. `lifx/action-setColor.js` declares
`function action(ctx)` and identifies the target light through `ctx.params.contextLeaf`.

---

## Authoring checklist

| Check | Rule |
|---|---|
| Identity | `id:` present, unique, equal to the directory name |
| Versioning | `updated:` is `YYYY-MM-DD` and is bumped whenever `changelog:` grows |
| Labels | every emitted stream path has an `output:` entry carrying `label:` — 61 of 219 shipped entries do not, and each renders a camelCase key |
| Percent | `percent` paths emit a fraction in the range 0–1 |
| Units | numeric paths that are not self-describing carry `unit:` |
| Actions | every `type: action` has a matching `action-<leaf>.js` **and** a `ctx.action.add()` call |
| Destructive actions | carry `confirm:` and `dangerous: true`, knowing neither is enforced server-side |
| Category | `category:` is set, knowing `install()` drops it |
| Handler spelling | action handlers are spelled exactly `function action(ctx)` |
| Script limits | the statement limit is 50'000 per execution (`ProbeSandbox.java:83`); every run gets a fresh context with no state carried between ticks |

---

## Field schema — machine-readable

```yaml
# Complete probe.yml schema. Parsed by CatalogService.parseManifest
# (Status-Server/src/main/java/com/plaiiin/status/catalog/CatalogService.java:512-592)
# into CatalogEntry (CatalogEntry.java:9-31). Verified 2026-08-28.

files:
  probe.yml:            {required: true,  effect: "manifest; absent => directory skipped"}
  check.js:             {required: false, effect: "defines function check(ctx); populates scriptSource"}
  run.js:               {required: false, effect: "alternative to check.js; check.js wins if both exist"}
  detect.js:            {required: false, effect: "populates detectSource; NEVER EXECUTED — zero callers"}
  icon.svg:             {required: false, effect: "populates iconSvg; overrides the icon: name"}
  action-<name>.js:     {required: false, effect: "defines function action(ctx); keyed by <name>"}
  infographic/template.svg:      {required: false, effect: "populates svgTemplate"}
  infographic/template-dark.svg: {required: false, effect: "populates svgTemplateDark; light used if absent"}
  infographic/bindings.yml:      {required: false, effect: "populates bindingsYaml; ignored without template.svg"}

probe_yml:
  id:          {type: string,  required: true,  default: null,  effect: "catalog key + install dir; absent => plugin dropped silently"}
  name:        {type: string,  required: false, default: null,  effect: "catalog card title"}
  description: {type: string,  required: false, default: null,  effect: "catalog card subtitle"}
  updated:     {type: date,    required: false, default: "",    effect: "update detection; must be YYYY-MM-DD"}
  icon:        {type: string,  required: false, default: null,  effect: "Lucide icon name"}
  category:    {type: string,  required: false, default: "",    effect: "catalog grouping; DROPPED by install()"}
  dev:         {type: boolean, required: false, default: false, effect: "true => excluded from agent delivery"}
  shell:       {type: enum,    required: false, default: none,  values: [none, optional, required], effect: "required => ERROR on a read-only agent; optional is INERT"}
  changelog:   {type: list,    required: false, default: [],    item: {date: string, note: string}}
  params:      {type: list,    required: false, default: [],    item: param_spec}
  output:      {type: list,    required: false, default: [],    item: output_spec}
  layout:      {type: list,    required: false, default: null,  effect: "tile specs, passed through verbatim"}
  plate:       {type: map,     required: false, default: null,  effect: "3D plate spec; 0 of 44 plugins use it"}
  suggestedThresholds: {type: map, required: false, effect: "NEVER READ — parseManifest ignores it"}
  actionScripts:       {type: map, required: false, effect: "NEVER READ — scripts come from action-*.js filenames"}

param_spec:
  name:            {type: string,  required: true,  default: null,      effect: "key under ctx.params"}
  type:            {type: string,  required: false, default: string,    values: [string, int, number, boolean, hostname, port, url, path, map, select, credential]}
  required:        {type: boolean, required: false, default: false,     effect: "form validation"}
  fixed:           {type: boolean, required: false, default: false,     effect: "shown, not editable"}
  configurable:    {type: boolean, required: false, default: "!fixed",  effect: "false => hidden from the form"}
  default:         {type: any,     required: false, default: null,      effect: "pre-filled into the assignment; serialized as defaultValue"}
  credential_type: {type: string,  required: false, default: null,      values: [bearer, basic, header, oauth2, tls, ssh], effect: "intended picker filter; serialized as credentialType; DROPPED by install()"}
  description:     {type: string,  required: false, default: null,      effect: "form help text"}
  options:         {type: list,    required: false, default: null,      effect: "allowed values for type: select"}

output_spec:
  path:        {type: string,  required: false, default: "",     effect: "stream key or {var}/* pattern; \"\" is the primary value"}
  type:        {type: string,  required: false, default: state,  values: [state, number, compact, percent, bytes, duration, boolean, label, string, timestamp, color, location, image, mjpeg, log, group, action]}
  label:       {type: string,  required: false, default: null,   effect: "display name; {var} captures substituted"}
  unit:        {type: string,  required: false, default: null,   effect: "suffix; applied to number and compact only"}
  description: {type: string,  required: false, default: null,   effect: "catalog screen only"}
  icon:        {type: string,  required: false, default: null,   effect: "icon on a type: group node"}
  i18n:        {type: map,     required: false, default: null,   effect: "locale -> label; overrides label"}
  confirm:     {type: string,  required: false, default: null,   effect: "actions only; prompt text with {var} substitution; NOT a permission check"}
  dangerous:   {type: boolean, required: false, default: false,  effect: "actions only; styling only; NOT a permission check"}
  params:      {type: list,    required: false, default: null,   effect: "actions only; form fields"}
  presets:     {type: list,    required: false, default: null,   effect: "actions only; {id, name, description, generator}"}

action_requirements:
  - "output: entry with type: action"
  - "ctx.action.add(<path>) called during check(ctx)"
  - "action-<leaf>.js in the plugin directory, <leaf> = last path segment"
  - "a stored probe result carrying the actions list"
  - "handler declared as exactly: function action(ctx)"

action_injected_params:
  container:   "the action path minus its last segment; always named container"
  contextLeaf: "the last segment of the parent path"
  actionPath:  "the full action path"

credential_resolution:
  syntax:  "param VALUE of the form credential:<name> in infrastructure.yml"
  site:    "AgentController.resolveCredentialRef (AgentController.java:76-98)"
  scope:   "extraParams only"
  delivers: "a RAW STRING, never a wrapper object"
  bearer:  token
  basic:   "username + \":\" + password"
  header:  "headerValue only; headerName is lost"
  oauth2:  "clientSecret only"
  tls:     "certPem only"
  ssh:     "privateKey only"
  unresolvable: "param omitted entirely; ctx.params.<name> is undefined"

fan_out:
  streamValues:
    produces:  "keys inside one probe result"
    history:   "one series per path"
    supports:  [labels, units, icons, actions, charts]
  scriptResult_services:
    produces:  "StatusNode children of type service"
    history:   "state ordinal only, one series per child"
    supports:  []

propagation:
  server_detection: "500ms WatchService debounce, or a 30s modification-time poll"
  agent_delivery:   "inline in heartbeat probe assignments; agent never calls /api/catalog/sync"
  heartbeat_default: "30s (agent.heartbeat-interval)"
  worst_case:       "~60s from file write to agent execution"

sandbox_limits:
  statement_limit: 50000
  state_between_runs: none
  shell_enabled: "agent readonly flag only"
```
