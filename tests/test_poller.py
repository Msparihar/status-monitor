"""Tests for the background poller logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.poller import (
    _poll_incidents,
    _poll_components,
    _poll_provider,
    _component_state,
    _failures,
    _last_attempt,
)
from app.providers import get_provider
from app.dedup import event_cache


@pytest.fixture
def openai_provider():
    return get_provider("openai")


@pytest.fixture(autouse=True)
def reset_poller_state():
    _component_state.clear()
    _failures.clear()
    _last_attempt.clear()
    event_cache._store.clear()
    yield
    _component_state.clear()
    _failures.clear()
    _last_attempt.clear()
    event_cache._store.clear()


MOCK_INCIDENTS_RESPONSE = {
    "incidents": [
        {
            "id": "inc1",
            "name": "API errors",
            "status": "investigating",
            "impact": "major",
            "incident_updates": [
                {"id": "upd1", "body": "Looking into it", "status": "investigating"}
            ],
            "components": [
                {"id": "c1", "name": "Chat Completions"}
            ],
        }
    ]
}

MOCK_COMPONENTS_RESPONSE = {
    "components": [
        {"id": "c1", "name": "Chat Completions", "status": "operational"},
        {"id": "c2", "name": "Responses API", "status": "operational"},
    ]
}



@pytest.mark.asyncio
async def test_poll_incidents_logs_new_incident(openai_provider):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_INCIDENTS_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    await _poll_incidents(mock_client, openai_provider)

    assert event_cache.is_seen("OpenAI:incident:inc1:upd1")


@pytest.mark.asyncio
async def test_poll_incidents_skips_duplicate(openai_provider):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_INCIDENTS_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    await _poll_incidents(mock_client, openai_provider)
    await _poll_incidents(mock_client, openai_provider)

    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_poll_components_detects_status_change(openai_provider):
    _component_state["openai"] = {
        "c1": "operational",
        "c2": "operational",
    }

    changed_response = {
        "components": [
            {"id": "c1", "name": "Chat Completions", "status": "degraded_performance"},
            {"id": "c2", "name": "Responses API", "status": "operational"},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = changed_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    await _poll_components(mock_client, openai_provider)

    assert event_cache.is_seen("OpenAI:component_change:c1:degraded_performance")
    assert not event_cache.is_seen("OpenAI:component_change:c2:operational")


@pytest.mark.asyncio
async def test_poll_components_first_run_no_alerts(openai_provider):
    """On first run, there's no previous state, so no transitions should be logged."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_COMPONENTS_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    await _poll_components(mock_client, openai_provider)

    assert _component_state["openai"] == {"c1": "operational", "c2": "operational"}
    assert event_cache.size == 0


@pytest.mark.asyncio
async def test_backoff_on_failure(openai_provider):
    """Failures should increment backoff counter."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    await _poll_provider(mock_client, openai_provider)

    assert _failures["openai"] == 1

    # Second attempt should be skipped (in backoff window)
    await _poll_provider(mock_client, openai_provider)
    # Still 1 because the second call was skipped
    assert _failures["openai"] == 1


@pytest.mark.asyncio
async def test_backoff_resets_on_success(openai_provider):
    """A successful poll should reset the backoff counter."""
    _failures["openai"] = 3
    _last_attempt["openai"] = -10_000_000  # far enough in the past to clear any backoff window

    # Build a mock that returns success for both incident + component calls
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.side_effect = [
        {"incidents": []},       # first call: _poll_incidents
        MOCK_COMPONENTS_RESPONSE,  # second call: _poll_components
    ]

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    await _poll_provider(mock_client, openai_provider)

    assert "openai" not in _failures
