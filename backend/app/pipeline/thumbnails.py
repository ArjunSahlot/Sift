from __future__ import annotations

from pathlib import Path

from app.utils.ffmpeg import run_command


def generate_thumbnail(
    input_path: str | Path,
    output_path: str | Path,
    *,
    seek_seconds: float,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(0.0, seek_seconds):.3f}",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output),
        ],
        timeout=120,
    )
    return output


def generate_cover_thumbnail(
    input_path: str | Path,
    output_path: str | Path,
    *,
    duration_seconds: float,
) -> Path:
    seek = min(max(duration_seconds * 0.25, 1.0), 5.0)
    return generate_thumbnail(input_path, output_path, seek_seconds=seek)
