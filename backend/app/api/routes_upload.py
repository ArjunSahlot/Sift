from __future__ import annotations

import logging
from pathlib import Path

import yt_dlp
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

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
        logger.exception("Unexpected error during upload for video_id=%s: %s", video_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed while validating video.",
        ) from exc


def _download_youtube(url: str, output_path: Path) -> dict:
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "max_filesize": settings.max_upload_bytes,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if info is None:
            raise ValueError("Could not extract video info.")
        duration = info.get("duration", 0)
        if duration > settings.max_duration_seconds:
            raise ValueError("Video exceeds 5 minute demo limit.")
        
        ydl.download([url])
        return info

@router.post("/youtube", status_code=status.HTTP_201_CREATED)
async def upload_youtube(
    url: str = Form(...),
    sourceType: str = Form(default="youtube"),
) -> dict[str, str]:
    if queries.queued_job_count() >= settings.max_queue_size:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload queue is full. Try again shortly.",
        )

    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube URL.",
        )

    video_id = new_id("video")
    job_id = new_id("job")
    raw_dir = settings.raw_dir / video_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "original.mp4"

    try:
        info = await run_in_threadpool(_download_youtube, url, raw_path)
        
        metadata = probe_video(raw_path)
        title = info.get("title", "YouTube Video")

        queries.create_video(
            {
                "id": video_id,
                "title": title,
                "filename": safe_filename(f"{title}.mp4"),
                "source_type": sourceType if sourceType in {"upload", "youtube", "example"} else "youtube",
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
    except yt_dlp.utils.DownloadError as exc:
        remove_video_files(video_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"YouTube download failed: {str(exc)}",
        ) from exc
    except ValueError as exc:
        remove_video_files(video_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        remove_video_files(video_id)
        logger.exception("Unexpected error during youtube download for video_id=%s: %s", video_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="YouTube download failed.",
        ) from exc
