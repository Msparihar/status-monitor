import os
import pytest
from fastapi.testclient import TestClient

# Set a predictable webhook secret for tests.
os.environ["WEBHOOK_SECRET"] = "test-secret-123"
os.environ["OPENAI_API_KEY"] = ""
os.environ["POLL_INTERVAL_SECONDS"] = "999999"

from app.main import app  # noqa: E402
from app.dedup import event_cache  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clear_dedup_cache():
    """Reset the dedup cache between tests."""
    event_cache._store.clear()
    yield
    event_cache._store.clear()


SAMPLE_INCIDENT_PAYLOAD = {
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
                "body": "We are investigating elevated error rates.",
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
                "id": "comp1",
                "name": "Chat Completions",
                "status": "major_outage",
            }
        ],
    },
}

SAMPLE_COMPONENT_PAYLOAD = {
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
        "component_id": "comp1",
    },
    "component": {
        "created_at": "2024-01-01T00:00:00.000Z",
        "id": "comp1",
        "name": "Chat Completions",
        "status": "degraded_performance",
    },
}

SAMPLE_MAINTENANCE_PAYLOAD = {
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
                "id": "comp1",
                "name": "Chat Completions",
                "status": "under_maintenance",
            }
        ],
    },
}
