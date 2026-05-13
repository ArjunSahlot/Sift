from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import queries

router = APIRouter(prefix="/api", tags=["clips"])


@router.get("/videos/{video_id}/clips")
def get_video_clips(video_id: str) -> list[dict]:
    if queries.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return [queries.clip_response(clip) for clip in queries.get_clips_for_video(video_id)]
