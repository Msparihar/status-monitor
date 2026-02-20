"""Send test webhook payloads to the local server.

Usage: uv run python test_webhook.py [webhook-secret]
"""

import httpx
import asyncio
import sys

BASE_URL = "http://localhost:8000"

SAMPLE_INCIDENT = {
    "meta": {
        "unsubscribe": "https://status.openai.com/unsubscribe",
        "documentation": "https://doers.statuspage.io/customer-notifications/webhooks/",
    },
    "page": {
        "id": "01JMDK9XYNY6RXSED6SDWW50WY",
        "status_indicator": "major",
        "status_description": "Partial System Outage",
    },
    "incident": {
        "backfilled": False,
        "created_at": "2025-11-03T14:32:00.000Z",
        "id": "abc123",
        "impact": "major",
        "name": "Degraded performance on Chat Completions API",
        "resolved_at": None,
        "status": "investigating",
        "updated_at": "2025-11-03T14:35:00.000Z",
        "incident_updates": [
            {
                "body": "We are investigating reports of elevated error rates on the Chat Completions API. Some requests may timeout or return 500 errors.",
                "created_at": "2025-11-03T14:35:00.000Z",
                "display_at": "2025-11-03T14:35:00.000Z",
                "id": "upd1",
                "incident_id": "abc123",
                "status": "investigating",
                "updated_at": "2025-11-03T14:35:00.000Z",
            }
        ],
        "components": [
            {
                "created_at": "2024-01-01T00:00:00.000Z",
                "id": "01JMXBRMFE6N2NNT7DG6XZQ6PW",
                "name": "Chat Completions",
                "status": "major_outage",
            }
        ],
    },
}

SAMPLE_COMPONENT = {
    "meta": {
        "unsubscribe": "https://status.openai.com/unsubscribe",
        "documentation": "https://doers.statuspage.io/customer-notifications/webhooks/",
    },
    "page": {
        "id": "01JMDK9XYNY6RXSED6SDWW50WY",
        "status_indicator": "minor",
        "status_description": "Minor Service Outage",
    },
    "component_update": {
        "created_at": "2025-11-03T15:00:00.000Z",
        "new_status": "degraded_performance",
        "old_status": "operational",
        "id": "cupd1",
        "component_id": "01JMXBRMFE6N2NNT7DG6XZQ6PW",
    },
    "component": {
        "created_at": "2024-01-01T00:00:00.000Z",
        "id": "01JMXBRMFE6N2NNT7DG6XZQ6PW",
        "name": "Chat Completions",
        "status": "degraded_performance",
    },
}

SAMPLE_MAINTENANCE = {
    "page": {
        "id": "01JMDK9XYNY6RXSED6SDWW50WY",
        "status_indicator": "none",
        "status_description": "Scheduled Maintenance",
    },
    "scheduled_maintenance": {
        "created_at": "2025-12-01T00:00:00.000Z",
        "id": "maint1",
        "impact": "maintenance",
        "name": "Database migration window",
        "scheduled_for": "2025-12-05T02:00:00.000Z",
        "scheduled_until": "2025-12-05T06:00:00.000Z",
        "status": "scheduled",
        "updated_at": "2025-12-01T00:00:00.000Z",
        "incident_updates": [
            {
                "body": "Scheduled maintenance for database migration.",
                "created_at": "2025-12-01T00:00:00.000Z",
                "id": "mupd1",
                "incident_id": "maint1",
                "status": "scheduled",
            }
        ],
        "components": [
            {
                "created_at": "2024-01-01T00:00:00.000Z",
                "id": "01JMXBRMFE6N2NNT7DG6XZQ6PW",
                "name": "Chat Completions",
                "status": "under_maintenance",
            }
        ],
    },
}


async def main():
    secret = sys.argv[1] if len(sys.argv) > 1 else ""
    if not secret:
        print("Usage: uv run python test_webhook.py <webhook-secret>")
        print("  (Check server startup logs for the webhook secret)")
        sys.exit(1)

    webhook_url = f"{BASE_URL}/webhook/{secret}"

    async with httpx.AsyncClient() as client:
        print("--- Health Check ---")
        r = await client.get(f"{BASE_URL}/health")
        print(f"  {r.status_code}: {r.json()}\n")

        print("--- Wrong secret (should be 403) ---")
        r = await client.post(f"{BASE_URL}/webhook/wrong-secret", json=SAMPLE_INCIDENT)
        print(f"  {r.status_code}: {r.json()}\n")

        print("--- Sending Incident Webhook ---")
        r = await client.post(webhook_url, json=SAMPLE_INCIDENT)
        print(f"  {r.status_code}: {r.json()}\n")

        print("--- Sending Component Webhook ---")
        r = await client.post(webhook_url, json=SAMPLE_COMPONENT)
        print(f"  {r.status_code}: {r.json()}\n")

        print("--- Sending Maintenance Webhook ---")
        r = await client.post(webhook_url, json=SAMPLE_MAINTENANCE)
        print(f"  {r.status_code}: {r.json()}\n")

        print("--- Sending Duplicate Incident (should be deduped) ---")
        r = await client.post(webhook_url, json=SAMPLE_INCIDENT)
        print(f"  {r.status_code}: {r.json()}\n")

        print("Done! Check the server logs for formatted output.")


if __name__ == "__main__":
    asyncio.run(main())
