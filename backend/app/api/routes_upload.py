from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.db import queries
from app.pipeline.probe import probe_video
from app.utils.cleanup import run_cleanup
from app.utils.files import remove_video_files, safe_extension, safe_filename
from app.utils.ids import new_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    sourceType: str = Form(default="upload"),
) -> dict[str, str]:
    if queries.queued_job_count() >= settings.max_queue_size:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload queue is full. Try again shortly.",
        )

    filename = safe_filename(file.filename or "upload")
    extension = safe_extension(filename)
    if extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    video_id = new_id("video")
    job_id = new_id("job")
    raw_dir = settings.raw_dir / video_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"original{extension}"

    size = 0
    try:
        with raw_path.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeds {settings.max_upload_mb} MB demo limit.",
                    )
                handle.write(chunk)

        metadata = probe_video(raw_path)
        if metadata["duration_seconds"] > settings.max_duration_seconds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video exceeds 5 minute demo limit.",
            )

        queries.create_video(
            {
                "id": video_id,
                "title": title.strip() if title else Path(filename).stem,
                "filename": filename,
                "source_type": sourceType if sourceType in {"upload", "youtube", "example"} else "upload",
                "status": "queued",
                "raw_path": str(raw_path),
                "normalized_path": None,
                "thumbnail_path": None,
                "duration_seconds": metadata["duration_seconds"],
                "file_size_mb": metadata["file_size_mb"],
                "width": metadata["width"],
                "height": metadata["height"],
                "fps": metadata["fps"],
                "is_example": 0,
            }
        )
        queries.create_job({"id": job_id, "video_id": video_id})
        run_cleanup()
        logger.info("job_created job_id=%s video_id=%s", job_id, video_id)
        return {"videoId": video_id, "jobId": job_id, "status": "queued"}
    except HTTPException:
        remove_video_files(video_id)
        raise
    except ValueError as exc:
        remove_video_files(video_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        remove_video_files(video_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed while validating video.",
        ) from exc
