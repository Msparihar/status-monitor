"""Tests for the webhook endpoint."""

from tests.conftest import (
    SAMPLE_INCIDENT_PAYLOAD,
    SAMPLE_COMPONENT_PAYLOAD,
    SAMPLE_MAINTENANCE_PAYLOAD,
)

SECRET = "test-secret-123"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_rejects_wrong_secret(client):
    resp = client.post("/webhook/wrong-secret", json=SAMPLE_INCIDENT_PAYLOAD)
    assert resp.status_code == 403


def test_incident_webhook(client):
    resp = client.post(f"/webhook/{SECRET}", json=SAMPLE_INCIDENT_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["incident_id"] == "abc123"


def test_component_webhook(client):
    resp = client.post(f"/webhook/{SECRET}", json=SAMPLE_COMPONENT_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["component_id"] == "comp1"


def test_maintenance_webhook(client):
    resp = client.post(f"/webhook/{SECRET}", json=SAMPLE_MAINTENANCE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["maintenance_id"] == "maint1"


def test_unknown_payload(client):
    resp = client.post(f"/webhook/{SECRET}", json={"foo": "bar"})
    assert resp.status_code == 200
    assert resp.json()["type"] == "unknown"


def test_duplicate_incident_is_deduped(client):
    resp1 = client.post(f"/webhook/{SECRET}", json=SAMPLE_INCIDENT_PAYLOAD)
    assert resp1.json().get("duplicate") is not True

    resp2 = client.post(f"/webhook/{SECRET}", json=SAMPLE_INCIDENT_PAYLOAD)
    assert resp2.json()["duplicate"] is True


def test_duplicate_component_is_deduped(client):
    resp1 = client.post(f"/webhook/{SECRET}", json=SAMPLE_COMPONENT_PAYLOAD)
    assert resp1.json().get("duplicate") is not True

    resp2 = client.post(f"/webhook/{SECRET}", json=SAMPLE_COMPONENT_PAYLOAD)
    assert resp2.json()["duplicate"] is True


def test_email_webhook(client):
    payload = {
        "source": "email",
        "from": "noreply@incident.io",
        "to": "status@manishsingh.tech",
        "subject": "OpenAI API - Degraded Performance",
        "body": "We are investigating elevated error rates on Chat Completions.",
        "received_at": "2026-02-20T16:00:00Z",
    }
    resp = client.post(f"/webhook/{SECRET}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["source"] == "email"
    assert data["subject"] == "OpenAI API - Degraded Performance"


def test_email_webhook_deduped(client):
    payload = {
        "source": "email",
        "from": "noreply@incident.io",
        "to": "status@manishsingh.tech",
        "subject": "OpenAI API - Degraded Performance",
        "body": "Same incident update.",
        "received_at": "2026-02-20T16:00:00Z",
    }
    resp1 = client.post(f"/webhook/{SECRET}", json=payload)
    assert resp1.json().get("duplicate") is not True

    resp2 = client.post(f"/webhook/{SECRET}", json=payload)
    assert resp2.json()["duplicate"] is True
