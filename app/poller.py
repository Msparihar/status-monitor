"""Background poller — safety net for missed webhooks.

Periodically fetches unresolved incidents and component statuses from all
enabled providers via their public Status API (no auth, no rate limits).
Uses the shared dedup cache so events already seen via webhooks are skipped.

Each provider tracks its own backoff state: consecutive failures increase the
wait before the next attempt exponentially (up to a cap), and a single
success resets it to zero.
"""

import asyncio
import time

import httpx

from app.config import POLL_INTERVAL_SECONDS
from app.dedup import event_cache, make_event_key
from app.logger import log_event, logger
from app.providers import StatusPageProvider, get_enabled_providers

# In-memory component state tracker: provider_key -> {component_id: status}
_component_state: dict[str, dict[str, str]] = {}

# Per-provider backoff tracking
_failures: dict[str, int] = {}        # provider_key -> consecutive failure count
_last_attempt: dict[str, float] = {}   # provider_key -> monotonic timestamp of last attempt

_MAX_BACKOFF_MULTIPLIER = 8  # cap: 8 * POLL_INTERVAL_SECONDS


def _next_allowed_at(provider_key: str) -> float:
    """Return the monotonic timestamp at which this provider can be polled again."""
    last = _last_attempt.get(provider_key, 0)
    failures = _failures.get(provider_key, 0)
    if failures == 0:
        return 0  # no delay
    multiplier = min(2 ** (failures - 1), _MAX_BACKOFF_MULTIPLIER)
    return last + POLL_INTERVAL_SECONDS * multiplier


def _record_success(provider_key: str) -> None:
    if _failures.get(provider_key, 0) > 0:
        logger.info(
            f"[poller] {provider_key} recovered after "
            f"{_failures[provider_key]} consecutive failure(s)"
        )
    _failures.pop(provider_key, None)


def _record_failure(provider_key: str) -> None:
    _failures[provider_key] = _failures.get(provider_key, 0) + 1
    backoff_s = POLL_INTERVAL_SECONDS * min(2 ** (_failures[provider_key] - 1), _MAX_BACKOFF_MULTIPLIER)
    logger.warning(
        f"[poller] {provider_key} failure #{_failures[provider_key]} — "
        f"next attempt in ~{backoff_s}s"
    )


async def _poll_incidents(client: httpx.AsyncClient, provider: StatusPageProvider) -> None:
    url = f"{provider.api_url}/incidents/unresolved.json"
    resp = await client.get(url, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    for incident in data.get("incidents", []):
        updates = incident.get("incident_updates", [])
        latest_update_id = updates[0]["id"] if updates else ""
        dedup_key = make_event_key(provider.name, "incident", incident["id"], latest_update_id)

        if event_cache.seen_or_mark(dedup_key):
            continue

        components = incident.get("components", [])
        affected = ", ".join(c["name"] for c in components) or "Unknown"
        latest_body = updates[0].get("body", "") if updates else ""

        log_event(
            source="poller",
            provider=provider.name,
            product=affected,
            event_type="incident",
            status=f"{incident.get('impact', 'unknown')} | {incident['status']} — {incident['name']}",
            detail=latest_body,
        )


async def _poll_components(client: httpx.AsyncClient, provider: StatusPageProvider) -> None:
    url = f"{provider.api_url}/components.json"
    resp = await client.get(url, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    prev = _component_state.get(provider.key, {})
    current: dict[str, str] = {}

    for comp in data.get("components", []):
        comp_id = comp["id"]
        comp_status = comp["status"]
        current[comp_id] = comp_status

        old_status = prev.get(comp_id)
        if old_status is not None and old_status != comp_status:
            dedup_key = make_event_key(
                provider.name, "component_change", comp_id, comp_status
            )
            if event_cache.seen_or_mark(dedup_key):
                continue

            log_event(
                source="poller",
                provider=provider.name,
                product=comp["name"],
                event_type="component",
                status=f"{old_status} → {comp_status}",
            )

    _component_state[provider.key] = current


async def _poll_provider(client: httpx.AsyncClient, provider: StatusPageProvider) -> None:
    """Poll a single provider, respecting its backoff window."""
    now = time.monotonic()
    if now < _next_allowed_at(provider.key):
        return  # still in backoff window, skip this cycle

    _last_attempt[provider.key] = now

    try:
        await _poll_incidents(client, provider)
        await _poll_components(client, provider)
        _record_success(provider.key)
    except httpx.HTTPError:
        _record_failure(provider.key)


async def poll_all_providers() -> None:
    providers = get_enabled_providers()
    if not providers:
        logger.info("[poller] No enabled providers — skipping poll cycle")
        return

    async with httpx.AsyncClient() as client:
        tasks = [_poll_provider(client, p) for p in providers]
        await asyncio.gather(*tasks, return_exceptions=True)


async def poll_loop() -> None:
    logger.info(
        f"[poller] Started — polling {len(get_enabled_providers())} providers "
        f"every {POLL_INTERVAL_SECONDS}s"
    )
    while True:
        try:
            await poll_all_providers()
        except Exception as e:
            logger.error(f"[poller] Unexpected error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
