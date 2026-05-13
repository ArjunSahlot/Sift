from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.config import settings
from app.db import queries
from app.pipeline import debug_artifacts
from app.pipeline.audio import extract_audio, score_clip_audio
from app.pipeline.clip_extract import extract_clip
from app.pipeline.face_detect import score_faces
from app.pipeline.normalize import normalize_video
from app.pipeline.probe import probe_video
from app.pipeline.quality import classify_clip
from app.pipeline.scenes import detect_scenes
from app.pipeline.thumbnails import generate_cover_thumbnail, generate_thumbnail
from app.pipeline.transcribe import transcribe_clip
from app.pipeline.vad import analyze_speech_segments, speech_coverage_for_range
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
    current_stage: str | None = None

    def begin_stage(stage: str, inputs: dict[str, Any] | None = None) -> None:
        nonlocal current_stage
        current_stage = stage
        queries.set_stage(job_id, video_id, stage)
        _debug(debug_artifacts.start_stage, video_id, job_id, stage, inputs=inputs)

    try:
        _debug(debug_artifacts.reset_video_debug, video_id, job_id)
        logger.info("job_started job_id=%s video_id=%s", job_id, video_id)

        begin_stage("probing_video", {"raw": _file_snapshot(raw_path)})
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
        _debug(debug_artifacts.complete_stage, video_id, job_id, "probing_video", outputs={"metadata": metadata})

        begin_stage(
            "normalizing",
            {
                "raw": _file_snapshot(raw_path),
                "target": "scale to <=1280px wide, 15 fps, mono AAC @ 16 kHz",
            },
        )
        normalized_path = settings.normalized_dir / video_id / "normalized.mp4"
        normalize_video(raw_path, normalized_path)
        normalized_metadata = probe_video(normalized_path)
        queries.update_video(video_id, normalized_path=str(normalized_path))
        cover_path = settings.thumbnails_dir / video_id / "cover.jpg"
        generate_cover_thumbnail(normalized_path, cover_path, duration_seconds=float(normalized_metadata["duration_seconds"]))
        queries.update_video(video_id, thumbnail_path=str(cover_path))
        _debug(
            debug_artifacts.complete_stage,
            video_id,
            job_id,
            "normalizing",
            outputs={"normalized": _file_snapshot(normalized_path), "coverThumbnail": _file_snapshot(cover_path)},
        )

        begin_stage("extracting_audio", {"normalized": _file_snapshot(normalized_path)})
        audio_path = tmp_dir / "audio.wav"
        extract_audio(normalized_path, audio_path)
        _debug(debug_artifacts.complete_stage, video_id, job_id, "extracting_audio", outputs={"audio": _file_snapshot(audio_path)})

        begin_stage("detecting_scenes", {"normalized": _file_snapshot(normalized_path), "threshold": 27.0})
        scenes = detect_scenes(normalized_path)
        if not scenes:
            raise ValueError("No scenes detected.")
        _assert_full_coverage(scenes, float(normalized_metadata["duration_seconds"]))
        _debug(debug_artifacts.complete_stage, video_id, job_id, "detecting_scenes", outputs={"scenes": scenes})

        begin_stage(
            "detecting_speech",
            {
                "audio": _file_snapshot(audio_path),
                "method": "silero_vad_onnx_with_energy_fallback",
                "note": "Speech is metadata on scene clips; it no longer determines clip boundaries.",
            },
        )
        speech_debug = analyze_speech_segments(audio_path, min_segment_seconds=0.25, max_segment_seconds=600, max_segments=500)
        speech_segments = speech_debug["segments"]
        _debug(debug_artifacts.complete_stage, video_id, job_id, "detecting_speech", outputs=speech_debug)

        queries.delete_clips_for_video(video_id)
        shutil.rmtree(settings.clips_dir / video_id, ignore_errors=True)
        shutil.rmtree(settings.thumbnails_dir / video_id, ignore_errors=True)
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        generate_cover_thumbnail(normalized_path, cover_path, duration_seconds=float(normalized_metadata["duration_seconds"]))

        begin_stage("extracting_clips", {"normalized": _file_snapshot(normalized_path), "scenes": scenes})
        extracted: list[dict[str, Any]] = []
        for scene in scenes:
            clip_id = new_id("clip")
            clip_path = settings.clips_dir / video_id / f"{clip_id}.mp4"
            start = float(scene["start_seconds"])
            end = float(scene["end_seconds"])
            extract_clip(normalized_path, clip_path, start_time=start, end_time=end)
            speech = speech_coverage_for_range(speech_segments, start, end)
            record = {
                "id": clip_id,
                "index": int(scene["scene_index"]) + 1,
                "scene": scene,
                "path": clip_path,
                "start": start,
                "end": end,
                "duration": end - start,
                "speech": speech,
            }
            extracted.append(record)
            queries.update_job(job_id, clips_found=len(extracted))
            logger.info("clip_extracted job_id=%s clip_id=%s scene=%s", job_id, clip_id, scene["scene_index"])
            _debug(debug_artifacts.update_stage, video_id, job_id, "extracting_clips", status="running", outputs={"clips": [_clip_artifact(item) for item in extracted]})
        _debug(debug_artifacts.complete_stage, video_id, job_id, "extracting_clips", outputs={"clips": [_clip_artifact(item) for item in extracted]})

        begin_stage("generating_thumbnails", {"clipsCount": len(extracted)})
        for record in extracted:
            thumbnail_path = settings.thumbnails_dir / video_id / f"{record['id']}.jpg"
            generate_thumbnail(record["path"], thumbnail_path, seek_seconds=max(0.1, record["duration"] / 2))
            record["thumbnail_path"] = thumbnail_path
            _debug(debug_artifacts.update_stage, video_id, job_id, "generating_thumbnails", status="running", outputs={"clips": [_clip_artifact(item) for item in extracted]})
        _debug(debug_artifacts.complete_stage, video_id, job_id, "generating_thumbnails", outputs={"coverThumbnail": _file_snapshot(cover_path), "clips": [_clip_artifact(item) for item in extracted]})

        begin_stage("running_face_detection", {"clipsCount": len(extracted), "detector": "YuNet ONNX via OpenCV"})
        for record in extracted:
            record["face_stats"] = score_faces(record["path"], include_samples=True, absolute_start_time=float(record["start"]))
            _debug(debug_artifacts.update_stage, video_id, job_id, "running_face_detection", status="running", outputs={"clips": [_clip_artifact(item) for item in extracted]})
        _debug(debug_artifacts.complete_stage, video_id, job_id, "running_face_detection", outputs={"clips": [_clip_artifact(item) for item in extracted]})

        begin_stage("scoring_quality", {"thresholds": {"speechDetectedAt": 0.08, "faceVisibleAt": 0.2, "goodAt": 0.75}})
        for record in extracted:
            clip_audio_path = tmp_dir / f"{record['id']}.wav"
            audio_stats = score_clip_audio(record["path"], clip_audio_path)
            speech_score = float(record["speech"]["speech_coverage"])
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
            record["audio_stats"] = audio_stats
            record["speech_score"] = speech_score
            record["face_score"] = face_score
            record["audio_score"] = audio_score
            record["quality"] = quality
            _debug(debug_artifacts.update_stage, video_id, job_id, "scoring_quality", status="running", outputs={"clips": [_clip_artifact(item) for item in extracted]})
        _debug(debug_artifacts.complete_stage, video_id, job_id, "scoring_quality", outputs={"clips": [_clip_artifact(item) for item in extracted]})

        begin_stage("transcribing", {"eligibleClips": sum(1 for record in extracted if record["quality"]["quality"] in {"good", "review"})})
        for record in extracted:
            record["transcript"] = transcribe_clip(record["path"]) if record["quality"]["quality"] in {"good", "review"} else None
            _debug(debug_artifacts.update_stage, video_id, job_id, "transcribing", status="running", outputs={"clips": [_clip_artifact(item) for item in extracted]})
        _debug(debug_artifacts.complete_stage, video_id, job_id, "transcribing", outputs={"clips": [_clip_artifact(item) for item in extracted]})

        begin_stage("saving_results", {"clipRows": len(extracted), "embeddingStatus": "pending"})
        for record in extracted:
            quality = record["quality"]
            face_stats = record["face_stats"]
            queries.insert_clip(
                {
                    "id": record["id"],
                    "video_id": video_id,
                    "scene_index": int(record["scene"]["scene_index"]),
                    "clip_path": str(record["path"]),
                    "thumbnail_path": str(record["thumbnail_path"]),
                    "start_time": record["start"],
                    "end_time": record["end"],
                    "duration": record["duration"],
                    "quality": quality["quality"],
                    "quality_score": quality["quality_score"],
                    "speech_score": record["speech_score"],
                    "face_score": record["face_score"],
                    "audio_score": record["audio_score"],
                    "has_speech": 1 if record["speech"]["has_speech"] else 0,
                    "speech_coverage": record["speech"]["speech_coverage"],
                    "speaker_count": face_stats.get("speaker_count", 0),
                    "speaker_bucket": face_stats.get("speaker_bucket", "0"),
                    "face_axis": face_stats.get("face_axis", "unknown"),
                    "embedding_status": "pending",
                    "transcript": record["transcript"],
                    "tags_json": json.dumps(quality["tags"]),
                    "rejection_reasons_json": json.dumps(quality["rejection_reasons"]),
                    "exportable": 1 if quality["exportable"] else 0,
                }
            )

        queries.update_video(video_id, thumbnail_path=str(cover_path))
        _debug(debug_artifacts.complete_stage, video_id, job_id, "saving_results", outputs={"clipRowsWritten": len(extracted), "embeddingStatus": "pending"})
        queries.mark_job_complete(job_id, video_id)
        logger.info("job_completed job_id=%s video_id=%s", job_id, video_id)
    except Exception as exc:
        if current_stage:
            _debug(debug_artifacts.fail_stage, video_id, job_id, current_stage, str(exc))
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _assert_full_coverage(scenes: list[dict[str, Any]], duration: float) -> None:
    if not scenes:
        raise ValueError("Scene detection returned no coverage.")
    first = float(scenes[0]["start_seconds"])
    last = float(scenes[-1]["end_seconds"])
    if first > 0.1 or last < duration - 0.1:
        raise ValueError("Scene detection did not cover the full video.")
    for previous, current in zip(scenes, scenes[1:]):
        gap = float(current["start_seconds"]) - float(previous["end_seconds"])
        if abs(gap) > 0.1:
            raise ValueError("Scene coverage has a gap or overlap.")


