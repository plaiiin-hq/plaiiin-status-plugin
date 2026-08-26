# Icon System

Status uses distinct icons for different entity types across web, iOS, and watchOS.

## Entity Icons

| Entity        | Web (Lucide)      | iOS/watchOS (SF Symbols) | Color               |
|---------------|-------------------|--------------------------|----------------------|
| App / Service | `Server`          | `server.rack`            | State color          |
| Agent         | `Cpu`             | `cpu`                    | State color          |
| Host          | `Server`          | `server.rack`            | State color          |
| Probe (leaf)  | `StatusDot` (8px) | `Circle` (4-6px)         | State color          |

## State Colors

| State   | Web CSS variable              | iOS/watchOS    |
|---------|-------------------------------|----------------|
| OK      | `--status-green` (`#B9D26E`)  | `.green`       |
| Warning | `--status-amber` (`#d97706`)  | `.orange`      |
| Error   | `--status-red` (`#dc2626`)    | `.red`         |
| Unknown | `--bs-secondary-color`        | `.gray`        |

## Web Components

- `ServerIcon.vue` — wraps Lucide `Server`, accepts `state` prop
- `AgentIcon.vue` — wraps Lucide `Cpu`, accepts `state` prop
- `StatusDot.vue` — 8px colored circle for probes/leaf nodes
- `StatusBadge.vue` — labeled badge (`OK`, `ERROR`, etc.)

Library: [lucide-vue-next](https://lucide.dev) (tree-shakeable, only imports used icons).

## iOS Components

No wrapper components — SF Symbols used inline:

```swift
// App or host
Image(systemName: "server.rack")
    .foregroundStyle(status.color)

// Agent
Image(systemName: "cpu")
    .foregroundStyle(agent.isOnline ? .green : .red)

// Probe leaf
Circle()
    .fill(probe.state.color)
    .frame(width: 6, height: 6)
```

`ProbeState.swift` provides `.color` and `.icon` properties for state-dependent styling.

## Where Icons Appear

**Web:**
- Dashboard: project summary row, app card headers
- Systems page: agent cards, host cards

**iOS:**
- Dashboard: app summary indicators, host card headers, expanded app rows
- Systems page: agent section (cpu), external hosts section (server.rack)
- Admin > Agents: agent list rows

**watchOS:**
- Systems tab: host rows, app indicators
- Overview: hosts section
