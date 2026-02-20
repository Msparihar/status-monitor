"""Tests for the deduplication cache."""

import time
from unittest.mock import patch

from app.dedup import EventCache, make_event_key


def test_mark_and_check():
    cache = EventCache()
    assert not cache.is_seen("key1")
    cache.mark_seen("key1")
    assert cache.is_seen("key1")


def test_seen_or_mark():
    cache = EventCache()
    assert cache.seen_or_mark("key1") is False  # first time → mark it
    assert cache.seen_or_mark("key1") is True   # second time → already seen


def test_ttl_expiry():
    cache = EventCache(default_ttl=1)
    cache.mark_seen("key1")
    assert cache.is_seen("key1")

    # Fast-forward time past TTL
    with patch("app.dedup.time.monotonic", return_value=time.monotonic() + 2):
        assert not cache.is_seen("key1")


def test_size():
    cache = EventCache()
    assert cache.size == 0
    cache.mark_seen("a")
    cache.mark_seen("b")
    assert cache.size == 2


def test_make_event_key():
    key = make_event_key("OpenAI", "incident", "inc123", "upd456")
    assert key == "OpenAI:incident:inc123:upd456"


def test_make_event_key_no_update():
    key = make_event_key("GitHub", "component", "comp1")
    assert key == "GitHub:component:comp1:"
