"""Structured logging and optional AI enrichment."""

import json
import logging
import sys
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.config import LOG_FORMAT, OPENAI_API_KEY

# ---------------------------------------------------------------------------
# AI client (optional)
# ---------------------------------------------------------------------------
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;31m",  # bold red
    "RESET": "\033[0m",
}


class _PrettyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        color = _COLORS.get(record.levelname, "")
        reset = _COLORS["RESET"]
        return f"{color}[{ts}] [{record.levelname}]{reset} {record.getMessage()}"


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry.update(record.extra_data)
        return json.dumps(entry)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("status_monitor")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _PrettyFormatter() if LOG_FORMAT == "pretty" else _JSONFormatter()
    )
    logger.addHandler(handler)
    return logger


logger = setup_logging()

# ---------------------------------------------------------------------------
# Structured event logging
# ---------------------------------------------------------------------------

def log_event(
    source: str,
    product: str,
    status: str,
    detail: str = "",
    provider: str = "",
    event_type: str = "",
) -> None:
    parts = [
        f"\n{'='*60}",
        f"  Source   : {source}",
    ]
    if provider:
        parts.append(f"  Provider : {provider}")
    parts.append(f"  Product  : {product}")
    if event_type:
        parts.append(f"  Event    : {event_type}")
    parts.append(f"  Status   : {status}")
    if detail:
        parts.append(f"  Detail   : {detail}")
    parts.append(f"{'='*60}")
    logger.info("\n".join(parts))


# ---------------------------------------------------------------------------
# AI enrichment (optional — gracefully degrades if no API key)
# ---------------------------------------------------------------------------

async def enrich_with_ai(
    incident_name: str, status: str, updates: list[str]
) -> str | None:
    if not ai_client:
        return None

    updates_text = "\n".join(f"- {u}" for u in updates[:5])
    prompt = (
        f"Summarize this service incident in 1-2 sentences for an engineering team.\n\n"
        f"Incident: {incident_name}\n"
        f"Status: {status}\n"
        f"Updates:\n{updates_text}"
    )

    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"AI enrichment failed: {e}")
        return None
