import os
import uuid

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Webhook secret — used as URL path token for security.
# Auto-generates a random UUID if not explicitly set.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "") or str(uuid.uuid4())

WEBHOOK_BASE_URL = os.getenv(
    "WEBHOOK_BASE_URL", "http://localhost:8000"
)

# Polling interval for the background fallback poller (seconds).
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "90"))

# Logging format: "pretty" for colorized console, "json" for structured JSON.
LOG_FORMAT = os.getenv("LOG_FORMAT", "pretty")
