from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import List

from app.schemas import LogEntry

_ring_buffer: deque[LogEntry] = deque(maxlen=2000)
_lock = threading.Lock()
_subscribers: list[asyncio.Queue[LogEntry]] = []
_loop: asyncio.AbstractEventLoop | None = None


class _RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                + f",{record.msecs:03.0f}",
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
            )
        except Exception:
            return
        with _lock:
            _ring_buffer.append(entry)
        if _loop is not None:
            with _lock:
                subs = list(_subscribers)
            for q in subs:
                _loop.call_soon_threadsafe(q.put_nowait, entry)


def setup_logging() -> None:
    global _loop
    _loop = asyncio.get_event_loop()

    handler = _RingHandler()

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def subscribe() -> asyncio.Queue[LogEntry]:
    q: asyncio.Queue[LogEntry] = asyncio.Queue()
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue[LogEntry]) -> None:
    with _lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


def get_recent(n: int = 200) -> List[LogEntry]:
    with _lock:
        buf = list(_ring_buffer)
    if len(buf) <= n:
        return buf
    return buf[-n:]
