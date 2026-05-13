from __future__ import annotations

import shutil
from pathlib import Path

from app.config import settings


def ensure_data_dirs() -> None:
    for path in [
        settings.db_path.parent,
        settings.raw_dir,
        settings.normalized_dir,
        settings.clips_dir,
        settings.thumbnails_dir,
        settings.exports_dir,
        settings.debug_dir,
        settings.tmp_dir,
        settings.logs_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def safe_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    return name or "video"


def media_url(path: str | Path | None) -> str | None:
    if not path:
        return None

    file_path = Path(path)
    try:
        relative = file_path.relative_to(settings.storage_dir)
    except ValueError:
        return None
    return f"{settings.media_url_prefix}/{relative.as_posix()}"


def assert_within_data_dir(path: Path) -> Path:
    resolved = path.resolve()
    data_root = settings.data_dir.resolve()
    if resolved != data_root and data_root not in resolved.parents:
        raise ValueError(f"Refusing to operate outside data dir: {resolved}")
    return resolved


def remove_path(path: str | Path | None) -> None:
    if not path:
        return
    target = assert_within_data_dir(Path(path))
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    elif target.exists():
        target.unlink(missing_ok=True)


def remove_video_files(video_id: str) -> None:
    for base in [
        settings.raw_dir,
        settings.normalized_dir,
        settings.clips_dir,
        settings.thumbnails_dir,
        settings.debug_dir,
    ]:
        remove_path(base / video_id)
