from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from sqlite3 import Row
from typing import Any

from app.db.models import PROGRESS_PERCENT
from app.db.session import connect, get_connection
from app.utils.files import media_url, remove_path, remove_video_files
from app.utils.time import utc_now


def _row_to_dict(row: Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def create_video(values: dict[str, Any]) -> None:
    now = utc_now()
    payload = {
        "created_at": now,
        "updated_at": now,
        "is_example": 0,
        **values,
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO videos (
              id, title, filename, source_type, status, raw_path, normalized_path,
              thumbnail_path, duration_seconds, file_size_mb, width, height, fps,
              created_at, updated_at, is_example
            )
            VALUES (
              :id, :title, :filename, :source_type, :status, :raw_path,
              :normalized_path, :thumbnail_path, :duration_seconds, :file_size_mb,
              :width, :height, :fps, :created_at, :updated_at, :is_example
            )
            """,
            payload,
        )


def create_job(values: dict[str, Any]) -> None:
    now = utc_now()
    payload = {
        "status": "queued",
        "progress_stage": "queued",
        "progress_percent": 0,
        "clips_found": 0,
        "error": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
        **values,
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
              id, video_id, status, progress_stage, progress_percent, clips_found,
              error, started_at, completed_at, created_at, updated_at
            )
            VALUES (
              :id, :video_id, :status, :progress_stage, :progress_percent,
              :clips_found, :error, :started_at, :completed_at, :created_at,
              :updated_at
            )
            """,
            payload,
        )


def queued_job_count() -> int:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM jobs WHERE status IN ('queued', 'processing')"
        ).fetchone()
        return int(row["count"])


