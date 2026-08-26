# Probe vs Command Output Comparison

| | Probe | Command |
|---|---|---|
| **State** | OK / WARNING / ERROR | OK / ERROR (completed/failed) |
| **Stream values** | Yes — per-path metrics every tick (state, number, percent, bytes, log, label) | No |
| **Structured result** | `data` + `schema` JSON | `data` + `schema` JSON (same format) |
| **Result file** | `results/probes/{name}.json` | `results/commands/{id}.json` |
| **DB storage** | ProbeHistoryStore (SQLite per probe) | `agent_commands.result` column |
| **API** | `GET /api/probes/result?probe={name}` | `GET /api/commands/result?command={id}` |
| **Lifecycle** | Recurring (interval) | One-shot (triggered) |
| **Execution** | JS sandbox on agent | Java CommandExecutor on agent |
| **Streaming output** | No | Yes — line-by-line via command-stream |

The `data` + `schema` format is identical between probes and commands — same `CommandResult`-style structure with typed field annotations for UI rendering.

## Command Instances

Commands additionally support **instances** — operator-defined presets that wrap
a catalog command with a custom name and preset parameters. An instance can mark
some params as `frozen`, meaning the operator can't override them at run time
(useful for locking a specific path, container, or script). Instances live in
`infrastructure.yml` under `agentCommands.commands` (defaults) and
`agentCommandOverrides[agentName]` (per-agent extras). See
[infrastructure-model.md](../../docs/infrastructure-model.md#agent-policies).
