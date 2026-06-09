from __future__ import annotations

import logging
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import logger
from app.api import admin, albums, assets, auth, folders, shares
from app.config import settings
from app.db import create_db_and_tables
from app.services.watcher import LibraryWatcher


logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.ERROR)
logging.getLogger("PIL.Image").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*PNG file does not have exif data.*")
warnings.filterwarnings("ignore", message=".*File format not recognized.*")


watcher = LibraryWatcher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.setup_logging()
    if settings.watch_enabled:
        watcher.start()
    yield
    watcher.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.library_watcher = watcher

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(folders.router)
app.include_router(assets.router)
app.include_router(albums.router)
app.include_router(admin.router)
app.include_router(shares.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
