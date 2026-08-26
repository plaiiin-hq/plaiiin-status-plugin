# `infrastructure.yml` — the complete schema

Every top-level section, from the loader's model classes. `infrastructure-model.md` covers
hosts, agents and agent policies in prose; this is the field-by-field reference.

```yaml
defaults:      {}    # Map<String,String> — inherited defaults
hosts:         []    # the physical tree: Agents / <host> / <probe>
projects:      []    # the logical view — tabs made of refs into the physical tree
sites:         []    # geographic + floor-plan placement
dependencies:  []    # third parties you depend on but do not run
agentProbes:   {}    # which probes every agent runs by default
agentCommands: {}    # which commands agents accept
agentCommandOverrides: {}   # per-agent command overrides
thresholds:    []    # warn/error cutoffs matched across probes
```

Only `hosts` and `projects` are needed for a working board. The rest are additive.

---

## `hosts`

| Field | Type | Notes |
|---|---|---|
| `name` | string | Also the **agent name** a decomposed probe binds to — see trap 1. |
| `address` | string | Hostname or IP the server/agent dials. |
| `user` | string | SSH user, for agent install and shell probes. |
| `labels` | map | Free-form (`provider`, `location`, `os`, `cpu`, `ram`, `disk`). Rendered on the host card. |
| `links` | list | `{ name, url }` — deep links shown on the host. |
| `services` | list | Services running on this host (see below). |
| `probes` | list | Host-level probes. |

## Probe entries

Whether under a host or a service, a probe entry accepts:

| Field | Type | Notes |
|---|---|---|
| `name` | string | Display name **and the reload key** — renaming re-registers, editing in place does not. |
| `probe` | string | Catalog probe id (`http-endpoint`, `tcp-port`, `docker-services`, …). |
| `target` | string | Full target URL. **Leaves the agent null so the server runs it** — the safe form on agentless hosts. |
| `host` / `port` | string / int | Decomposed form. ⚠️ **Binds the probe to an agent named after the host.** |
| `protocol` · `path` | string | Scheme and request path when decomposed. |
| `agent` | string | Explicit agent override; wins over the host-name default. |
| `interval` | int | Seconds between runs. Defaults to the catalog's. |
| `script` | string | Script id for SCRIPT probes. |
| `type` | string | Probe type override. |
| `url` | string | For dependency-style probes. |
| `command` | string | Command probes. |
| `container` | string | Docker container name. |

## `projects`

```yaml
projects:
  - name: Public Site           # becomes a tab
    apps:
      - name: Web
        icon: globe
        host: app-01.example.com     # optional pin
        hostAgents: true             # surface the host's own agent probes here
        links: [{ name: Docs, url: https://… }]
        refs: []                     # app-level refs
        services:
          - name: API
            icon: server
            type: spring-boot        # service-type catalog entry — auto-generates probes
            vars: { port: 8080 }     # substituted into the type's probe templates
            refs:
              - Agents / app-01.example.com / Web Reachable
            references:
              - { agent: app-01.example.com, probe: Docker, path: web-api, action: restart }
            probes: []               # inline custom probes
            links: []
```

`refs` are **whitespace-sensitive path strings** matched against the live tree — a miss
renders an empty node, silently. `references` is the structured form and additionally carries
an `action`, which is what puts a working button on the card.

## `dependencies`

Third parties you rely on but do not run.

```yaml
dependencies:
  - name: GitHub
    type: statuspage
    url: https://www.githubstatus.com
    script: statuspage           # JS mapper turning their status page into StatusNodes
    consumers: [Web, API]        # which apps degrade when this does
```

`consumers` is what makes a third-party outage visibly attach to *your* apps.

## `agentProbes` / `agentCommands` / `agentCommandOverrides`

```yaml
agentProbes:
  enabled: true
  probes: [system-cpu, system-memory, system-disk, system-location]
  params:
    system-disk: { warn: 85, error: 95 }

agentCommands:
  enabled: true
  commands: [restart, logs]

agentCommandOverrides:
  app-01.example.com: [restart]
```

Every approved agent runs the `agentProbes` list without per-host configuration. This is the
cheapest way to get uniform CPU/memory/disk coverage across an estate.

## `thresholds`

Warn/error cutoffs matched across probes, so you set them once rather than per probe.

```yaml
thresholds:
  - match: { probe: system-memory }
    warn: 80
    error: 90
  - match: { probe: system-disk }
    field: usedPercent          # which output path the cutoffs apply to
    warn: 85
    error: 95
```

`match` is a map of criteria; `field` selects the output path (defaults to the primary).

## `sites`

Geographic and floor-plan placement — hosts rendered on a map, or on drawn floors.

```yaml
sites:
  - name: HQ
    latitude: 47.37
    longitude: 8.54
    description: Main office
    floors:
      - name: Ground
        background: floor0.png
        calibration: { p1: [0,0], p2: [100,0], distance: 12.5, unit: m }
        walls:     [{ from: [0,0], to: [10,0] }]
        openings:  [{ type: door, wall: 0, at: 2.5, width: 0.9, sillHeight: 0, headHeight: 2.1 }]
        zones:     [{ shape: rect, label: Server room, at: [2,2], size: [4,3] }]
        furniture: [{ type: rack, label: R1, at: [3,3], size: [0.6,1.0], rotation: 90 }]
        stairs:    [{ at: [8,1], size: [1,3], rise: 3.0, label: Up }]
        placements:[{ ref: "Agents / app-01.example.com", at: [3,3], label: app-01, icon: server }]
        roof: flat
        wallStyle: solid
```

`calibration` maps two pixel points to a real-world `distance`, so everything else can be
authored in metres. `placements.ref` uses the same path strings as `projects.refs` — and
misses the same way.

---

## Applying changes

Config is **file-based on purpose** — the save path re-serialises from the object graph and
erases every comment. Edit the file, then touch any `probes/<id>/probe.yml` to trigger the
catalog watcher; do not restart, it drops every session. See the skill for the full sequence
and for the verification that actually proves a change landed.
