"""TTL-based in-memory event deduplication cache.

Prevents the same incident/component update from being logged twice when
both the webhook and the background poller detect it.
"""

import time


class EventCache:
    def __init__(self, default_ttl: int = 600):
        self._store: dict[str, float] = {}  # key -> expiry timestamp
        self._default_ttl = default_ttl

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, exp in self._store.items() if exp <= now]
        for k in expired:
            del self._store[k]

    def is_seen(self, key: str) -> bool:
        self._cleanup()
        return key in self._store

    def mark_seen(self, key: str, ttl: int | None = None) -> None:
        self._store[key] = time.monotonic() + (ttl or self._default_ttl)

    def seen_or_mark(self, key: str, ttl: int | None = None) -> bool:
        """Return True if already seen, otherwise mark and return False."""
        if self.is_seen(key):
            return True
        self.mark_seen(key, ttl)
        return False

    @property
    def size(self) -> int:
        self._cleanup()
        return len(self._store)


def make_event_key(
    provider: str, event_type: str, event_id: str, update_id: str = ""
) -> str:
    return f"{provider}:{event_type}:{event_id}:{update_id}"


# Singleton shared across webhook handler and poller.
event_cache = EventCache()
