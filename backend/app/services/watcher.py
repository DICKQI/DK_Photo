from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from sqlmodel import Session, select
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.db import engine
from app.models import LibraryRoot, ScanJob
from app.services.operation_log import log_operation
from app.services.paths import is_docker_photos_root
from app.services.scanner import active_scan_job, is_supported_media, run_scan_job


class DebouncedScanHandler(FileSystemEventHandler):
    def __init__(self, library_id: int, schedule_scan: Callable[[int], None]) -> None:
        self.library_id = library_id
        self.schedule_scan = schedule_scan

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            self.schedule_scan(self.library_id)
            return
        if is_supported_media(Path(event.src_path)):
            self.schedule_scan(self.library_id)


class LibraryWatcher:
    def __init__(self, debounce_seconds: float = 2.0) -> None:
        self.debounce_seconds = debounce_seconds
        self.observer: Observer | None = None
        self.timers: dict[int, threading.Timer] = {}

    def start(self) -> None:
        if self.observer:
            return
        self.observer = Observer()
        self.refresh()
        self.observer.start()

    def stop(self) -> None:
        for timer in self.timers.values():
            timer.cancel()
        self.timers.clear()
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None

    def refresh(self) -> None:
        if not self.observer:
            return
        self.observer.unschedule_all()
        with Session(engine) as session:
            libraries = session.exec(
                select(LibraryRoot).where(
                    LibraryRoot.is_enabled == True,  # noqa: E712
                    LibraryRoot.watch_enabled == True,  # noqa: E712
                )
            ).all()
            for library in libraries:
                path = Path(library.path)
                if is_docker_photos_root(library.path):
                    continue
                try:
                    is_existing_directory = path.exists() and path.is_dir()
                except OSError:
                    continue
                if is_existing_directory:
                    handler = DebouncedScanHandler(library.id or 0, self.schedule_scan)
                    self.observer.schedule(handler, str(path), recursive=True)

    def schedule_scan(self, library_id: int) -> None:
        existing = self.timers.get(library_id)
        if existing:
            existing.cancel()
        timer = threading.Timer(self.debounce_seconds, self._create_and_run_job, args=(library_id,))
        timer.daemon = True
        self.timers[library_id] = timer
        timer.start()

    def _create_and_run_job(self, library_id: int) -> None:
        self.timers.pop(library_id, None)
        with Session(engine) as session:
            if active_scan_job(session, library_id):
                log_operation(
                    "watcher.scan.skipped",
                    category="task",
                    status="skipped",
                    target_type="library",
                    target_id=library_id,
                    message="Filesystem scan skipped because another scan is active",
                    metadata={"library_id": library_id},
                )
                return
            job = ScanJob(library_id=library_id, status="queued", message="Filesystem change detected")
            session.add(job)
            session.commit()
            session.refresh(job)
            log_operation(
                "watcher.scan.queued",
                category="task",
                status="queued",
                target_type="scan_job",
                target_id=job.id,
                message="Filesystem change queued scan",
                metadata={"job_id": job.id, "library_id": library_id},
            )
            run_scan_job(session, job.id or 0, generate_thumbnails=True)
