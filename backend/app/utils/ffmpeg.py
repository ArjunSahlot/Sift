from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_command(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required binary not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip().splitlines()[-1:]
        detail = message[0] if message else str(exc)
        raise RuntimeError(f"{command[0]} failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{command[0]} timed out") from exc
    return result


def ffprobe_json(path: str | Path) -> dict:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=60,
    )
    return json.loads(result.stdout)
