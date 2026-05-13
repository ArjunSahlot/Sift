from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import queries
from app.utils.ids import new_id

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


@router.post("/videos/{video_id}/reprocess")
def reprocess_video(video_id: str) -> dict:
    video = queries.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    
    # Check max queued jobs
    from app.config import settings
    if queries.queued_job_count() >= settings.max_queue_size:
        raise HTTPException(status_code=429, detail="Upload queue is full.")

    queries.delete_clips_for_video(video_id)
    queries.refresh_video_counts(video_id)
    
    job_id = new_id("job")
    queries.update_video(video_id, status="queued")
    queries.create_job({"id": job_id, "video_id": video_id})
    return {"videoId": video_id, "jobId": job_id, "status": "queued"}