def _debug(action: Any, *args: Any, **kwargs: Any) -> None:
    try:
        action(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("debug_artifact_failed action=%s error=%s", action, exc)


def _file_snapshot(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False, "sizeBytes": None}
    file_path = Path(path)
    exists = file_path.exists()
    return {"path": str(file_path), "exists": exists, "sizeBytes": file_path.stat().st_size if exists else None}


def _clip_artifact(record: dict[str, Any]) -> dict[str, Any]:
    quality = record.get("quality") or {}
    face_stats = record.get("face_stats") or {}
    audio_stats = record.get("audio_stats") or {}
    speech = record.get("speech") or {}
    return {
        "id": record["id"],
        "index": record.get("index"),
        "scene": record.get("scene"),
        "path": _file_snapshot(record.get("path")),
        "thumbnail": _file_snapshot(record.get("thumbnail_path")),
        "start": record.get("start"),
        "end": record.get("end"),
        "duration": record.get("duration"),
        "speech": speech,
        "hasSpeech": speech.get("has_speech"),
        "speechCoverage": speech.get("speech_coverage"),
        "faceStats": face_stats,
        "audioStats": audio_stats,
        "quality": quality.get("quality"),
        "qualityScore": quality.get("quality_score"),
        "speechScore": record.get("speech_score"),
        "faceScore": record.get("face_score"),
        "audioScore": record.get("audio_score"),
        "speakerCount": face_stats.get("speaker_count"),
        "speakerBucket": face_stats.get("speaker_bucket"),
        "faceAxis": face_stats.get("face_axis"),
        "tags": quality.get("tags") or [],
        "rejectionReasons": quality.get("rejection_reasons") or [],
        "exportable": quality.get("exportable"),
        "transcript": record.get("transcript"),
        "embeddingStatus": "pending",
    }
