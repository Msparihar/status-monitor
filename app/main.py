import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import WEBHOOK_SECRET
from app.dedup import event_cache, make_event_key
from app.logger import log_event, logger, enrich_with_ai
from app.models import IncidentWebhook, ComponentWebhook, MaintenanceWebhook
from app.poller import poll_loop
from app.providers import get_provider_by_page_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Webhook secret: {WEBHOOK_SECRET}")
    logger.info(f"Webhook path:   /webhook/{WEBHOOK_SECRET}")
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Status Page Monitor", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "cache_size": event_cache.size}


@app.post("/webhook/{secret}")
async def handle_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        logger.warning(f"Rejected webhook with invalid secret")
        return JSONResponse(status_code=403, content={"error": "forbidden"})

    payload = await request.json()

    if "incident" in payload:
        return await _handle_incident(payload)
    elif "component_update" in payload:
        return await _handle_component(payload)
    elif "scheduled_maintenance" in payload:
        return await _handle_maintenance(payload)

    logger.warning(f"Unknown webhook payload keys: {list(payload.keys())}")
    return {"received": True, "type": "unknown"}


async def _handle_incident(payload: dict):
    try:
        data = IncidentWebhook(**payload)
    except Exception as e:
        logger.error(f"Incident parse error: {e}")
        return {"error": "parse_failed"}

    incident = data.incident
    provider = get_provider_by_page_id(data.page.id)
    provider_name = provider.name if provider else "Unknown"

    # Dedup: key on incident id + latest update id
    latest_update_id = incident.incident_updates[0].id if incident.incident_updates else ""
    dedup_key = make_event_key(provider_name, "incident", incident.id, latest_update_id)
    if event_cache.seen_or_mark(dedup_key):
        logger.debug(f"Skipping duplicate incident {incident.id}")
        return {"received": True, "duplicate": True}

    affected = ", ".join(c.name for c in incident.components) or "Unknown"
    latest_update = incident.incident_updates[0].body if incident.incident_updates else "No details"

    log_event(
        source="webhook",
        provider=provider_name,
        product=affected,
        event_type="incident",
        status=f"{incident.impact or 'unknown'} | {incident.status} — {incident.name}",
        detail=latest_update or "",
    )

    update_bodies = [u.body for u in incident.incident_updates if u.body]
    summary = await enrich_with_ai(incident.name, incident.status, update_bodies)
    if summary:
        logger.info(f"  [AI Summary] {summary}")

    return {"received": True, "incident_id": incident.id}


async def _handle_component(payload: dict):
    try:
        data = ComponentWebhook(**payload)
    except Exception as e:
        logger.error(f"Component parse error: {e}")
        return {"error": "parse_failed"}

    provider = get_provider_by_page_id(data.page.id)
    provider_name = provider.name if provider else "Unknown"

    dedup_key = make_event_key(
        provider_name, "component", data.component.id, data.component_update.id
    )
    if event_cache.seen_or_mark(dedup_key):
        return {"received": True, "duplicate": True}

    log_event(
        source="webhook",
        provider=provider_name,
        product=data.component.name,
        event_type="component",
        status=f"{data.component_update.old_status} → {data.component_update.new_status}",
    )

    return {"received": True, "component_id": data.component.id}


async def _handle_maintenance(payload: dict):
    try:
        data = MaintenanceWebhook(**payload)
    except Exception as e:
        logger.error(f"Maintenance parse error: {e}")
        return {"error": "parse_failed"}

    maint = data.scheduled_maintenance
    provider = get_provider_by_page_id(data.page.id)
    provider_name = provider.name if provider else "Unknown"

    latest_update_id = maint.incident_updates[0].id if maint.incident_updates else ""
    dedup_key = make_event_key(provider_name, "maintenance", maint.id, latest_update_id)
    if event_cache.seen_or_mark(dedup_key):
        return {"received": True, "duplicate": True}

    affected = ", ".join(c.name for c in maint.components) or "Unknown"
    schedule = ""
    if maint.scheduled_for:
        schedule = f" (scheduled {maint.scheduled_for} → {maint.scheduled_until or '?'})"

    log_event(
        source="webhook",
        provider=provider_name,
        product=affected,
        event_type="scheduled_maintenance",
        status=f"{maint.status} — {maint.name}{schedule}",
    )

    return {"received": True, "maintenance_id": maint.id}
