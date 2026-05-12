from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db import queries
from app.utils.files import assert_within_data_dir

logger = logging.getLogger(__name__)


def run_cleanup() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    export_cutoff = (now - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    failed_cutoff = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")

    for export in queries.list_expired_exports(export_cutoff):
        queries.delete_export(export["id"])
        logger.info("cleanup_deleted_export export_id=%s", export["id"])

    for video in queries.old_failed_videos(failed_cutoff):
        queries.delete_video(video["id"])
        logger.info("cleanup_deleted_video video_id=%s reason=failed_old", video["id"])

    non_examples = queries.non_example_videos_oldest_first()
    overflow = max(0, len(non_examples) - settings.max_non_example_videos)
    for video in non_examples[:overflow]:
        queries.delete_video(video["id"])
        logger.info("cleanup_deleted_video video_id=%s reason=cap", video["id"])

    _cleanup_tmp_dirs(hours=6)


def _cleanup_tmp_dirs(*, hours: int) -> None:
    cutoff = datetime.now(UTC).timestamp() - hours * 3600
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    for child in settings.tmp_dir.iterdir():
        target = assert_within_data_dir(child)
        try:
            if target.stat().st_mtime < cutoff:
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
