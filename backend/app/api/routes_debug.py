from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db import queries
from app.db.session import get_connection
from app.pipeline.debug_artifacts import read_video_debug
from app.pipeline.probe import probe_video
from app.utils.files import media_url

router = APIRouter(prefix="/api", tags=["debug"])


STAGE_ORDER = [
    "probing_video",
    "normalizing",
    "extracting_audio",
    "detecting_scenes",
    "detecting_speech",
    "extracting_clips",
    "generating_thumbnails",
    "running_face_detection",
    "scoring_quality",
    "transcribing",
    "saving_results",
    "indexing_embeddings",
]

STAGE_LABELS = {
    "probing_video": "Probe video",
    "normalizing": "Normalize video",
    "extracting_audio": "Extract audio",
    "detecting_scenes": "Detect scenes",
    "detecting_speech": "Detect speech (VAD)",
    "extracting_clips": "Extract clips",
    "generating_thumbnails": "Generate thumbnails",
    "running_face_detection": "Face detection",
    "scoring_quality": "Score quality",
    "transcribing": "Transcribe",
    "saving_results": "Save results",
    "indexing_embeddings": "Index embeddings",
}

STAGE_MODULES = {
    "probing_video": "app.pipeline.probe.probe_video",
    "normalizing": "app.pipeline.normalize.normalize_video",
    "extracting_audio": "app.pipeline.audio.extract_audio",
    "detecting_scenes": "app.pipeline.scenes.detect_scenes",
    "detecting_speech": "app.pipeline.vad.analyze_speech_segments",
    "extracting_clips": "app.pipeline.clip_extract.extract_clip",
    "generating_thumbnails": "app.pipeline.thumbnails.generate_thumbnail",
    "running_face_detection": "app.pipeline.face_detect.score_faces",
    "scoring_quality": "app.pipeline.quality.classify_clip",
    "transcribing": "app.pipeline.transcribe.transcribe_clip",
    "saving_results": "app.db.queries.insert_clip",
    "indexing_embeddings": "app.pipeline.embeddings.build_embedding_index",
}


