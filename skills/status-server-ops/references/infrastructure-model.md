# Infrastructure Model

## Overview

Status monitors infrastructure through a unified host model. Every piece of
the system connects through hosts.

```
infrastructure.yml
├── hosts[]              ← physical/virtual servers
├── projects[]
│   └── apps[]
│       ├── host: "..."  ← references a host by name
│       └── services[]
│           └── probes[]
└── dependencies[]       ← third-party services
```

## Hosts

A host is a server. Defined in `infrastructure.yml`:

```yaml
hosts:
  - name: app-01.example.com        # unique identifier
    address: app-01.example.com     # network address
    user: root
    labels:
      provider: acme-cloud
      location: Falkenstein, DE
```

The host `name` is the anchor — everything references it.

## Host-Agent

A host-agent is a lightweight Docker sidecar that runs on a host and pushes
live metrics (CPU, memory, disk, containers) via heartbeats.

The agent registers with the server using `HOST_AGENT_NAME`. When this name
matches a host name in `infrastructure.yml`, the agent attaches to that host
automatically:

```
infrastructure.yml:  hosts: [{name: "app-01.example.com"}]
                                      ↕ matched by name
docker-compose.yml:  HOST_AGENT_NAME=app-01.example.com
```

If an agent registers with a name that doesn't match any host, the server
creates a synthetic host node for it (visible but has no app assignments).

### What the agent provides

- **Online/offline status** (heartbeat recency < 90 seconds)
- **CPU**: cores, utilization %, load averages (1m/5m/15m), per-core utilization
- **Memory**: used %, total/used bytes, swap
- **Disk**: all mount points with used %, total/used bytes
- **Uptime**: host uptime in seconds
- **Containers**: Docker container inventory (name, image, state, status)

### Agent security

- Ed25519 keypair generated on first run
- Agent registers with public key, admin approves
- Every heartbeat signed with private key, verified server-side
- Agent only pushes (no inbound ports needed)

## Apps → Hosts

Apps declare which host they run on via the `host` field:

```yaml
projects:
  - name: Trading Suite
    apps:
      - name: Hyperliquid History
        host: plaiiin-02          # ← must match a host name
        services:
          - name: API
            type: custom
            probes:
              - name: Health
                type: HTTP_HEALTH
                url: http://app-02.example.com:9820/health
```

Multiple apps can reference the same host.

## Agent Policies

Two top-level blocks in `infrastructure.yml` define what every agent does by
default and what extra tooling specific agents get.

### Default Probes (`agentProbes`)

System-metric probes that run on every agent:

```yaml
agentProbes:
  enabled: true
  probes:
    - host-metrics
    - system-cpu
    - system-memory
    - system-disk
  params:
    lifx:                        # per-probe params (credentials etc.)
      token: "credential:lifx-token"
```

### Default Commands (`agentCommands`)

One-shot commands every agent exposes in the runtime command menu. Entries
are either plain catalog IDs or **command instances** — operator-defined
presets that wrap a catalog command with a custom name and preset (optionally
frozen) parameters:

```yaml
agentCommands:
  enabled: true
  commands:
    - docker-logs                # plain catalog id
    - tail-file
    - name: Restart Prod Stack   # command instance (preset)
      command: compose-up        # catalog id this instance wraps
      params:
        path: /opt/apps/prod-stack
      frozen: [path]             # params the operator can't override at runtime
```

### Per-Agent Overrides (`agentCommandOverrides`)

Extra commands/instances installed on specific agents on top of the defaults:

```yaml
agentCommandOverrides:
  prod-agent-01:
    - name: Redeploy App
      command: compose-up
      params:
        path: /opt/apps/app-01
      frozen: [path]
  dev-agent:
    - nmap-scan                  # plain id — uses ad-hoc params at runtime
```

**Instance resolution:** frozen preset values always win over user-entered
values at run time. Non-frozen presets are just defaults that the operator
can edit in the command menu. The menu fetches instances from
`/api/admin/agents/{name}/configured-instances` and merges them with the
catalog manifest from `/api/admin/agents/{name}/commands`.

## How it all connects

```
┌─────────────────────────────────────────────────┐
│  infrastructure.yml                             │
│                                                 │
│  host "app-01.example.com"                         │
│    │                                            │
│    ├── apps that reference this host:            │
│    │   └── Status (project: Plaiiin)            │
│    │                                            │
│    └── host-agent (HOST_AGENT_NAME matches):     │
│        ├── online: true                         │
│        ├── cpu: 4 cores, 13% utilization        │
│        ├── memory: 27% used                     │
│        ├── disk: 15% used                       │
│        └── containers: [status, traefik, ...]   │
│                                                 │
│  host "plaiiin-02"                              │
│    │                                            │
│    ├── apps:                                    │
│    │   ├── Hyperliquid History                  │
│    │   ├── Binance History                      │
│    │   ├── RootService                          │
│    │   └── ...                                  │
│    │                                            │
│    └── host-agent: (none yet — deploy with      │
│        HOST_AGENT_NAME=plaiiin-02 to attach)    │
└─────────────────────────────────────────────────┘
```

## API Response

The `/api/status` response includes host nodes with embedded agent data:

```json
{
  "hosts": [
    {
      "name": "app-01.example.com",
      "type": "host",
      "status": "OK",
      "hostAgent": {
        "online": true,
        "lastHeartbeat": "2026-04-04T18:00:00Z",
        "metrics": {
          "cpuCores": 4,
          "cpuUtilization": 13.2,
          "memoryUsedPercent": 26.9,
          "diskUsedPercent": 15.3,
          "uptimeSeconds": 329645
        },
        "containers": [...]
      },
      "children": [
        {"name": "Status", "type": "app", "status": "OK", ...}
      ]
    }
  ]
}
```

No separate `agents[]` array — everything is on the host node.

## Mobile App

The mobile app renders hosts as cards:
- **Without agent**: host name + app status dots
- **With agent**: host name + online indicator + CPU/MEM/DISK gauges + app dots
- **Hosts tab**: expanded view with apps and services listed
- **Overview**: compact card at the bottom

Tap a host on the watch for the full detail view (gauges, load averages,
apps, containers).
