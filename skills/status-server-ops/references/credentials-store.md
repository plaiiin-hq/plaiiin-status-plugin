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

⚠️ **A credential is referenced as a param VALUE, never as a `credentials:` field.** There is
no `credentials:` key on a probe — the config model has no such field, and because a save
re-serialises from the object graph, one you write is accepted and then **silently stripped**.
The probe then runs with no token and reports a 401, which reads as a broken credential rather
than a dropped field.

The real form is `"credential:<name>"` as the value of a param the probe declares:

```yaml
projects:
  - name: Platform
    apps:
      - name: Acme Cloud
        services:
          - name: API
            type: custom
            probes:
              - name: Server Status
                probe: http-endpoint
                agent: app-01.example.com
                params:
                  token: "credential:acme-cloud-prod"
```

The same works on a host-level probe, and in `agentProbes.params` keyed by probe id:

```yaml
agentProbes:
  params:
    lifx:
      token: "credential:lifx-token"
```

`params` on an inline probe needs a server build from **2026-08-27 or later**. Before that the
only writer was `agentProbes.params`, which applies a probe to EVERY approved agent — so on an
older build a probe that needs a secret and belongs to one host has nowhere to live.

### 🔑 What the probe actually receives: the RAW secret, as a string

`resolveCredentialRef` substitutes the secret itself into the param — **not** a wrapper object.
A `check.js` that reads `ctx.params.token.token` gets `undefined` and sends no header.

| Type | What lands in the param |
|---|---|
| `bearer` | the token string |
| `basic` | `"username:password"` |
| `header` | the header VALUE (the name is yours to supply) |
| `oauth2` | the client secret |
| `tls` | the cert PEM |
| `ssh` | the private key |

```js
var token = ctx.params.token          // already the raw string
if (token) headers['Authorization'] = 'Bearer ' + token
```

Accept both shapes if the probe is also driven from the IDE test runner, which passes a
credential inline as an object:

```js
var c = ctx.params.token
var token = typeof c === 'string' ? c : (c && c.token)
```

**The audit log will NOT show an agent read.** The server resolves the reference inline while
building the assignment, so a working credential shows only its `create` entry. An empty log is
not evidence the credential failed — check the probe's message instead.

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

