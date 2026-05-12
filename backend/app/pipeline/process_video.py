from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from app.config import settings
from app.db import queries
from app.pipeline.audio import extract_audio, score_clip_audio
from app.pipeline.clip_extract import extract_clip
from app.pipeline.face_detect import score_faces
from app.pipeline.normalize import normalize_video
from app.pipeline.probe import probe_video
from app.pipeline.quality import classify_clip
from app.pipeline.thumbnails import generate_cover_thumbnail, generate_thumbnail
from app.pipeline.transcribe import transcribe_clip
from app.pipeline.vad import detect_speech_segments
from app.utils.ids import new_id

logger = logging.getLogger(__name__)


def process_video_job(job: dict) -> None:
    video = queries.get_video(job["video_id"])
    if video is None:
        raise ValueError("Video row not found.")

    job_id = job["id"]
    video_id = video["id"]
    raw_path = Path(video["raw_path"])
    tmp_dir = settings.tmp_dir / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("job_started job_id=%s video_id=%s", job_id, video_id)
        queries.set_stage(job_id, video_id, "probing_video")
        metadata = probe_video(raw_path)
        if metadata["duration_seconds"] > settings.max_duration_seconds:
            raise ValueError("Video exceeds 5 minute demo limit.")
        if not metadata["has_audio"]:
            raise ValueError("No audio stream found.")
        queries.update_video(
            video_id,
            duration_seconds=metadata["duration_seconds"],
            file_size_mb=metadata["file_size_mb"],
            width=metadata["width"],
            height=metadata["height"],
            fps=metadata["fps"],
        )

        queries.set_stage(job_id, video_id, "normalizing")
        normalized_path = settings.normalized_dir / video_id / "normalized.mp4"
        normalize_video(raw_path, normalized_path)
        queries.update_video(video_id, normalized_path=str(normalized_path))

        cover_path = settings.thumbnails_dir / video_id / "cover.jpg"
        generate_cover_thumbnail(
            normalized_path,
            cover_path,
            duration_seconds=float(metadata["duration_seconds"]),
        )
        queries.update_video(video_id, thumbnail_path=str(cover_path))

        queries.set_stage(job_id, video_id, "extracting_audio")
        audio_path = tmp_dir / "audio.wav"
        extract_audio(normalized_path, audio_path)

        queries.set_stage(job_id, video_id, "detecting_speech")
        segments = detect_speech_segments(
            audio_path,
            max_segment_seconds=settings.max_clip_duration_seconds,
            max_segments=settings.max_clips_per_video,
        )
        if not segments:
            raise ValueError("No speech detected.")

        queries.delete_clips_for_video(video_id)
        shutil.rmtree(settings.clips_dir / video_id, ignore_errors=True)
        shutil.rmtree(settings.thumbnails_dir / video_id, ignore_errors=True)
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        generate_cover_thumbnail(
            normalized_path,
            cover_path,
            duration_seconds=float(metadata["duration_seconds"]),
        )

        queries.set_stage(job_id, video_id, "extracting_clips")
        extracted: list[dict] = []
        for index, segment in enumerate(segments, start=1):
            clip_id = new_id("clip")
            clip_path = settings.clips_dir / video_id / f"{clip_id}.mp4"
            extract_clip(
                normalized_path,
                clip_path,
                start_time=segment["start"],
                end_time=segment["end"],
            )
            extracted.append(
                {
                    "id": clip_id,
                    "index": index,
                    "path": clip_path,
                    "start": segment["start"],
                    "end": segment["end"],
                    "duration": segment["end"] - segment["start"],
                }
            )
            queries.update_job(job_id, clips_found=len(extracted))
            logger.info("clip_extracted job_id=%s clip_id=%s", job_id, clip_id)

        queries.set_stage(job_id, video_id, "generating_thumbnails")
        for record in extracted:
            midpoint = max(0.1, record["duration"] / 2)
            thumbnail_path = settings.thumbnails_dir / video_id / f"{record['id']}.jpg"
            generate_thumbnail(record["path"], thumbnail_path, seek_seconds=midpoint)
            record["thumbnail_path"] = thumbnail_path

        queries.set_stage(job_id, video_id, "running_face_detection")
        for record in extracted:
            record["face_stats"] = score_faces(record["path"])

        queries.set_stage(job_id, video_id, "scoring_quality")
        for record in extracted:
            clip_audio_path = tmp_dir / f"{record['id']}.wav"
            audio_stats = score_clip_audio(record["path"], clip_audio_path)
            speech_score = max(0.0, min(1.0, 1.0 - audio_stats["silence_ratio"]))
            face_score = float(record["face_stats"]["face_score"])
            audio_score = float(audio_stats["audio_score"])
            quality = classify_clip(
                duration=record["duration"],
                speech_score=speech_score,
                face_score=face_score,
                audio_score=audio_score,
                face_stats=record["face_stats"],
                audio_stats=audio_stats,
            )
            transcript = (
                transcribe_clip(record["path"])
                if quality["quality"] in {"good", "review"}
                else None
            )
            queries.insert_clip(
                {
                    "id": record["id"],
                    "video_id": video_id,
                    "clip_path": str(record["path"]),
                    "thumbnail_path": str(record["thumbnail_path"]),
                    "start_time": record["start"],
                    "end_time": record["end"],
                    "duration": record["duration"],
                    "quality": quality["quality"],
                    "quality_score": quality["quality_score"],
                    "speech_score": speech_score,
                    "face_score": face_score,
                    "audio_score": audio_score,
                    "transcript": transcript,
                    "tags_json": json.dumps(quality["tags"]),
                    "rejection_reasons_json": json.dumps(quality["rejection_reasons"]),
                    "exportable": 1 if quality["exportable"] else 0,
                }
            )

        queries.set_stage(job_id, video_id, "saving_results")
        queries.update_video(video_id, thumbnail_path=str(cover_path))
        queries.mark_job_complete(job_id, video_id)
        logger.info("job_completed job_id=%s video_id=%s", job_id, video_id)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
