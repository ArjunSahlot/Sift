from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db import queries

router = APIRouter(prefix="/api", tags=["debug"])


STAGE_ORDER = [
    "probing_video",
    "normalizing",
    "extracting_audio",
    "detecting_speech",
    "extracting_clips",
    "generating_thumbnails",
    "running_face_detection",
    "scoring_quality",
    "transcribing",
    "saving_results",
]

STAGE_LABELS = {
    "probing_video": "Probe video",
    "normalizing": "Normalize video",
    "extracting_audio": "Extract audio",
    "detecting_speech": "Detect speech (VAD)",
    "extracting_clips": "Extract clips",
    "generating_thumbnails": "Generate thumbnails",
    "running_face_detection": "Face detection",
    "scoring_quality": "Score quality",
    "transcribing": "Transcribe",
    "saving_results": "Save results",
}


def _file_info(path_str: str | None) -> dict[str, Any]:
    if not path_str:
        return {"path": None, "exists": False, "sizeBytes": None}
    path = Path(path_str)
    exists = path.exists()
    size = path.stat().st_size if exists else None
    return {"path": str(path), "exists": exists, "sizeBytes": size}


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _stage_status(target: str, current: str | None, job_status: str | None) -> str:
    if current is None:
        return "pending"
    try:
        target_index = STAGE_ORDER.index(target)
    except ValueError:
        return "pending"

    if job_status == "complete":
        return "complete"

    if current in STAGE_ORDER:
        current_index = STAGE_ORDER.index(current)
    elif current == "complete":
        return "complete"
    else:
        current_index = -1

    if job_status == "failed":
        if target_index < current_index:
            return "complete"
        if target_index == current_index:
            return "failed"
        return "pending"

    if target_index < current_index:
        return "complete"
    if target_index == current_index:
        return "running"
    return "pending"


def _latest_job_for_video(video_id: str) -> dict[str, Any] | None:
    from app.db.session import get_connection

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM jobs
            WHERE video_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (video_id,),
        ).fetchone()
    return dict(row) if row else None


