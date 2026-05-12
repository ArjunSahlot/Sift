from __future__ import annotations

import logging
import time

from app.db import queries
from app.db.init import init_db
from app.pipeline.process_video import process_video_job
from app.utils.cleanup import run_cleanup
from app.utils.files import ensure_data_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def run_worker() -> None:
    ensure_data_dirs()
    init_db()
    logger.info("sift_worker_started")

    while True:
        job = queries.claim_next_queued_job()
        if job is None:
            time.sleep(2)
            continue

        try:
            process_video_job(job)
            run_cleanup()
        except Exception as exc:
            logger.exception("job_failed job_id=%s", job["id"])
            queries.mark_job_failed(job["id"], job["video_id"], _readable_error(exc))


def _readable_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message if message else exc.__class__.__name__


if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        logger.info("sift_worker_stopped")
