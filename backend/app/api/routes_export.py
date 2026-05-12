from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.db import queries
from app.utils.files import media_url
from app.utils.ids import new_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["export"])


class ExportRequest(BaseModel):
    mode: Literal["video", "query"]
    videoId: str | None = None
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    includeClips: bool = True
    includeThumbnails: bool = True
    includeManifest: bool = True
    includeSummary: bool = True
    includeTranscripts: bool = True
    includeQualityScores: bool = True
    includeTags: bool = True
    includeRejectionReasons: bool = True


@router.post("/export")
def create_export(payload: ExportRequest) -> dict[str, str]:
    clips = _select_export_clips(payload)
    export_id = new_id("export")
    export_path = settings.exports_dir / f"{export_id}.zip"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest_rows = []
        for clip in clips:
            record = queries.clip_export_record(clip)
            clip_path = Path(record["clipPath"]) if record.get("clipPath") else None
            thumbnail_path = (
                Path(record["thumbnailPath"]) if record.get("thumbnailPath") else None
            )

            if payload.includeClips and clip_path and clip_path.exists():
                archive.write(clip_path, f"clips/{clip_path.name}")
                record["exportClipPath"] = f"clips/{clip_path.name}"
            if payload.includeThumbnails and thumbnail_path and thumbnail_path.exists():
                archive.write(thumbnail_path, f"thumbnails/{thumbnail_path.name}")
                record["exportThumbnailPath"] = f"thumbnails/{thumbnail_path.name}"

            manifest_rows.append(_manifest_record(record, payload))

        if payload.includeManifest:
            archive.writestr(
                "manifest.jsonl",
                "".join(json.dumps(row) + "\n" for row in manifest_rows),
            )
        if payload.includeSummary:
            archive.writestr(
                "summary.json",
                json.dumps(_summary(clips, payload), indent=2),
            )

    queries.create_export(
        {
            "id": export_id,
            "mode": payload.mode,
            "query": payload.query,
            "filters_json": json.dumps(payload.filters),
            "export_path": str(export_path),
            "status": "complete",
        }
    )
    logger.info("export_created export_id=%s clips=%s", export_id, len(clips))
    return {
        "exportId": export_id,
        "status": "complete",
        "downloadUrl": media_url(export_path) or f"/media/exports/{export_path.name}",
    }


def _select_export_clips(payload: ExportRequest) -> list[dict]:
    quality = str(payload.filters.get("quality") or "any")
    if payload.mode == "video":
        if not payload.videoId:
            raise HTTPException(status_code=400, detail="videoId is required.")
        if queries.get_video(payload.videoId) is None:
            raise HTTPException(status_code=404, detail="Video not found.")
        query_quality = quality if quality in {"good", "review", "rejected"} else "all"
        return queries.get_clips_for_video(payload.videoId, query_quality)

    clip_type = str(payload.filters.get("type") or "any")
    duration = str(payload.filters.get("duration") or "any")
    return queries.search_clips(
        query=payload.query or "",
        quality=quality,
        clip_type=clip_type,
        duration=duration,
    )


def _manifest_record(record: dict, payload: ExportRequest) -> dict:
    output = {
        "id": record["id"],
        "videoId": record["videoId"],
        "sourceVideoTitle": record["sourceVideoTitle"],
        "clipUrl": record["clipUrl"],
        "thumbnailUrl": record["thumbnailUrl"],
        "startTime": record["startTime"],
        "endTime": record["endTime"],
        "duration": record["duration"],
        "quality": record["quality"],
        "exportable": record["exportable"],
    }
    if payload.includeTranscripts:
        output["transcript"] = record["transcript"]
    if payload.includeQualityScores:
        output["qualityScore"] = record["qualityScore"]
        output["speechScore"] = record["speechScore"]
        output["faceScore"] = record["faceScore"]
        output["audioScore"] = record["audioScore"]
    if payload.includeTags:
        output["tags"] = record["tags"]
    if payload.includeRejectionReasons:
        output["rejectionReasons"] = record["rejectionReasons"]
    if "exportClipPath" in record:
        output["exportClipPath"] = record["exportClipPath"]
    if "exportThumbnailPath" in record:
        output["exportThumbnailPath"] = record["exportThumbnailPath"]
    return output


def _summary(clips: list[dict], payload: ExportRequest) -> dict:
    counts = {"good": 0, "review": 0, "rejected": 0}
    total_duration = 0.0
    for clip in clips:
        counts[clip["quality"]] = counts.get(clip["quality"], 0) + 1
        total_duration += float(clip["duration"] or 0)
    return {
        "mode": payload.mode,
        "query": payload.query,
        "filters": payload.filters,
        "clipCount": len(clips),
        "qualityCounts": counts,
        "totalDurationSeconds": round(total_duration, 3),
    }
