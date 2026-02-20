"""Subscribe/unsubscribe to Statuspage webhook notifications and check status."""

import asyncio
import sys

import httpx

from app.config import WEBHOOK_BASE_URL, WEBHOOK_SECRET
from app.providers import get_provider, get_enabled_providers

_STATUS_COLORS = {
    "operational": "\033[32m",            # green
    "degraded_performance": "\033[33m",   # yellow
    "partial_outage": "\033[31m",         # red
    "major_outage": "\033[1;31m",         # bold red
    "under_maintenance": "\033[36m",      # cyan
}
_RESET = "\033[0m"


async def subscribe(page_key: str, email: str = "monitor@status-monitor.local"):
    provider = get_provider(page_key)
    if not provider:
        keys = [p.key for p in get_enabled_providers()]
        print(f"Unknown page: {page_key}. Available: {keys}")
        return None

    endpoint = f"{WEBHOOK_BASE_URL}/webhook/{WEBHOOK_SECRET}"
    url = f"{provider.api_url}/subscribers.json"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={"subscriber": {"endpoint": endpoint, "email": email}},
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"Subscribed to {provider.name} status page")
        print(f"  Subscriber ID: {data.get('id', 'unknown')}")
        print(f"  Webhook endpoint: {endpoint}")
        return data
    else:
        print(f"Failed to subscribe to {provider.name}: {resp.status_code}")
        print(f"  Response: {resp.text}")
        return None


async def unsubscribe(page_key: str, subscriber_id: str):
    provider = get_provider(page_key)
    if not provider:
        print(f"Unknown page: {page_key}")
        return

    url = f"{provider.api_url}/subscribers/{subscriber_id}.json"
    async with httpx.AsyncClient() as client:
        resp = await client.delete(url)

    if resp.status_code in (200, 204):
        print(f"Unsubscribed {subscriber_id} from {provider.name}")
    else:
        print(f"Failed to unsubscribe: {resp.status_code} — {resp.text}")


async def list_subscriptions():
    providers = get_enabled_providers()
    print(f"\nConfigured status pages ({len(providers)} enabled):")
    for p in providers:
        print(f"  [{p.key}] {p.name} — {p.base_url}")
    print(f"\nWebhook endpoint: {WEBHOOK_BASE_URL}/webhook/{WEBHOOK_SECRET}\n")


async def check_status():
    """Fetch current status from all enabled providers."""
    providers = get_enabled_providers()
    print(f"\n{'='*60}")
    print(f"  Status check — {len(providers)} providers")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=15) as client:
        for provider in providers:
            url = f"{provider.api_url}/summary.json"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                print(f"  [{provider.key}] {provider.name}: ERROR — {e}\n")
                continue

            page_status = data.get("page", {}).get("status", {})
            indicator = page_status.get("indicator", "unknown")
            description = page_status.get("description", "Unknown")
            print(f"  [{provider.key}] {provider.name}: {description}")

            components = data.get("components", [])
            non_operational = [
                c for c in components if c.get("status") != "operational"
            ]
            if non_operational:
                for c in non_operational:
                    color = _STATUS_COLORS.get(c["status"], "")
                    print(f"    {color}⚠ {c['name']}: {c['status']}{_RESET}")
            print()

    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  uv run -m app.subscriber subscribe <page_key> [email]")
        print("  uv run -m app.subscriber unsubscribe <page_key> <subscriber_id>")
        print("  uv run -m app.subscriber list")
        print("  uv run -m app.subscriber status")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "subscribe":
        page_key = sys.argv[2] if len(sys.argv) > 2 else "openai"
        email = sys.argv[3] if len(sys.argv) > 3 else "monitor@status-monitor.local"
        asyncio.run(subscribe(page_key, email))
    elif cmd == "unsubscribe":
        page_key = sys.argv[2]
        sub_id = sys.argv[3]
        asyncio.run(unsubscribe(page_key, sub_id))
    elif cmd == "list":
        asyncio.run(list_subscriptions())
    elif cmd == "status":
        asyncio.run(check_status())
    else:
        print(f"Unknown command: {cmd}")
