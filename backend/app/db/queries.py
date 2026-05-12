from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from sqlite3 import Row
from typing import Any

from app.db.models import CLIP_QUALITIES, PROGRESS_PERCENT
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
        "transcript": None,
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
              id, video_id, clip_path, thumbnail_path, start_time, end_time,
              duration, quality, quality_score, speech_score, face_score,
              audio_score, transcript, tags_json, rejection_reasons_json,
              exportable, created_at, updated_at
            )
            VALUES (
              :id, :video_id, :clip_path, :thumbnail_path, :start_time,
              :end_time, :duration, :quality, :quality_score, :speech_score,
              :face_score, :audio_score, :transcript, :tags_json,
              :rejection_reasons_json, :exportable, :created_at, :updated_at
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


def get_clips_for_video(video_id: str, quality: str = "all") -> list[dict[str, Any]]:
    params: list[Any] = [video_id]
    where = "clips.video_id = ?"
    if quality != "all":
        where += " AND clips.quality = ?"
        params.append(quality)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT clips.*, videos.title AS source_video_title
            FROM clips
            JOIN videos ON videos.id = clips.video_id
            WHERE {where}
            ORDER BY clips.start_time ASC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def update_clip_quality(clip_id: str, quality: str) -> dict[str, Any] | None:
    if quality not in CLIP_QUALITIES:
        raise ValueError("Invalid clip quality.")
    now = utc_now()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT video_id FROM clips WHERE id = ?", (clip_id,)
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            """
            UPDATE clips
            SET quality = ?, exportable = ?, updated_at = ?
            WHERE id = ?
            """,
            (quality, 0 if quality == "rejected" else 1, now, clip_id),
        )
    refresh_video_counts(row["video_id"])
    return get_clip(clip_id)


def refresh_video_counts(video_id: str) -> None:
    with get_connection() as connection:
        counts = connection.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN quality = 'good' THEN 1 ELSE 0 END) AS good,
              SUM(CASE WHEN quality = 'review' THEN 1 ELSE 0 END) AS review,
              SUM(CASE WHEN quality = 'rejected' THEN 1 ELSE 0 END) AS rejected
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


def search_clips(
    query: str = "",
    quality: str = "any",
    clip_type: str = "any",
    duration: str = "any",
) -> list[dict[str, Any]]:
    quality = quality.replace("-", "_")
    clip_type = clip_type.replace("-", "_")
    duration = {
        "short": "lt10",
        "medium": "10to20",
        "long": "gt20",
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
                clip.get("quality") or "",
                " ".join(tags),
                " ".join(reasons),
            ]
        ).lower()

        if normalized_query and normalized_query not in haystack:
            continue
        if quality not in {"any", "all", ""} and clip["quality"] != quality:
            continue
        if clip_type not in {"any", "all", ""}:
            if clip_type in {"speaking", "human_speaking"} and "human-speaking" not in tags:
                continue
            if clip_type == "human_visible" and "face-visible" not in tags:
                continue
            if clip_type == "clean_audio" and "clean-audio" not in tags:
                continue
            if clip_type == "single_speaker" and not any(
                tag.startswith("single-speaker") for tag in tags
            ):
                continue
        if duration == "lt10" and float(clip["duration"]) >= 10:
            continue
        if duration == "10to20" and not (10 <= float(clip["duration"]) <= 20):
            continue
        if duration == "gt20" and float(clip["duration"]) <= 20:
            continue

        results.append(clip)
    return results


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
        "goodClips": counts["good"],
        "reviewClips": counts["review"],
        "rejectedClips": counts["rejected"],
        "createdAt": row["created_at"],
    }


def video_detail_response(row: dict[str, Any]) -> dict[str, Any]:
    response = video_response(row)
    response["processingTimeSeconds"] = _processing_time_seconds(row["id"])
    response["mostCommonRejectionReason"] = _most_common_rejection_reason(row["id"])
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
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "duration": row["duration"],
        "quality": row["quality"],
        "qualityScore": row["quality_score"],
        "speechScore": row["speech_score"],
        "faceScore": row["face_score"],
        "audioScore": row["audio_score"],
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
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN quality = 'good' THEN 1 ELSE 0 END) AS good,
              SUM(CASE WHEN quality = 'review' THEN 1 ELSE 0 END) AS review,
              SUM(CASE WHEN quality = 'rejected' THEN 1 ELSE 0 END) AS rejected
            FROM clips
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "good": int(row["good"] or 0),
        "review": int(row["review"] or 0),
        "rejected": int(row["rejected"] or 0),
    }


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


def _most_common_rejection_reason(video_id: str) -> str | None:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT rejection_reasons_json FROM clips WHERE video_id = ?",
            (video_id,),
        ).fetchall()
    reasons: list[str] = []
    for row in rows:
        reasons.extend(_json_list(row["rejection_reasons_json"]))
    if not reasons:
        return None
    return Counter(reasons).most_common(1)[0][0]


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
