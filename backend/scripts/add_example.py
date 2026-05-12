from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from app.config import settings
from app.db import queries
from app.db.init import init_db
from app.pipeline.probe import probe_video
from app.utils.files import ensure_data_dirs, safe_extension
from app.utils.ids import new_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Add an example video to Sift.")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    ensure_data_dirs()
    init_db()

    source = args.video_path.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Video does not exist: {source}")

    extension = safe_extension(source.name)
    if extension not in settings.allowed_extensions:
        raise SystemExit(f"Unsupported file type: {extension}")

    metadata = probe_video(source)
    if metadata["duration_seconds"] > settings.max_duration_seconds:
        raise SystemExit("Video exceeds 5 minute demo limit.")

    video_id = new_id("video")
    job_id = new_id("job")
    raw_dir = settings.raw_dir / video_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"original{extension}"
    shutil.copy2(source, raw_path)

    queries.create_video(
        {
            "id": video_id,
            "title": args.title,
            "filename": source.name,
            "source_type": "example",
            "status": "queued",
            "raw_path": str(raw_path),
            "normalized_path": None,
            "thumbnail_path": None,
            "duration_seconds": metadata["duration_seconds"],
            "file_size_mb": metadata["file_size_mb"],
            "width": metadata["width"],
            "height": metadata["height"],
            "fps": metadata["fps"],
            "is_example": 1,
        }
    )
    queries.create_job({"id": job_id, "video_id": video_id})
    print(f"Added example video: videoId={video_id} jobId={job_id}")


if __name__ == "__main__":
    main()