def get_video(video_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return _row_to_dict(
            connection.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return _row_to_dict(
            connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        )


def list_videos() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM videos ORDER BY datetime(created_at) DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def update_video(video_id: str, **values: Any) -> None:
    if not values:
        return
    values["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = :{key}" for key in values)
    values["id"] = video_id
    with get_connection() as connection:
        connection.execute(
            f"UPDATE videos SET {assignments} WHERE id = :id",
            values,
        )


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress_stage: str | None = None,
    progress_percent: int | None = None,
    clips_found: int | None = None,
    error: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> None:
    values: dict[str, Any] = {"updated_at": utc_now()}
    if status is not None:
        values["status"] = status
    if progress_stage is not None:
        values["progress_stage"] = progress_stage
        values["progress_percent"] = (
            progress_percent
            if progress_percent is not None
            else PROGRESS_PERCENT.get(progress_stage, 0)
        )
    elif progress_percent is not None:
        values["progress_percent"] = progress_percent
    if clips_found is not None:
        values["clips_found"] = clips_found
    if error is not None:
        values["error"] = error
    if started_at is not None:
        values["started_at"] = started_at
    if completed_at is not None:
        values["completed_at"] = completed_at

    assignments = ", ".join(f"{key} = :{key}" for key in values)
    values["id"] = job_id
    with get_connection() as connection:
        connection.execute(f"UPDATE jobs SET {assignments} WHERE id = :id", values)


def set_stage(job_id: str, video_id: str, stage: str) -> None:
    percent = PROGRESS_PERCENT.get(stage, 0)
    update_job(job_id, status="processing", progress_stage=stage, progress_percent=percent)
    update_video(video_id, status="processing")


def claim_next_queued_job() -> dict[str, Any] | None:
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'queued'
            ORDER BY datetime(created_at) ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            connection.commit()
            return None

        now = utc_now()
        connection.execute(
            """
            UPDATE jobs
            SET status = 'processing',
                progress_stage = 'validating',
                progress_percent = ?,
                started_at = COALESCE(started_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (PROGRESS_PERCENT["validating"], now, now, row["id"]),
        )
        connection.execute(
            "UPDATE videos SET status = 'processing', updated_at = ? WHERE id = ?",
            (now, row["video_id"]),
        )
        connection.commit()
        return get_job(row["id"])
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def mark_job_complete(job_id: str, video_id: str) -> None:
    now = utc_now()
    update_job(
        job_id,
        status="complete",
        progress_stage="complete",
        progress_percent=100,
        completed_at=now,
    )
    refresh_video_counts(video_id)
    update_video(video_id, status="complete")


def mark_job_failed(job_id: str, video_id: str, error: str) -> None:
    now = utc_now()
    update_job(
        job_id,
        status="failed",
        progress_stage="failed",
        progress_percent=100,
        error=error[:600],
        completed_at=now,
    )
    update_video(video_id, status="failed")


def insert_clip(values: dict[str, Any]) -> None:
    now = utc_now()
    payload = {
        "scene_index": None,
        "transcript": None,
        "has_speech": 0,
        "speech_coverage": 0.0,
        "speaker_count": 0,
        "speaker_bucket": "0",
        "face_axis": "unknown",
        "embedding_status": "pending",
        "embedding_updated_at": now,
        "tags_json": "[]",
        "rejection_reasons_json": "[]",
        "exportable": 1,
        "created_at": now,
        "updated_at": now,
        **values,
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO clips (
              id, video_id, scene_index, clip_path, thumbnail_path, start_time, end_time,
              duration, quality, quality_score, speech_score, face_score,
              audio_score, has_speech, speech_coverage, speaker_count, speaker_bucket,
              face_axis, embedding_status, embedding_updated_at, transcript, tags_json,
              rejection_reasons_json, exportable, created_at, updated_at
            )
            VALUES (
              :id, :video_id, :scene_index, :clip_path, :thumbnail_path, :start_time,
              :end_time, :duration, :quality, :quality_score, :speech_score,
              :face_score, :audio_score, :has_speech, :speech_coverage, :speaker_count,
              :speaker_bucket, :face_axis, :embedding_status, :embedding_updated_at,
              :transcript, :tags_json, :rejection_reasons_json, :exportable,
              :created_at, :updated_at
            )
            """,
            payload,
        )


def delete_clips_for_video(video_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM clips WHERE video_id = ?", (video_id,))


def get_clip(clip_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT clips.*, videos.title AS source_video_title
            FROM clips
            JOIN videos ON videos.id = clips.video_id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
        return _row_to_dict(row)


def get_clips_for_video(video_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT clips.*, videos.title AS source_video_title
            FROM clips
            JOIN videos ON videos.id = clips.video_id
            WHERE clips.video_id = ?
            ORDER BY clips.start_time ASC
            """,
            (video_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def refresh_video_counts(video_id: str) -> None:
    with get_connection() as connection:
        counts = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM clips
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
        connection.execute(
            """
            UPDATE jobs
            SET clips_found = COALESCE(?, 0), updated_at = ?
            WHERE video_id = ? AND status != 'failed'
            """,
            (counts["total"], utc_now(), video_id),
        )


def _clip_has_transcript(clip: dict[str, Any]) -> bool:
    text = clip.get("transcript")
    return bool(text and str(text).strip())


def search_clips(
    query: str = "",
    duration: str = "any",
    speaker: str = "any",
    face_axis: str = "any",
    speech: str = "any",
    transcript: str = "any",
    semantic_clip_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    duration = {
        "<1": "lt1",
        "<5": "lt5",
        "<10": "lt10",
        "10+": "gte10",
    }.get(duration, duration)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT clips.*, videos.title AS source_video_title
            FROM clips
            JOIN videos ON videos.id = clips.video_id
            ORDER BY datetime(clips.created_at) DESC
            """
        ).fetchall()

    normalized_query = query.strip().lower()
    results: list[dict[str, Any]] = []
    for row in rows:
        clip = dict(row)
        tags = _json_list(clip.get("tags_json"))
        reasons = _json_list(clip.get("rejection_reasons_json"))
        haystack = " ".join(
            [
                clip.get("source_video_title") or "",
                clip.get("transcript") or "",
                " ".join(tags),
                " ".join(reasons),
            ]
        ).lower()

        if semantic_clip_ids is None and normalized_query and normalized_query not in haystack:
            continue
        if duration == "lt1" and float(clip["duration"]) >= 1:
            continue
        if duration == "lt5" and float(clip["duration"]) >= 5:
            continue
        if duration == "lt10" and float(clip["duration"]) >= 10:
            continue
        if duration == "gte10" and float(clip["duration"]) < 10:
            continue
        if speaker not in {"any", "all", ""} and str(clip.get("speaker_bucket") or "0") != speaker:
            continue
        if face_axis not in {"any", "all", ""} and str(clip.get("face_axis") or "unknown") != face_axis:
            continue
        if speech == "detected" and not bool(clip.get("has_speech")):
            continue
        if speech == "none" and bool(clip.get("has_speech")):
            continue
        transcript_mode = (transcript or "any").lower()
        if transcript_mode == "has" and not _clip_has_transcript(clip):
            continue
        if transcript_mode == "none" and _clip_has_transcript(clip):
            continue
        if semantic_clip_ids is not None and clip["id"] not in semantic_clip_ids:
            continue

        results.append(clip)
    if semantic_clip_ids is not None:
        order = {clip_id: index for index, clip_id in enumerate(semantic_clip_ids)}
        results.sort(key=lambda clip: order.get(clip["id"], 999999))
    return results


def all_clips_for_embedding() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM clips
            WHERE clip_path IS NOT NULL
            ORDER BY datetime(created_at) ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def pending_embedding_video_ids(limit: int = 1) -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT video_id
            FROM clips
            WHERE embedding_status IN ('pending', 'failed')
            ORDER BY datetime(created_at) ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [str(row["video_id"]) for row in rows]


def update_video_embedding_status(video_id: str, status: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE clips
            SET embedding_status = ?, embedding_updated_at = ?, updated_at = ?
            WHERE video_id = ?
            """,
            (status, utc_now(), utc_now(), video_id),
        )


def update_clip_embedding_status(clip_ids: list[str], status: str) -> None:
    if not clip_ids:
        return
    placeholders = ",".join("?" for _ in clip_ids)
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE clips
            SET embedding_status = ?, embedding_updated_at = ?, updated_at = ?
            WHERE id IN ({placeholders})
            """,
            [status, now, now, *clip_ids],
        )


def create_export(values: dict[str, Any]) -> None:
    payload = {"created_at": utc_now(), **values}
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO exports (id, mode, query, filters_json, export_path, status, created_at)
            VALUES (:id, :mode, :query, :filters_json, :export_path, :status, :created_at)
            """,
            payload,
        )


def list_expired_exports(cutoff_iso: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM exports WHERE datetime(created_at) < datetime(?)",
            (cutoff_iso,),
        ).fetchall()
        return [dict(row) for row in rows]


def delete_export(export_id: str) -> None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT export_path FROM exports WHERE id = ?", (export_id,)
        ).fetchone()
        if row:
            remove_path(row["export_path"])
        connection.execute("DELETE FROM exports WHERE id = ?", (export_id,))


def old_failed_videos(cutoff_iso: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM videos
            WHERE status = 'failed'
              AND is_example = 0
              AND datetime(created_at) < datetime(?)
            """,
            (cutoff_iso,),
        ).fetchall()
        return [dict(row) for row in rows]


def non_example_videos_oldest_first() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM videos
            WHERE is_example = 0
            ORDER BY datetime(created_at) ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def delete_video(video_id: str) -> None:
    remove_video_files(video_id)
    with get_connection() as connection:
        connection.execute("DELETE FROM videos WHERE id = ?", (video_id,))


def video_response(row: dict[str, Any]) -> dict[str, Any]:
    counts = _clip_counts(row["id"])
    job = _latest_job(row["id"])
    width = row.get("width")
    height = row.get("height")
    return {
        "id": row["id"],
        "title": row["title"],
        "filename": row["filename"],
        "sourceType": row["source_type"],
        "status": row["status"],
        "progressStage": job.get("progress_stage") if job else row["status"],
        "progressPercent": job.get("progress_percent") if job else None,
        "thumbnailUrl": media_url(row.get("thumbnail_path")),
        "videoUrl": media_url(row.get("raw_path")),
        "durationSeconds": row.get("duration_seconds"),
        "fileSizeMb": row.get("file_size_mb"),
        "resolution": f"{width}x{height}" if width and height else None,
        "fps": row.get("fps"),
        "clipsFound": counts["total"],
        "error": job.get("error") if job else None,
        "createdAt": row["created_at"],
    }


def video_detail_response(row: dict[str, Any]) -> dict[str, Any]:
    response = video_response(row)
    response["processingTimeSeconds"] = _processing_time_seconds(row["id"])
    return response


def job_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "videoId": row["video_id"],
        "status": row["status"],
        "progressStage": row["progress_stage"],
        "progressPercent": row["progress_percent"],
        "clipsFound": row["clips_found"],
        "error": row["error"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def clip_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "videoId": row["video_id"],
        "sourceVideoTitle": row["source_video_title"],
        "clipUrl": media_url(row.get("clip_path")),
        "thumbnailUrl": media_url(row.get("thumbnail_path")),
        "sceneIndex": row.get("scene_index"),
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "duration": row["duration"],
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
        "semanticScore": row.get("semantic_score"),
        "bestFrameUrl": row.get("best_frame_url") or media_url(row.get("best_frame_path")),
        "bestFrameTimeSeconds": row.get("best_frame_time_seconds"),
        "transcript": row["transcript"],
        "tags": _json_list(row.get("tags_json")),
        "rejectionReasons": _json_list(row.get("rejection_reasons_json")),
        "exportable": bool(row["exportable"]),
    }


def clip_export_record(row: dict[str, Any]) -> dict[str, Any]:
    response = clip_response(row)
    response["clipPath"] = row.get("clip_path")
    response["thumbnailPath"] = row.get("thumbnail_path")
    return response


def _clip_counts(video_id: str) -> dict[str, int]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM clips
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
    return {"total": int(row["total"] or 0)}


def _latest_job(video_id: str) -> dict[str, Any] | None:
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
        return _row_to_dict(row)


def _processing_time_seconds(video_id: str) -> int | None:
    job = _latest_job(video_id)
    if not job or not job.get("started_at") or not job.get("completed_at"):
        return None
    with get_connection() as connection:
        row = connection.execute(
            "SELECT CAST((julianday(?) - julianday(?)) * 86400 AS INTEGER) AS seconds",
            (job["completed_at"], job["started_at"]),
        ).fetchone()
        return int(row["seconds"] or 0)


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


def paths_exist(paths: Iterable[str | None]) -> list[Path]:
    existing: list[Path] = []
    for path in paths:
        if path and Path(path).exists():
            existing.append(Path(path))
    return existing
