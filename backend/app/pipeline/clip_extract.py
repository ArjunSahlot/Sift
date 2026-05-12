from __future__ import annotations

from pathlib import Path

from app.utils.ffmpeg import run_command


def extract_clip(
    input_path: str | Path,
    output_path: str | Path,
    *,
    start_time: float,
    end_time: float,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, end_time - start_time)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-i",
            str(input_path),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            str(output),
        ],
        timeout=300,
    )
    return output
