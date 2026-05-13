from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import queries
from app.pipeline.embeddings import search_embeddings

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search_clips(
    q: str = Query(default=""),
    quality: str = Query(default="any"),
    type: str = Query(default="any"),
    duration: str = Query(default="any"),
    speaker: str = Query(default="any"),
    axis: str = Query(default="any"),
    speech: str = Query(default="any"),
    embedding: str = Query(default="any"),
) -> list[dict]:
    semantic_matches = search_embeddings(q) if q.strip() else []
    semantic_by_id = {match["clipId"]: match for match in semantic_matches}
    semantic_clip_ids = list(semantic_by_id) if semantic_matches else None
    clips = queries.search_clips(
        query=q,
        quality=quality,
        clip_type=type,
        duration=duration,
        speaker=speaker,
        face_axis=axis,
        speech=speech,
        embedding=embedding,
        semantic_clip_ids=semantic_clip_ids,
    )
    if semantic_matches:
        for clip in clips:
            match = semantic_by_id.get(clip["id"])
            if match:
                clip["semantic_score"] = match["semanticScore"]
                clip["best_frame_url"] = match.get("bestFrameUrl")
                clip["best_frame_time_seconds"] = match.get("bestFrameTimeSeconds")
    return [
        queries.clip_response(clip)
        for clip in clips
    ]
