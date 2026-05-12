from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _origins(value: str | None) -> list[str]:
    if not value:
        return [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:3002",
        ]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    storage_dir: Path
    raw_dir: Path
    normalized_dir: Path
    clips_dir: Path
    thumbnails_dir: Path
    exports_dir: Path
    tmp_dir: Path
    logs_dir: Path
    media_url_prefix: str
    max_upload_mb: int
    max_upload_bytes: int
    max_duration_seconds: int
    max_queue_size: int
    max_processing_concurrency: int
    max_clips_per_video: int
    max_clip_duration_seconds: int
    max_non_example_videos: int
    cors_origins: list[str]
    allowed_extensions: set[str]


def load_settings() -> Settings:
    _load_dotenv()

    data_dir = Path(BACKEND_DIR / "local_data")
    storage_dir = data_dir / "storage"
    max_upload_mb = _int_env("SIFT_MAX_UPLOAD_MB", 250)

    return Settings(
        data_dir=data_dir,
        db_path=data_dir / "data" / "sift.db",
        storage_dir=storage_dir,
        raw_dir=storage_dir / "raw",
        normalized_dir=storage_dir / "normalized",
        clips_dir=storage_dir / "clips",
        thumbnails_dir=storage_dir / "thumbnails",
        exports_dir=storage_dir / "exports",
        tmp_dir=data_dir / "tmp",
        logs_dir=data_dir / "logs",
        media_url_prefix="/media",
        max_upload_mb=max_upload_mb,
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        max_duration_seconds=_int_env("SIFT_MAX_DURATION_SECONDS", 300),
        max_queue_size=_int_env("SIFT_MAX_QUEUE_SIZE", 5),
        max_processing_concurrency=1,
        max_clips_per_video=30,
        max_clip_duration_seconds=20,
        max_non_example_videos=_int_env("SIFT_MAX_NON_EXAMPLE_VIDEOS", 40),
        cors_origins=_origins(os.environ.get("SIFT_CORS_ORIGINS")),
        allowed_extensions={".mp4", ".mov", ".webm", ".mkv"},
    )


settings = load_settings()
