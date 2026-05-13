from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipeline.probe import probe_video


def detect_scenes(
    video_path: str | Path,
    *,
    threshold: float = 27.0,
) -> list[dict[str, Any]]:
    path = Path(video_path)
    duration = float(probe_video(path)["duration_seconds"] or 0)
    if duration <= 0:
        return []

    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector

        video = open_video(str(path))
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))
        scene_manager.detect_scenes(video)
        scenes = scene_manager.get_scene_list()
        detected = [
            {
                "scene_index": index,
                "start_seconds": float(start.get_seconds()),
                "end_seconds": float(end.get_seconds()),
                "start_timecode": start.get_timecode(),
                "end_timecode": end.get_timecode(),
                "duration_seconds": float(end.get_seconds() - start.get_seconds()),
                "source": "scenedetect",
            }
            for index, (start, end) in enumerate(scenes)
        ]
    except Exception:  # noqa: BLE001
        detected = []

    return _cover_full_video(detected, duration)


def _cover_full_video(
    scenes: list[dict[str, Any]],
    duration: float,
) -> list[dict[str, Any]]:
    valid = [
        {
            **scene,
            "start_seconds": max(0.0, float(scene["start_seconds"])),
            "end_seconds": min(duration, float(scene["end_seconds"])),
        }
        for scene in scenes
        if float(scene.get("end_seconds") or 0) > float(scene.get("start_seconds") or 0)
    ]
    valid.sort(key=lambda scene: scene["start_seconds"])

    covered: list[dict[str, Any]] = []
    cursor = 0.0
    for scene in valid:
        start = scene["start_seconds"]
        end = scene["end_seconds"]
        if start > cursor + 0.05:
            covered.append(_scene_record(cursor, start, "gap_fill"))
        if end > cursor + 0.05:
            covered.append(_scene_record(max(start, cursor), end, scene.get("source", "scenedetect")))
            cursor = end

    if cursor < duration - 0.05:
        covered.append(_scene_record(cursor, duration, "tail_fill"))

    if not covered:
        covered = [_scene_record(0.0, duration, "full_video_fallback")]

    for index, scene in enumerate(covered):
        scene["scene_index"] = index
    return covered


def _scene_record(start: float, end: float, source: str) -> dict[str, Any]:
    return {
        "scene_index": 0,
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "start_timecode": _timecode(start),
        "end_timecode": _timecode(end),
        "duration_seconds": round(max(0.0, end - start), 3),
        "source": source,
    }


def _timecode(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    minutes, second = divmod(whole, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d}.{millis:03d}"
