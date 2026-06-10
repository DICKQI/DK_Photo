from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from datetime import datetime, timezone

from app.schemas import LogEntry


RING_BUFFER_SIZE = 2000
SUBSCRIBER_QUEUE_SIZE = 1000


class LogBroker:
    def __init__(self) -> None:
        self._ring_buffer: deque[LogEntry] = deque(maxlen=RING_BUFFER_SIZE)
        self._lock = threading.Lock()
        self._subscribers: list[asyncio.Queue[LogEntry]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_id = 1

    def set_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        with self._lock:
            self._loop = loop

    def publish(self, record: logging.LogRecord) -> None:
        try:
            timestamp = (
                datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                + f",{record.msecs:03.0f}"
            )
            message = record.getMessage()
        except Exception:
            return

        with self._lock:
            entry = LogEntry(
                id=self._next_id,
                timestamp=timestamp,
                level=record.levelname,
                logger=record.name,
                message=message,
            )
            self._next_id += 1
            self._ring_buffer.append(entry)
            subscribers = list(self._subscribers)
            loop = self._loop

        if not loop or loop.is_closed():
            return
        for queue in subscribers:
            loop.call_soon_threadsafe(self._offer_to_subscriber, queue, entry)

    def subscribe(self) -> asyncio.Queue[LogEntry]:
        queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        with self._lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LogEntry]) -> None:
        with self._lock:
            try:
                self._subscribers.remove(queue)
            except ValueError:
                pass

    def get_recent(self, tail: int = 200, after: int | None = None) -> list[LogEntry]:
        if tail <= 0:
            return []
        with self._lock:
            entries = list(self._ring_buffer)
        if after is not None:
            entries = [entry for entry in entries if entry.id > after]
        if len(entries) <= tail:
            return entries
        return entries[-tail:]

    def reset(self) -> None:
        with self._lock:
            self._ring_buffer.clear()
            self._subscribers.clear()
            self._loop = None
            self._next_id = 1

    @staticmethod
    def _offer_to_subscriber(queue: asyncio.Queue[LogEntry], entry: LogEntry) -> None:
        try:
            queue.put_nowait(entry)
            return
        except asyncio.QueueFull:
            pass

        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        try:
            queue.put_nowait(entry)
        except asyncio.QueueFull:
            pass


class _RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _broker.publish(record)


_broker = LogBroker()
_handler: _RingHandler | None = None


def setup_logging() -> None:
    global _handler

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    _broker.set_loop(loop)

    if _handler is None:
        _handler = _RingHandler()

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if _handler not in root.handlers:
        root.addHandler(_handler)


def subscribe() -> asyncio.Queue[LogEntry]:
    return _broker.subscribe()


def unsubscribe(queue: asyncio.Queue[LogEntry]) -> None:
    _broker.unsubscribe(queue)


def get_recent(tail: int = 200, after: int | None = None) -> list[LogEntry]:
    return _broker.get_recent(tail=tail, after=after)


def _reset_for_tests() -> None:
    global _handler

    root = logging.getLogger()
    if _handler is not None and _handler in root.handlers:
        root.removeHandler(_handler)
    _handler = None
    _broker.reset()
