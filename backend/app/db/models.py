from __future__ import annotations

JOB_STATUSES = {"queued", "processing", "complete", "failed"}
VIDEO_STATUSES = {"queued", "uploading", "processing", "complete", "failed"}
CLIP_QUALITIES = {"good", "review", "rejected"}

PROGRESS_PERCENT = {
    "queued": 0,
    "validating": 5,
    "probing_video": 10,
    "normalizing": 20,
    "extracting_audio": 30,
    "detecting_scenes": 38,
    "detecting_speech": 45,
    "extracting_clips": 55,
    "generating_thumbnails": 65,
    "running_face_detection": 74,
    "scoring_quality": 85,
    "transcribing": 92,
    "saving_results": 97,
    "complete": 100,
    "failed": 100,
}
