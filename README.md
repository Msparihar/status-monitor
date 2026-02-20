# Status Page Monitor

Event-driven monitoring system that tracks service outages and degradations across multiple providers using Atlassian Statuspage webhooks.

## Architecture

```
                         ┌──────────────────────┐
  Statuspage providers   │   Status Page Monitor │
  (OpenAI, GitHub, ...)  │                       │
          │              │  ┌─────────────────┐  │
          │  webhook     │  │  FastAPI server  │  │
          ├─────────────►│  │  /webhook/{secret}│ │
          │  (real-time) │  └────────┬────────┘  │
          │              │           │            │
          │              │     ┌─────▼─────┐     │
          │              │     │ Dedup Cache│     │
          │              │     └─────┬─────┘     │
          │              │           │            │
          │              │  ┌────────▼────────┐  │
          │  poll API    │  │ Structured Log  │  │
          ├──────────────│  │ (pretty / JSON) │  │
             (fallback)  │  └─────────────────┘  │
          ▲              │                       │
          │              │  ┌─────────────────┐  │
          └──────────────│──│ Background Poller│  │
            every 90s    │  │ (with backoff)  │  │
                         │  └─────────────────┘  │
                         └──────────────────────┘
```

**Three-channel design:** Webhooks deliver events in real-time for providers that support them. For providers like OpenAI (incident.io) that don't offer webhook subscriptions, a **Cloudflare Email Worker** converts status page email notifications into webhook POSTs. A background poller checks all providers every 90 seconds as a safety net for missed deliveries. All three channels share a TTL-based dedup cache, so events are never logged twice.

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd status-monitor
uv sync

# Configure
cp .env.example .env
# Edit .env — set WEBHOOK_BASE_URL to your public URL

# Run
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On startup, the server logs the webhook secret and path:

```
[INFO] Webhook secret: a1b2c3d4-...
[INFO] Webhook path:   /webhook/a1b2c3d4-...
[INFO] [poller] Started — polling 10 providers every 90s
```

## Webhook Registration

Register your webhook URL with a provider (one-time operation):

```bash
uv run -m app.subscriber subscribe openai your@email.com
```

Statuspage stores the subscription on their side. Your server receives POST requests at `/webhook/{secret}` whenever an incident or component change occurs.

## CLI Commands

```bash
# Subscribe to a provider's webhooks
uv run -m app.subscriber subscribe <provider_key> [email]

# Unsubscribe
uv run -m app.subscriber unsubscribe <provider_key> <subscriber_id>

# List all configured providers
uv run -m app.subscriber list

# Check live status of all providers right now
uv run -m app.subscriber status
```

## Supported Providers

| Key         | Provider   | Status Page                      |
|-------------|------------|----------------------------------|
| `openai`    | OpenAI     | status.openai.com                |
| `github`    | GitHub     | www.githubstatus.com             |
| `cloudflare`| Cloudflare | www.cloudflarestatus.com         |
| `atlassian` | Atlassian  | status.atlassian.com             |
| `datadog`   | Datadog    | status.datadoghq.com             |
| `twilio`    | Twilio     | status.twilio.com                |
| `vercel`    | Vercel     | www.vercel-status.com            |
| `linear`    | Linear     | linearstatus.com                 |
| `hashicorp` | HashiCorp  | status.hashicorp.com             |
| `notion`    | Notion     | www.notion-status.com            |

Adding a new provider is one entry in `app/providers.py` — just the key, name, base URL, and Statuspage page ID.

## Event Types

- **Incidents** — New outages, degradations, and their status updates
- **Component changes** — Individual service status transitions (e.g., operational -> degraded)
- **Scheduled maintenance** — Upcoming maintenance windows and progress updates

## Sample Output

```
============================================================
  Source   : webhook
  Provider : OpenAI
  Product  : Chat Completions
  Event    : incident
  Status   : major | investigating — Degraded performance on Chat Completions API
  Detail   : We are investigating elevated error rates.
============================================================
```

## Configuration

| Variable               | Default         | Description                                   |
|------------------------|-----------------|-----------------------------------------------|
| `WEBHOOK_SECRET`       | (auto-generated)| Secret token in webhook URL path for security  |
| `WEBHOOK_BASE_URL`     | `http://localhost:8000` | Public URL where this server is reachable |
| `POLL_INTERVAL_SECONDS`| `90`            | Background poller interval                     |
| `LOG_FORMAT`           | `pretty`        | `pretty` for colorized console, `json` for structured |
| `OPENAI_API_KEY`       | (empty)         | Optional — enables AI-powered incident summaries |

## Docker

```bash
docker compose up
```

Health check runs against `/health` every 30 seconds.

## Tests

```bash
uv sync --group dev
uv run pytest tests/ -v
```

22 tests covering webhook handling (including email events), deduplication, poller logic, and exponential backoff.

## Email-to-Webhook Pipeline

For providers that don't support webhook subscriptions (e.g., OpenAI uses incident.io which only offers email/RSS), a Cloudflare Email Worker bridges the gap:

```
Status page incident
  -> Email sent to status@yourdomain.com
  -> Cloudflare Email Routing receives it
  -> Email Worker parses subject + body
  -> Worker POSTs structured JSON to /webhook/{secret}
  -> FastAPI server logs and enriches the event
```

Setup:
1. Enable Cloudflare Email Routing on your domain
2. Deploy the worker: `cd email-worker && bun install && bunx wrangler deploy`
3. Create a routing rule: `status@yourdomain.com` -> `status-email-worker`
4. Subscribe to status pages with `status@yourdomain.com`

The worker code lives in `email-worker/`.

## Design Decisions

- **Webhook-first, poller as fallback** — The assignment requires event-driven (not polling). Webhooks satisfy this. The poller exists purely as a safety net since Statuspage doesn't guarantee webhook delivery.
- **URL-path secret** — Statuspage webhooks don't support HMAC signatures. A secret token in the URL path prevents unauthorized payloads.
- **In-memory dedup** — No database needed. TTL-based cache (10 min default) prevents duplicates across both channels. Acceptable for a stateless monitor.
- **Exponential backoff** — Per-provider backoff with cap at 8x the poll interval. A single provider being unreachable doesn't affect others.
- **AI enrichment is optional** — If `OPENAI_API_KEY` is not set, the feature is silently disabled. No hard dependency on external AI services.

## Project Structure

```
app/
  main.py        — FastAPI app, webhook handlers, lifespan
  providers.py   — Provider registry (10 Statuspage instances)
  poller.py      — Background poller with per-provider backoff
  dedup.py       — TTL-based event deduplication cache
  logger.py      — Structured logging + optional AI enrichment
  models.py      — Pydantic models for webhook payloads
  config.py      — Environment configuration
  subscriber.py  — CLI for webhook management and status checks
email-worker/
  src/index.ts   — Cloudflare Email Worker (email -> webhook bridge)
  wrangler.toml  — Worker deployment config
tests/
  test_webhook.py — Endpoint tests (auth, parsing, dedup)
  test_dedup.py   — Cache TTL and key generation tests
  test_poller.py  — Poller logic, backoff, and component tracking tests
```
