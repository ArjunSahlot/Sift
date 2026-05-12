from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import queries

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search_clips(
    q: str = Query(default=""),
    quality: str = Query(default="any"),
    type: str = Query(default="any"),
    duration: str = Query(default="any"),
) -> list[dict]:
    return [
        queries.clip_response(clip)
        for clip in queries.search_clips(
            query=q,
            quality=quality,
            clip_type=type,
            duration=duration,
        )
    ]
