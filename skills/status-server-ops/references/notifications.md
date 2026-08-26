# Notification Channels

Status supports multiple notification channels for alerts, recoveries, and daily digests. Channels are split into two categories:

- **Personal channels** — per-user (Telegram, SMS). Admin provides credentials, users link their own accounts on the Account page.
- **Server-wide channels** — shared (Slack, MS Teams, Discord, Webhook). Admin provides webhook URLs, all alerts go there automatically.

## Configuration

All channel config lives in `notifications.yml`, mounted into the container at `/status/config/notifications.yml` (same volume as `infrastructure.yml`). The admin UI at `/admin/notifications` can edit this file if the container has write permissions.

Example:

```yaml
telegram:
  bot-token: "${STATUS_TELEGRAM_BOT_TOKEN}"
  bot-username: "plaiiin_status_bot"

slack:
  webhook-url: "https://hooks.slack.com/services/T.../B.../xxx"
```

## Telegram Setup

### 1. Create a bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a display name (e.g. "Plaiiin Status")
4. Choose a username ending in `bot` (e.g. `plaiiin_status_bot`)
5. BotFather replies with a **bot token** — save it

### 2. Configure Status

Add to `notifications.yml`:

```yaml
telegram:
  bot-token: "YOUR_BOT_TOKEN"
  bot-username: "your_bot_username"
```

Or set the token as an environment variable and reference it:

```yaml
telegram:
  bot-token: "${STATUS_TELEGRAM_BOT_TOKEN}"
  bot-username: "plaiiin_status_bot"
```

### 3. Register the webhook

The bot needs a webhook so Telegram can forward messages (like `/start`) to Status.

**Via admin UI:**
Go to `/admin/notifications` > Telegram > enter your server's base URL (e.g. `https://status.example.com`) > click "Register Webhook".

**Via curl:**
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://status.example.com/api/telegram/webhook"
```

The endpoint `/api/telegram/webhook` is public (no auth required) — it only accepts Telegram bot update payloads.

### 4. Users link their accounts

1. User goes to Account page > Notifications > Telegram > "Link Telegram"
2. A link appears: `https://t.me/plaiiin_status_bot?start=<token>`
3. User opens the link in Telegram, which sends `/start <token>` to the bot
4. The webhook validates the token and stores the user's `chat_id` in Keycloak
5. Done — user now receives personal alerts via Telegram

Users can configure which notification types they receive (alerts, recoveries, digests) via checkboxes on the Account page.

## SMS (Twilio) Setup

### 1. Get Twilio credentials

Sign up at [twilio.com](https://www.twilio.com), get:
- Account SID
- Auth Token
- A phone number (the "From" number)

### 2. Configure Status

```yaml
sms:
  twilio-account-sid: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  twilio-auth-token: "your-auth-token"
  twilio-from-number: "+15551234567"
```

### 3. Users add their phone numbers

Account page > Notifications > SMS > enter phone number in E.164 format (e.g. `+491234567890`) > Save.

## Slack Setup

1. Create an [Incoming Webhook](https://api.slack.com/messaging/webhooks) in your Slack workspace
2. Choose the channel (e.g. `#alerts`)
3. Copy the webhook URL
4. Add to `notifications.yml`:

```yaml
slack:
  webhook-url: "https://hooks.slack.com/services/T.../B.../xxx"
```

All alerts, recoveries, and digests are posted to this channel automatically.

## Discord Setup

1. In your Discord server, go to Channel Settings > Integrations > Webhooks
2. Create a new webhook, copy the URL
3. Add to `notifications.yml`:

```yaml
discord:
  webhook-url: "https://discord.com/api/webhooks/..."
```

## Microsoft Teams Setup

1. In your Teams channel, add an Incoming Webhook connector
2. Copy the webhook URL
3. Add to `notifications.yml`:

```yaml
msteams:
  webhook-url: "https://outlook.office.com/webhook/..."
```

## Generic Webhook

For custom integrations. Status POSTs a JSON payload to your endpoint.

```yaml
webhook:
  url: "https://your-endpoint.com/status-alerts"
  secret: "optional-hmac-secret"
```

### Payload format

**Alert:**
```json
{
  "event": "alert",
  "probe": {"name": "Infra / API / Health", "project": "Infra", "state": "ERROR", "type": "HTTP_HEALTH"},
  "message": "Connection refused",
  "timestamp": "2026-04-04T12:00:00Z",
  "duration": "5m 30s",
  "consecutiveFailures": 3
}
```

**Recovery:**
```json
{
  "event": "recovery",
  "probe": {"name": "Infra / API / Health", "project": "Infra", "state": "OK", "previousState": "ERROR"},
  "timestamp": "2026-04-04T12:05:00Z",
  "duration": "5m 30s"
}
```

**Digest:**
```json
{
  "event": "digest",
  "timestamp": "2026-04-04T07:00:00Z",
  "summary": {"ok": 12, "warning": 1, "error": 0, "total": 13}
}
```

### HMAC verification

If `secret` is set, every request includes an `X-Status-Signature` header:

```
X-Status-Signature: sha256=<hex-encoded HMAC-SHA256 of request body>
```

## User Preferences

Each user can toggle per-channel delivery on the Account page:
- **Alerts** — probe failure notifications
- **Recoveries** — probe recovery notifications
- **Digests** — daily status summaries

Preferences are stored as a Keycloak user attribute (`notification_preferences`). Default is all enabled.

## Architecture

```
notifications.yml (mounted config file)
  ├── telegram.bot-token        → TelegramSender reads token
  ├── sms.twilio-*              → SmsSender reads credentials
  ├── slack.webhook-url         → SlackSender posts here
  ├── msteams.webhook-url       → MSTeamsSender posts here
  ├── discord.webhook-url       → DiscordSender posts here
  └── webhook.url + secret      → WebhookSender posts here

Keycloak user attributes
  ├── telegram_chat_id          → linked via bot /start flow
  ├── phone_number              → entered on Account page
  └── notification_preferences  → JSON toggles per channel

AlertManager
  ├── EmailSender               (existing)
  ├── PushRelaySender           (existing)
  └── NotificationDispatcher
        ├── Server-wide: Slack, Discord, Teams, Webhook
        └── Personal: Telegram, SMS (per-user via Keycloak)
```
