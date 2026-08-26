# Credentials Store

Central, encrypted credential storage for probe authentication against external services.

## Credential Types

| Type | Fields | Use Case |
|------|--------|----------|
| **Bearer** | token | REST APIs (cloud providers, Grafana, etc.) |
| **Basic** | username, password | Internal services, Jenkins, databases |
| **Header** | headerName, headerValue | APIs using custom auth headers (`X-API-Key`) |
| **OAuth2** | clientId, clientSecret, tokenUrl, scope | Cloud APIs, enterprise SSO services |
| **TLS** | certPem, keyPem, caPem (optional) | Mutual TLS / client certificate auth |
| **SSH** | privateKey, passphrase (optional), username | Remote command execution on 3rd-party hosts |

Each type is a strongly-typed Java record (sealed interface). The compiler enforces exhaustive handling — no generic key-value blobs.

## Encryption

- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key derivation**: PBKDF2WithHmacSHA256, 600,000 iterations
- **Master key**: from environment variable `STATUS_CREDENTIALS_KEY`
- **IV**: random 12-byte per credential
- **AAD**: credential type string bound to ciphertext (tamper detection)
- **Storage**: separate SQLite database (`credentials.db`)

If `STATUS_CREDENTIALS_KEY` is not set, a dev-only fallback key is used with a warning logged.

## Usage in Infrastructure Config

Reference credentials by name in `infrastructure.yml`:

```yaml
projects:
  - name: Platform
    apps:
      - name: Acme Cloud
        services:
          - type: custom
            probes:
              - name: Server Status
                probe: http-endpoint
                target: https://api.acme-cloud.example/v1/servers
                credentials: acme-cloud-prod
```

## Agent Delivery

1. Server includes credential name in probe assignments during heartbeat
2. Agent fetches credential via signed request: `GET /api/agents/{name}/credentials/{credentialName}`
3. Server verifies Ed25519 signature, decrypts, returns full credential
4. Agent caches in memory (5-min TTL), never writes to disk
5. Credential injected as `ctx.params.credentials` in probe sandbox

## Admin API

All endpoints require `infraAdmin` or `admin` role.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/credentials` | List all (metadata only, no secrets) |
| `GET` | `/api/admin/credentials/{id}` | Get one with masked secrets |
| `POST` | `/api/admin/credentials` | Create: `{name, type, data: {...}}` |
| `PUT` | `/api/admin/credentials/{id}` | Update |
| `DELETE` | `/api/admin/credentials/{id}` | Delete |
| `GET` | `/api/admin/credentials/{id}/log` | Access audit log |

Secrets are never returned in full — API responses show masked values (e.g., `eyJh****...****gIs`).

## Audit Log

Every credential access is logged:
- **Who**: admin email or agent name
- **What**: credential name
- **Action**: create, read, update, delete
- **When**: timestamp

Stored in `credential_access_log` table in the same database.

## Admin UI

Settings > Credentials page:
- Create/edit form with dynamic fields per credential type
- Type selector drives the field layout
- Secret fields use password inputs
- PEM/key fields use textareas
- Name is immutable after creation (used as reference key)

## Dev Setup

```bash
# Optional — without this, a dev fallback key is used
export STATUS_CREDENTIALS_KEY="your-secret-key"
```

