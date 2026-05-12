from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from app.utils.ffmpeg import ffprobe_json


def probe_video(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    data = ffprobe_json(file_path)
    streams = data.get("streams", [])
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    audio_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )

    if video_stream is None:
        raise ValueError("No video stream found.")

    duration = _float(data.get("format", {}).get("duration"))
    if not duration:
        duration = _float(video_stream.get("duration"))

    width = int(video_stream.get("width") or 0) or None
    height = int(video_stream.get("height") or 0) or None
    fps = _fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))

    return {
        "duration_seconds": duration or 0,
        "width": width,
        "height": height,
        "fps": fps,
        "file_size_mb": file_path.stat().st_size / 1024 / 1024,
        "has_audio": audio_stream is not None,
        "has_video": True,
    }


def _float(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fps(value: Any) -> float | None:
    if value in (None, "", "0/0", "N/A"):
        return None
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None
