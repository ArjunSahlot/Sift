from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import queries

router = APIRouter(prefix="/api", tags=["videos"])


@router.get("/videos")
def list_videos() -> list[dict]:
    return [queries.video_response(video) for video in queries.list_videos()]


@router.get("/videos/{video_id}")
def get_video(video_id: str) -> dict:
    video = queries.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return queries.video_detail_response(video)
