from __future__ import annotations

from pathlib import Path

from app.utils.ffmpeg import run_command


def normalize_video(input_path: str | Path, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            "scale='min(1280,iw)':-2,fps=15",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output),
        ],
        timeout=900,
    )
    return output
