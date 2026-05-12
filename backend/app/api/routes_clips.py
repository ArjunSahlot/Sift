from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import queries

router = APIRouter(prefix="/api", tags=["clips"])


class ClipQualityUpdate(BaseModel):
    quality: Literal["good", "review", "rejected"]


@router.get("/videos/{video_id}/clips")
def get_video_clips(
    video_id: str,
    quality: Literal["good", "review", "rejected", "all"] = Query(default="all"),
) -> list[dict]:
    if queries.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return [
        queries.clip_response(clip)
        for clip in queries.get_clips_for_video(video_id, quality)
    ]


@router.patch("/clips/{clip_id}")
def update_clip(clip_id: str, payload: ClipQualityUpdate) -> dict:
    try:
        clip = queries.update_clip_quality(clip_id, payload.quality)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found.")
    return queries.clip_response(clip)
