from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _env_opt_str(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _get_model() -> WhisperModel:
    """Load faster-whisper once per process; clips in one job reuse the same model."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel as FWWhisperModel

        model_id = _env_str("SIFT_WHISPER_MODEL", "base")
        device = _env_str("SIFT_WHISPER_DEVICE", "auto")
        download_root = _env_opt_str("SIFT_WHISPER_DOWNLOAD_ROOT")

        compute_type = _env_opt_str("SIFT_WHISPER_COMPUTE_TYPE")
        if not compute_type:
            compute_type = "float16" if device == "cuda" else "default"

        kwargs: dict = {
            "device": device,
            "compute_type": compute_type,
        }
        if download_root is not None:
            kwargs["download_root"] = download_root

        logger.info(
            "whisper_model_loading model=%s device=%s compute_type=%s",
            model_id,
            device,
            compute_type,
        )
        _model = FWWhisperModel(model_id, **kwargs)
        return _model


def transcribe_clip(clip_path: str | Path) -> str | None:
    """
    Return plain text for the clip's speech, or None if transcription fails or is empty.

    Configure via environment (optional):
    - SIFT_WHISPER_MODEL: HuggingFace model id or local path (default: base)
    - SIFT_WHISPER_DEVICE: auto | cpu | cuda (default: auto)
    - SIFT_WHISPER_COMPUTE_TYPE: e.g. float16, int8_float32 (default: float16 on cuda, else default)
    - SIFT_WHISPER_LANGUAGE: ISO code or unset for auto-detect
    - SIFT_WHISPER_DOWNLOAD_ROOT: cache directory for model weights
    """
    path = Path(clip_path)
    if not path.is_file():
        logger.warning("transcribe_skip_missing path=%s", path)
        return None

    language = _env_opt_str("SIFT_WHISPER_LANGUAGE")

    try:
        model = _get_model()
        segments_iter, _info = model.transcribe(
            str(path),
            language=language,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            without_timestamps=True,
            log_progress=False,
        )
        parts: list[str] = []
        for segment in segments_iter:
            text = (segment.text or "").strip()
            if text:
                parts.append(text)
        joined = " ".join(parts).strip()
        if not joined:
            return None
        return joined
    except Exception:
        logger.exception("transcribe_failed path=%s", path)
        return None