def _probe_safely(path_str: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path_str:
        return None, "no source path on record"
    path = Path(path_str)
    if not path.exists():
        return None, f"file does not exist on disk: {path}"
    try:
        from app.pipeline.probe import probe_video

        return probe_video(path), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


@router.get("/videos/{video_id}/debug")
def get_video_debug(video_id: str) -> dict[str, Any]:
    video = queries.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    job = _latest_job_for_video(video_id)
    clips = queries.get_clips_for_video(video_id, "all")

    raw_file = _file_info(video.get("raw_path"))
    normalized_file = _file_info(video.get("normalized_path"))
    cover_file = _file_info(video.get("thumbnail_path"))

    probe_source = video.get("normalized_path") or video.get("raw_path")
    probe_output, probe_error = _probe_safely(probe_source)

    current_stage = job.get("progress_stage") if job else None
    job_status = job.get("status") if job else None

    segments = [
        {
            "index": idx + 1,
            "clipId": clip["id"],
            "start": clip["start_time"],
            "end": clip["end_time"],
            "duration": clip["duration"],
        }
        for idx, clip in enumerate(clips)
    ]

    eligible_for_transcript = sum(
        1 for clip in clips if clip["quality"] in {"good", "review"}
    )

    stages: list[dict[str, Any]] = [
        {
            "id": "probing_video",
            "label": STAGE_LABELS["probing_video"],
            "status": _stage_status("probing_video", current_stage, job_status),
            "module": "app.pipeline.probe.probe_video",
            "inputs": {"file": raw_file},
            "outputs": {
                "probed": probe_output,
                "error": probe_error,
                "storedFromDb": {
                    "durationSeconds": video.get("duration_seconds"),
                    "fileSizeMb": video.get("file_size_mb"),
                    "width": video.get("width"),
                    "height": video.get("height"),
                    "fps": video.get("fps"),
                },
            },
        },
        {
            "id": "normalizing",
            "label": STAGE_LABELS["normalizing"],
            "status": _stage_status("normalizing", current_stage, job_status),
            "module": "app.pipeline.normalize.normalize_video",
            "inputs": {"raw": raw_file},
            "outputs": {
                "normalized": normalized_file,
                "coverThumbnail": cover_file,
            },
        },
        {
            "id": "extracting_audio",
            "label": STAGE_LABELS["extracting_audio"],
            "status": _stage_status("extracting_audio", current_stage, job_status),
            "module": "app.pipeline.audio.extract_audio",
            "inputs": {"normalized": normalized_file},
            "outputs": {
                "format": "mono WAV @ 16 kHz",
                "path": "tmp/<job_id>/audio.wav (deleted on job teardown)",
            },
        },
        {
            "id": "detecting_speech",
            "label": STAGE_LABELS["detecting_speech"],
            "status": _stage_status("detecting_speech", current_stage, job_status),
            "module": "app.pipeline.vad.detect_speech_segments",
            "inputs": {
                "audio": "tmp WAV",
                "minSegmentSeconds": 3.0,
                "mergeGapSeconds": 0.5,
                "maxSegmentSeconds": settings.max_clip_duration_seconds,
                "maxSegments": settings.max_clips_per_video,
            },
            "outputs": {
                "segmentCount": len(segments),
                "segments": segments,
                "note": "Segments are derived from persisted clip rows (start/end). "
                "Raw RMS / threshold values are not stored.",
            },
        },
        {
            "id": "extracting_clips",
            "label": STAGE_LABELS["extracting_clips"],
            "status": _stage_status("extracting_clips", current_stage, job_status),
            "module": "app.pipeline.clip_extract.extract_clip",
            "inputs": {"normalized": normalized_file, "segmentsIn": len(segments)},
            "outputs": {
                "clipsOut": len(clips),
                "clips": [
                    {
                        "id": clip["id"],
                        "file": _file_info(clip.get("clip_path")),
                        "startTime": clip["start_time"],
                        "endTime": clip["end_time"],
                        "duration": clip["duration"],
                    }
                    for clip in clips
                ],
            },
        },
        {
            "id": "generating_thumbnails",
            "label": STAGE_LABELS["generating_thumbnails"],
            "status": _stage_status("generating_thumbnails", current_stage, job_status),
            "module": "app.pipeline.thumbnails.generate_thumbnail",
            "inputs": {"clipsCount": len(clips)},
            "outputs": {
                "thumbnails": [
                    {
                        "clipId": clip["id"],
                        "file": _file_info(clip.get("thumbnail_path")),
                    }
                    for clip in clips
                ],
            },
        },
        {
            "id": "running_face_detection",
            "label": STAGE_LABELS["running_face_detection"],
            "status": _stage_status("running_face_detection", current_stage, job_status),
            "module": "app.pipeline.face_detect.score_faces",
            "inputs": {"clipsCount": len(clips)},
            "outputs": {
                "note": "Per-clip face_stats (presence_ratio, sizes, count) are computed "
                "in-memory and not persisted. Only the derived face_score is saved.",
                "faceScores": [
                    {"clipId": clip["id"], "faceScore": clip["face_score"]}
                    for clip in clips
                ],
            },
        },
        {
            "id": "scoring_quality",
            "label": STAGE_LABELS["scoring_quality"],
            "status": _stage_status("scoring_quality", current_stage, job_status),
            "module": "app.pipeline.quality.classify_clip",
            "inputs": {
                "thresholds": {
                    "speechMin": 0.45,
                    "faceMin": 0.30,
                    "audioReviewBelow": 0.35,
                    "audioCleanAt": 0.65,
                    "goodAt": 0.75,
                    "durationMin": 3,
                    "durationMax": 20,
                },
            },
            "outputs": {
                "classifications": [
                    {
                        "clipId": clip["id"],
                        "quality": clip["quality"],
                        "qualityScore": clip["quality_score"],
                        "speechScore": clip["speech_score"],
                        "faceScore": clip["face_score"],
                        "audioScore": clip["audio_score"],
                        "tags": _json_list(clip.get("tags_json")),
                        "rejectionReasons": _json_list(clip.get("rejection_reasons_json")),
                        "exportable": bool(clip["exportable"]),
                    }
                    for clip in clips
                ],
            },
        },
        {
            "id": "transcribing",
            "label": STAGE_LABELS["transcribing"],
            "status": _stage_status("transcribing", current_stage, job_status),
            "module": "app.pipeline.transcribe.transcribe_clip",
            "inputs": {"eligibleClips": eligible_for_transcript},
            "outputs": {
                "note": "transcribe_clip() is a stub that always returns None.",
                "transcripts": [
                    {
                        "clipId": clip["id"],
                        "quality": clip["quality"],
                        "transcript": clip.get("transcript"),
                    }
                    for clip in clips
                ],
            },
        },
        {
            "id": "saving_results",
            "label": STAGE_LABELS["saving_results"],
            "status": _stage_status("saving_results", current_stage, job_status),
            "module": "app.db.queries.mark_job_complete",
            "inputs": {"clipRowsWritten": len(clips)},
            "outputs": {
                "videoStatus": video.get("status"),
                "jobStatus": job_status,
                "completedAt": job.get("completed_at") if job else None,
            },
        },
    ]

    return {
        "video": {
            "id": video["id"],
            "title": video["title"],
            "filename": video["filename"],
            "sourceType": video["source_type"],
            "status": video["status"],
            "createdAt": video["created_at"],
            "updatedAt": video["updated_at"],
            "raw": raw_file,
            "normalized": normalized_file,
            "coverThumbnail": cover_file,
            "durationSeconds": video.get("duration_seconds"),
            "fileSizeMb": video.get("file_size_mb"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("fps"),
        },
        "job": job,
        "settings": {
            "maxDurationSeconds": settings.max_duration_seconds,
            "maxClipsPerVideo": settings.max_clips_per_video,
            "maxClipDurationSeconds": settings.max_clip_duration_seconds,
        },
        "stages": stages,
    }