@router.get("/videos/{video_id}/debug")
def get_video_debug(video_id: str) -> dict[str, Any]:
    if not settings.enable_debug_artifacts:
        raise HTTPException(status_code=404, detail="Debug artifacts are disabled.")

    video = queries.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    job = _latest_job_for_video(video_id)
    clips = queries.get_clips_for_video(video_id, "all")
    debug_payload = read_video_debug(video_id) or {}
    stored_stages = debug_payload.get("stages") if isinstance(debug_payload, dict) else {}
    if not isinstance(stored_stages, dict):
        stored_stages = {}

    media_clips = _media_clips(video_id, clips, stored_stages)
    stages = _stage_payloads(video, job, clips, stored_stages, media_clips)
    duration_seconds = _duration_seconds(video, media_clips, stored_stages)

    return {
        "schemaVersion": debug_payload.get("schemaVersion", 1),
        "video": {
            "id": video["id"],
            "title": video["title"],
            "filename": video["filename"],
            "sourceType": video["source_type"],
            "status": video["status"],
            "createdAt": video["created_at"],
            "updatedAt": video["updated_at"],
            "raw": _file_info(video.get("raw_path")),
            "normalized": _file_info(video.get("normalized_path")),
            "coverThumbnail": _file_info(video.get("thumbnail_path")),
            "durationSeconds": video.get("duration_seconds"),
            "fileSizeMb": video.get("file_size_mb"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("fps"),
        },
        "job": _job_response(job),
        "settings": {
            "maxDurationSeconds": settings.max_duration_seconds,
            "maxClipsPerVideo": settings.max_clips_per_video,
            "maxClipDurationSeconds": settings.max_clip_duration_seconds,
            "debugArtifactPath": str(settings.debug_dir / video_id / "pipeline.json"),
        },
        "media": {
            "rawUrl": media_url(video.get("raw_path")),
            "normalizedUrl": media_url(video.get("normalized_path")),
            "coverThumbnailUrl": media_url(video.get("thumbnail_path")),
            "clips": media_clips,
        },
        "timeline": {
            "durationSeconds": duration_seconds,
            "tracks": _timeline_tracks(duration_seconds, stored_stages, media_clips),
        },
        "stages": stages,
    }


def _stage_payloads(
    video: dict[str, Any],
    job: dict[str, Any] | None,
    clips: list[dict[str, Any]],
    stored_stages: dict[str, Any],
    media_clips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_stage = job.get("progress_stage") if job else None
    job_status = job.get("status") if job else None
    return [
        _stage_payload(
            stage_id,
            video,
            job,
            clips,
            stored_stages.get(stage_id) if isinstance(stored_stages.get(stage_id), dict) else {},
            media_clips,
            current_stage,
            job_status,
        )
        for stage_id in STAGE_ORDER
    ]


def _stage_payload(
    stage_id: str,
    video: dict[str, Any],
    job: dict[str, Any] | None,
    clips: list[dict[str, Any]],
    stored: dict[str, Any],
    media_clips: list[dict[str, Any]],
    current_stage: str | None,
    job_status: str | None,
) -> dict[str, Any]:
    if stage_id == "indexing_embeddings":
        return {
            "id": stage_id,
            "label": STAGE_LABELS[stage_id],
            "status": _embedding_stage_status(media_clips),
            "module": STAGE_MODULES[stage_id],
            "startedAt": None,
            "completedAt": None,
            "error": None,
            "inputs": {"clips": len(media_clips), "model": "clip-ViT-B-32"},
            "outputs": _embedding_outputs(media_clips),
        }

    outputs = stored.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        outputs = _fallback_outputs(stage_id, video, clips, media_clips)
    inputs = stored.get("inputs")
    if not isinstance(inputs, dict):
        inputs = _fallback_inputs(stage_id, video)

    return {
        "id": stage_id,
        "label": STAGE_LABELS[stage_id],
        "status": _stage_status(stage_id, stored, current_stage, job_status),
        "module": STAGE_MODULES[stage_id],
        "startedAt": stored.get("startedAt"),
        "completedAt": stored.get("completedAt"),
        "error": stored.get("error") or (job.get("error") if job and stage_id == current_stage else None),
        "inputs": _public_files(inputs),
        "outputs": _public_files(outputs),
    }


def _fallback_inputs(stage_id: str, video: dict[str, Any]) -> dict[str, Any]:
    if stage_id == "probing_video":
        return {"raw": _file_info(video.get("raw_path"))}
    if stage_id in {"normalizing", "extracting_audio", "detecting_scenes", "detecting_speech"}:
        return {"normalized": _file_info(video.get("normalized_path"))}
    return {}


def _fallback_outputs(
    stage_id: str,
    video: dict[str, Any],
    clips: list[dict[str, Any]],
    media_clips: list[dict[str, Any]],
) -> dict[str, Any]:
    if stage_id == "probing_video":
        probed, error = _probe_safely(video.get("normalized_path") or video.get("raw_path"))
        return {"metadata": probed, "error": error}
    if stage_id == "normalizing":
        return {
            "normalized": _file_info(video.get("normalized_path")),
            "coverThumbnail": _file_info(video.get("thumbnail_path")),
        }
    if stage_id == "detecting_speech":
        return {"segments": [_segment_from_clip(clip) for clip in clips]}
    if stage_id == "detecting_scenes":
        return {"scenes": [_segment_from_clip(clip) for clip in clips]}
    if stage_id in {"extracting_clips", "generating_thumbnails"}:
        return {"clips": media_clips}
    if stage_id == "running_face_detection":
        return {
            "clips": [
                {
                    "id": clip["id"],
                    "start": clip["start_time"],
                    "end": clip["end_time"],
                    "faceScore": clip["face_score"],
                }
                for clip in clips
            ]
        }
    if stage_id == "scoring_quality":
        return {"clips": media_clips}
    if stage_id == "transcribing":
        return {
            "clips": [
                {"id": clip["id"], "quality": clip["quality"], "transcript": clip.get("transcript")}
                for clip in clips
            ],
            "note": "transcribe_clip() may be a stub when ASR is not configured.",
        }
    if stage_id == "saving_results":
        return {"clipRowsWritten": len(clips), "videoStatus": video.get("status")}
    return {}


def _media_clips(
    video_id: str,
    db_clips: list[dict[str, Any]],
    stored_stages: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for stage_id in STAGE_ORDER:
        stage = stored_stages.get(stage_id)
        if not isinstance(stage, dict):
            continue
        outputs = stage.get("outputs")
        if not isinstance(outputs, dict):
            continue
        for item in outputs.get("clips") or []:
            if isinstance(item, dict) and item.get("id"):
                clip_id = str(item["id"])
                by_id.setdefault(clip_id, {}).update(item)

    for row in db_clips:
        clip_id = str(row["id"])
        by_id.setdefault(clip_id, {})
        by_id[clip_id].update(
            {
                "id": clip_id,
                "start": row["start_time"],
                "end": row["end_time"],
                "duration": row["duration"],
                "quality": row["quality"],
                "qualityScore": row["quality_score"],
                "speechScore": row["speech_score"],
                "faceScore": row["face_score"],
                "audioScore": row["audio_score"],
                "hasSpeech": bool(row.get("has_speech")),
                "speechCoverage": row.get("speech_coverage"),
                "speakerCount": row.get("speaker_count"),
                "speakerBucket": row.get("speaker_bucket"),
                "faceAxis": row.get("face_axis"),
                "embeddingStatus": row.get("embedding_status"),
                "transcript": row.get("transcript"),
                "tags": _json_list(row.get("tags_json")),
                "rejectionReasons": _json_list(row.get("rejection_reasons_json")),
                "exportable": bool(row["exportable"]),
                "path": _file_info(row.get("clip_path")),
                "thumbnail": _file_info(row.get("thumbnail_path")),
            }
        )

    clips = []
    for item in by_id.values():
        clip_path = _path_from_artifact(item.get("path"))
        thumbnail_path = _path_from_artifact(item.get("thumbnail"))
        clips.append(
            {
                "id": item.get("id"),
                "index": item.get("index"),
                "start": item.get("start"),
                "end": item.get("end"),
                "duration": item.get("duration"),
                "clipUrl": media_url(clip_path),
                "thumbnailUrl": media_url(thumbnail_path),
                "quality": item.get("quality"),
                "qualityScore": item.get("qualityScore"),
                "speechScore": item.get("speechScore"),
                "faceScore": item.get("faceScore"),
                "audioScore": item.get("audioScore"),
                "hasSpeech": item.get("hasSpeech"),
                "speechCoverage": item.get("speechCoverage"),
                "speakerCount": item.get("speakerCount"),
                "speakerBucket": item.get("speakerBucket"),
                "faceAxis": item.get("faceAxis"),
                "embeddingStatus": item.get("embeddingStatus"),
                "tags": item.get("tags") or [],
                "rejectionReasons": item.get("rejectionReasons") or [],
                "exportable": item.get("exportable"),
                "transcript": item.get("transcript"),
                "faceStats": item.get("faceStats") or {},
                "audioStats": item.get("audioStats") or {},
                "files": {
                    "clip": _file_info(clip_path),
                    "thumbnail": _file_info(thumbnail_path),
                },
            }
        )

    return sorted(
        clips,
        key=lambda clip: (
            float(clip["start"]) if clip.get("start") is not None else 1_000_000.0,
            str(clip.get("id") or ""),
        ),
    )


def _timeline_tracks(
    duration_seconds: float,
    stored_stages: dict[str, Any],
    media_clips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    speech_outputs = _stage_outputs(stored_stages, "detecting_speech")
    speech_segments = [
        _timeline_segment(
            f"speech_{index + 1}",
            "Speech",
            segment.get("start"),
            segment.get("end"),
            "speech",
        )
        for index, segment in enumerate(speech_outputs.get("segments") or [])
        if isinstance(segment, dict)
    ]
    clip_segments = [
        _timeline_segment(
            str(clip.get("id")),
            f"Clip {clip.get('index') or index + 1}",
            clip.get("start"),
            clip.get("end"),
            "clip",
            clip_id=clip.get("id"),
        )
        for index, clip in enumerate(media_clips)
    ]

    face_segments = _face_segments(media_clips, duration_seconds)
    quality_segments = [
        _timeline_segment(
            f"quality_{clip.get('id')}",
            str(clip.get("quality") or "unscored"),
            clip.get("start"),
            clip.get("end"),
            "quality",
            clip_id=clip.get("id"),
            quality=clip.get("quality"),
            score=clip.get("qualityScore"),
        )
        for clip in media_clips
        if clip.get("quality")
    ]

    return [
        {
            "id": "speech",
            "label": "Speech VAD",
            "description": "Silero VAD speech regions overlaid on scene clips.",
            "segments": _bounded_segments(speech_segments, duration_seconds),
        },
        {
            "id": "clips",
            "label": "Extracted Clips",
            "description": "MP4 clips produced by FFmpeg from speech candidates.",
            "segments": _bounded_segments(clip_segments, duration_seconds),
        },
        {
            "id": "faces",
            "label": "Face Detected",
            "description": "One-second samples where the face detector found a face.",
            "segments": _bounded_segments(face_segments, duration_seconds),
        },
        {
            "id": "quality",
            "label": "Quality Labels",
            "description": "Final curation decision per clip.",
            "segments": _bounded_segments(quality_segments, duration_seconds),
        },
        {
            "id": "embeddings",
            "label": "Embedding Index",
            "description": "CLIP frame embedding status for semantic search.",
            "segments": _bounded_segments(
                [
                    _timeline_segment(
                        f"embedding_{clip.get('id')}",
                        str(clip.get("embeddingStatus") or "pending"),
                        clip.get("start"),
                        clip.get("end"),
                        "embedding",
                        clip_id=clip.get("id"),
                    )
                    for clip in media_clips
                ],
                duration_seconds,
            ),
        },
    ]


def _embedding_outputs(media_clips: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for clip in media_clips:
        status = str(clip.get("embeddingStatus") or "pending")
        counts[status] = counts.get(status, 0) + 1
    return {
        "statusCounts": counts,
        "clips": [
            {"id": clip.get("id"), "embeddingStatus": clip.get("embeddingStatus")}
            for clip in media_clips
        ],
    }


def _embedding_stage_status(media_clips: list[dict[str, Any]]) -> str:
    statuses = {str(clip.get("embeddingStatus") or "pending") for clip in media_clips}
    if not media_clips:
        return "pending"
    if "indexing" in statuses:
        return "running"
    if "failed" in statuses:
        return "failed"
    if statuses == {"complete"}:
        return "complete"
    return "pending"


def _face_segments(
    media_clips: list[dict[str, Any]],
    duration_seconds: float,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for clip in media_clips:
        samples = (clip.get("faceStats") or {}).get("samples") or []
        for sample_index, sample in enumerate(samples):
            if not isinstance(sample, dict) or not sample.get("hasFace"):
                continue
            start = float(sample.get("absoluteTime") or clip.get("start") or 0)
            end = min(float(clip.get("end") or duration_seconds), start + 1.0)
            segments.append(
                _timeline_segment(
                    f"face_{clip.get('id')}_{sample_index}",
                    f"{sample.get('faceCount', 1)} face",
                    start,
                    end,
                    "face",
                    clip_id=clip.get("id"),
                    score=sample.get("largestFaceSizeRatio"),
                )
            )
        if not samples and float(clip.get("faceScore") or 0) >= 0.3:
            segments.append(
                _timeline_segment(
                    f"face_{clip.get('id')}",
                    "Face likely",
                    clip.get("start"),
                    clip.get("end"),
                    "face",
                    clip_id=clip.get("id"),
                    score=clip.get("faceScore"),
                )
            )
    return segments


def _timeline_segment(
    segment_id: str,
    label: str,
    start: Any,
    end: Any,
    kind: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": segment_id,
        "label": label,
        "start": float(start or 0),
        "end": float(end or start or 0),
        "kind": kind,
        **{key: value for key, value in extra.items() if value is not None},
    }


def _bounded_segments(
    segments: list[dict[str, Any]],
    duration_seconds: float,
) -> list[dict[str, Any]]:
    bounded = []
    for segment in segments:
        start = max(0.0, min(float(segment["start"]), duration_seconds))
        end = max(start, min(float(segment["end"]), duration_seconds))
        bounded.append({**segment, "start": start, "end": end})
    return bounded


def _stage_outputs(stored_stages: dict[str, Any], stage_id: str) -> dict[str, Any]:
    stage = stored_stages.get(stage_id)
    if not isinstance(stage, dict):
        return {}
    outputs = stage.get("outputs")
    return outputs if isinstance(outputs, dict) else {}


def _duration_seconds(
    video: dict[str, Any],
    media_clips: list[dict[str, Any]],
    stored_stages: dict[str, Any],
) -> float:
    candidates = [float(video.get("duration_seconds") or 0)]
    speech_outputs = _stage_outputs(stored_stages, "detecting_speech")
    candidates.extend(
        float(segment.get("end") or 0)
        for segment in speech_outputs.get("segments") or []
        if isinstance(segment, dict)
    )
    candidates.extend(float(clip.get("end") or 0) for clip in media_clips)
    return max(candidates + [1.0])


def _stage_status(
    target: str,
    stored: dict[str, Any],
    current: str | None,
    job_status: str | None,
) -> str:
    stored_status = stored.get("status")
    inferred = _inferred_stage_status(target, current, job_status)
    if stored_status == "failed" or inferred == "failed":
        return "failed"
    if stored_status == "complete":
        return "complete"
    if stored_status == "running" and inferred != "complete":
        return "running"
    return inferred


def _inferred_stage_status(target: str, current: str | None, job_status: str | None) -> str:
    if current is None:
        return "pending"
    target_index = STAGE_ORDER.index(target)
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


def _job_response(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return queries.job_response(job)


def _file_info(path_str: str | Path | None) -> dict[str, Any]:
    if not path_str:
        return {"path": None, "exists": False, "sizeBytes": None, "url": None}
    path = Path(path_str)
    exists = path.exists()
    size = path.stat().st_size if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "sizeBytes": size,
        "url": media_url(path),
    }


def _public_files(value: Any) -> Any:
    if isinstance(value, list):
        return [_public_files(item) for item in value]
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str):
            return {**{key: _public_files(item) for key, item in value.items()}, "url": media_url(path)}
        return {key: _public_files(item) for key, item in value.items()}
    return value


def _path_from_artifact(value: Any) -> str | None:
    if isinstance(value, dict):
        path = value.get("path")
        return str(path) if path else None
    if isinstance(value, str):
        return value
    return None


def _segment_from_clip(clip: dict[str, Any]) -> dict[str, Any]:
    return {
        "clipId": clip["id"],
        "start": clip["start_time"],
        "end": clip["end_time"],
        "duration": clip["duration"],
    }


def _probe_safely(path_str: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path_str:
        return None, "no source path on record"
    path = Path(path_str)
    if not path.exists():
        return None, f"file does not exist on disk: {path}"
    try:
        return probe_video(path), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


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
