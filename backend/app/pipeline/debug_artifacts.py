from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.config import settings
from app.utils.time import utc_now


SCHEMA_VERSION = 1


def reset_video_debug(video_id: str, job_id: str) -> None:
    root = _debug_root(video_id)
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    _write_payload(
        video_id,
        {
            "schemaVersion": SCHEMA_VERSION,
            "videoId": video_id,
            "jobId": job_id,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
            "stages": {},
        },
    )


def read_video_debug(video_id: str) -> dict[str, Any] | None:
    path = _payload_path(video_id)
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def start_stage(
    video_id: str,
    job_id: str,
    stage_id: str,
    *,
    inputs: dict[str, Any] | None = None,
) -> None:
    update_stage(
        video_id,
        job_id,
        stage_id,
        status="running",
        inputs=inputs,
        started=True,
    )


def complete_stage(
    video_id: str,
    job_id: str,
    stage_id: str,
    *,
    outputs: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
) -> None:
    update_stage(
        video_id,
        job_id,
        stage_id,
        status="complete",
        outputs=outputs,
        artifacts=artifacts,
        completed=True,
    )


def fail_stage(video_id: str, job_id: str, stage_id: str, error: str) -> None:
    update_stage(
        video_id,
        job_id,
        stage_id,
        status="failed",
        error=error[:600],
        completed=True,
    )


def update_stage(
    video_id: str,
    job_id: str,
    stage_id: str,
    *,
    status: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    error: str | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    payload = read_video_debug(video_id) or {
        "schemaVersion": SCHEMA_VERSION,
        "videoId": video_id,
        "jobId": job_id,
        "createdAt": utc_now(),
        "stages": {},
    }
    payload["jobId"] = job_id
    payload["updatedAt"] = utc_now()

    stages = payload.setdefault("stages", {})
    stage = stages.setdefault(stage_id, {"id": stage_id})
    if status:
        stage["status"] = status
    if started and "startedAt" not in stage:
        stage["startedAt"] = utc_now()
    if completed:
        stage["completedAt"] = utc_now()
    if inputs is not None:
        stage["inputs"] = _to_jsonable(inputs)
    if outputs is not None:
        stage["outputs"] = _to_jsonable(outputs)
    if artifacts is not None:
        stage["artifacts"] = _to_jsonable(artifacts)
    if error:
        stage["error"] = error

    _write_payload(video_id, payload)


def _debug_root(video_id: str) -> Path:
    return settings.debug_dir / video_id


def _payload_path(video_id: str) -> Path:
    return _debug_root(video_id) / "pipeline.json"


def _write_payload(video_id: str, payload: dict[str, Any]) -> None:
    path = _payload_path(video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(_to_jsonable(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            pass
    return str(value)
