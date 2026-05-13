from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_clips,
    routes_debug,
    routes_export,
    routes_health,
    routes_jobs,
    routes_search,
    routes_upload,
    routes_videos,
)
from app.config import settings
from app.db.init import init_db
from app.utils.files import ensure_data_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

ensure_data_dirs()
init_db()

app = FastAPI(title="Sift API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_upload.router)
app.include_router(routes_videos.router)
app.include_router(routes_jobs.router)
app.include_router(routes_clips.router)
app.include_router(routes_search.router)
app.include_router(routes_export.router)
app.include_router(routes_debug.router)

app.mount("/media", StaticFiles(directory=settings.storage_dir), name="media")
