from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas import LogEntry


RING_BUFFER_SIZE = 2000
SUBSCRIBER_QUEUE_SIZE = 1000
DEFAULT_HISTORY_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_HISTORY_BACKUP_COUNT = 10


class LogBroker:
    def __init__(self) -> None:
        self._ring_buffer: deque[LogEntry] = deque(maxlen=RING_BUFFER_SIZE)
        self._lock = threading.Lock()
        self._history_lock = threading.Lock()
        self._subscribers: list[asyncio.Queue[LogEntry]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_id = 1
        self._history_path: Path | None = None
        self._history_max_bytes = DEFAULT_HISTORY_MAX_BYTES
        self._history_backup_count = DEFAULT_HISTORY_BACKUP_COUNT

    def configure_history(
        self,
        path: Path,
        max_bytes: int = DEFAULT_HISTORY_MAX_BYTES,
        backup_count: int = DEFAULT_HISTORY_BACKUP_COUNT,
    ) -> None:
        with self._history_lock:
            self._history_path = path
            self._history_max_bytes = max(1, max_bytes)
            self._history_backup_count = max(0, backup_count)
            path.parent.mkdir(parents=True, exist_ok=True)

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
                category=getattr(record, "log_category", None),
                action=getattr(record, "operation_action", None),
                status=getattr(record, "operation_status", None),
                actor_id=getattr(record, "actor_id", None),
                target_type=getattr(record, "target_type", None),
                target_id=_optional_str(getattr(record, "target_id", None)),
                request_id=getattr(record, "request_id", None),
                duration_ms=getattr(record, "duration_ms", None),
                metadata=_metadata_dict(getattr(record, "operation_metadata", None)),
            )
            self._next_id += 1
            self._ring_buffer.append(entry)
            subscribers = list(self._subscribers)
            loop = self._loop

        self._write_history(entry)

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

    def read_history(
        self,
        limit: int = 200,
        cursor: str | None = None,
        level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> tuple[list[LogEntry], str | None]:
        limit = min(max(1, limit), 500)
        try:
            offset = max(0, int(cursor or "0"))
        except ValueError:
            offset = 0

        entries = self._read_history_entries()
        entries.reverse()
        if level:
            level_upper = level.upper()
            entries = [entry for entry in entries if entry.level == level_upper]
        if category:
            entries = [entry for entry in entries if entry.category == category]
        if search:
            query = search.lower()
            entries = [entry for entry in entries if query in _history_search_text(entry)]

        page = entries[offset : offset + limit]
        next_offset = offset + limit
        next_cursor = str(next_offset) if next_offset < len(entries) else None
        return page, next_cursor

    def reset(self) -> None:
        with self._lock:
            self._ring_buffer.clear()
            self._subscribers.clear()
            self._loop = None
            self._next_id = 1
        with self._history_lock:
            self._history_path = None
            self._history_max_bytes = DEFAULT_HISTORY_MAX_BYTES
            self._history_backup_count = DEFAULT_HISTORY_BACKUP_COUNT

    def _write_history(self, entry: LogEntry) -> None:
        with self._history_lock:
            path = self._history_path
            if path is None:
                return
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.stat().st_size >= self._history_max_bytes:
                    self._rotate_history_locked(path)
                payload = json.dumps(entry.model_dump(), ensure_ascii=False, separators=(",", ":"), default=str)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(payload + "\n")
            except OSError:
                return

    def _rotate_history_locked(self, path: Path) -> None:
        if self._history_backup_count <= 0:
            path.unlink(missing_ok=True)
            return
        for idx in range(self._history_backup_count - 1, 0, -1):
            src = Path(f"{path}.{idx}")
            dst = Path(f"{path}.{idx + 1}")
            if src.exists():
                dst.unlink(missing_ok=True)
                src.replace(dst)
        first_backup = Path(f"{path}.1")
        first_backup.unlink(missing_ok=True)
        if path.exists():
            path.replace(first_backup)

    def _read_history_entries(self) -> list[LogEntry]:
        with self._history_lock:
            path = self._history_path
            backup_count = self._history_backup_count
        if path is None:
            return []
        paths = [Path(f"{path}.{idx}") for idx in range(backup_count, 0, -1)]
        paths.append(path)
        entries: list[LogEntry] = []
        for item in paths:
            if not item.exists():
                continue
            try:
                lines = item.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entries.append(LogEntry.model_validate(json.loads(line)))
                except Exception:
                    continue
        return entries

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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _history_search_text(entry: LogEntry) -> str:
    return " ".join(
        [
            entry.message,
            entry.logger,
            entry.level,
            entry.category or "",
            entry.action or "",
            entry.status or "",
            entry.target_type or "",
            entry.target_id or "",
            json.dumps(entry.metadata, ensure_ascii=False, default=str),
        ]
    ).lower()


_broker = LogBroker()
_handler: _RingHandler | None = None


def setup_logging(log_path: Path | None = None) -> None:
    global _handler

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    _broker.set_loop(loop)

    if log_path is not None:
        _broker.configure_history(log_path)
    elif _broker._history_path is None:
        _broker.configure_history(settings.data_dir / "logs" / "app.jsonl")

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


def read_history(
    limit: int = 200,
    cursor: str | None = None,
    level: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> tuple[list[LogEntry], str | None]:
    return _broker.read_history(limit=limit, cursor=cursor, level=level, category=category, search=search)


def _reset_for_tests() -> None:
    global _handler

    root = logging.getLogger()
    if _handler is not None and _handler in root.handlers:
        root.removeHandler(_handler)
    _handler = None
    _broker.reset()
