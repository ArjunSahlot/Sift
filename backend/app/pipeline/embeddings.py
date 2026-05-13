from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.db import queries

logger = logging.getLogger(__name__)

MODEL_NAME = "clip-ViT-B-32"
INDEX_PATH = settings.index_dir / "frames.faiss"
METADATA_PATH = settings.index_dir / "metadata.jsonl"
_MODEL: Any | None = None
_THREAD_STARTED = False


def start_embedding_worker() -> None:
    global _THREAD_STARTED
    if _THREAD_STARTED:
        return
    _THREAD_STARTED = True
    thread = threading.Thread(target=_embedding_loop, name="sift_embedding_worker", daemon=True)
    thread.start()
    logger.info("embedding_worker_started")


def search_embeddings(query: str, *, top_k_frames: int = 50, top_k_clips: int = 25) -> list[dict[str, Any]]:
    if not query.strip() or not INDEX_PATH.exists() or not METADATA_PATH.exists():
        return []
    try:
        import faiss

        index = faiss.read_index(str(INDEX_PATH))
        metadata = _load_metadata(METADATA_PATH)
        model = _model()
        query_embedding = model.encode([query], convert_to_numpy=True)
        query_embedding = normalize_embeddings(query_embedding)
        scores, indices = index.search(query_embedding, top_k_frames)
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding_search_failed error=%s", exc)
        return []

    clip_matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score, index_value in zip(scores[0], indices[0]):
        if index_value < 0 or index_value >= len(metadata):
            continue
        record = metadata[index_value]
        clip_matches[str(record["clip_id"])].append(
            {
                "score": float(score),
                "clipId": record["clip_id"],
                "frameUrl": _media_url(record.get("frame_path")),
                "frameTimeSeconds": record.get("frame_time_seconds"),
            }
        )

    ranked = []
    for clip_id, matches in clip_matches.items():
        matches.sort(key=lambda item: item["score"], reverse=True)
        ranked.append(
            {
                "clipId": clip_id,
                "semanticScore": matches[0]["score"],
                "bestFrameUrl": matches[0].get("frameUrl"),
                "bestFrameTimeSeconds": matches[0].get("frameTimeSeconds"),
                "matchingFrames": matches[:3],
            }
        )
    ranked.sort(key=lambda item: item["semanticScore"], reverse=True)
    return ranked[:top_k_clips]


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    embeddings = embeddings.astype("float32")
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return embeddings / norms


def _embedding_loop() -> None:
    while True:
        try:
            video_ids = queries.pending_embedding_video_ids(limit=1)
            if not video_ids:
                time.sleep(3)
                continue
            build_embedding_index(video_ids[0])
        except Exception as exc:  # noqa: BLE001
            logger.exception("embedding_worker_iteration_failed error=%s", exc)
            time.sleep(5)


def build_embedding_index(video_id: str | None = None) -> None:
    target_ids = [video_id] if video_id else []
    if video_id:
        queries.update_video_embedding_status(video_id, "indexing")

    records: list[dict[str, Any]] = []
    clips = queries.all_clips_for_embedding()
    for clip in clips:
        clip_path = Path(clip["clip_path"])
        if not clip_path.exists():
            continue
        records.extend(_sample_frames(clip))

    if not records:
        if video_id:
            queries.update_video_embedding_status(video_id, "failed")
        return

    try:
        from PIL import Image
        import faiss

        model = _model()
        images = [Image.open(record["frame_path"]).convert("RGB") for record in records]
        embeddings = model.encode(
            images,
            batch_size=16,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        embeddings = normalize_embeddings(embeddings)
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        settings.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(INDEX_PATH))
        with METADATA_PATH.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

        indexed_clip_ids = sorted({str(record["clip_id"]) for record in records})
        queries.update_clip_embedding_status(indexed_clip_ids, "complete")
        if video_id:
            queries.update_video_embedding_status(video_id, "complete")
        logger.info("embedding_index_built clips=%s frames=%s target=%s", len(indexed_clip_ids), len(records), target_ids)
    except Exception as exc:  # noqa: BLE001
        logger.exception("embedding_index_failed video_id=%s", video_id)
        if video_id:
            queries.update_video_embedding_status(video_id, "failed")
        raise exc


def _sample_frames(clip: dict[str, Any], *, sample_every_seconds: float = 1.0) -> list[dict[str, Any]]:
    try:
        import cv2  # type: ignore
    except ImportError:
        return []

    clip_path = Path(clip["clip_path"])
    output_dir = settings.frames_dir / clip["video_id"] / clip["id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        return []

    fps = capture.get(cv2.CAP_PROP_FPS) or 15
    frame_step = max(1, int(fps * sample_every_seconds))
    frame_index = 0
    saved = 0
    records = []
    while saved < 12:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % frame_step == 0:
            frame_time = frame_index / fps if fps else saved * sample_every_seconds
            frame_path = output_dir / f"frame_{saved:04d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            records.append(
                {
                    "clip_id": clip["id"],
                    "video_id": clip["video_id"],
                    "clip_path": str(clip_path),
                    "frame_path": str(frame_path),
                    "frame_time_seconds": round(frame_time, 3),
                    "absolute_time_seconds": round(float(clip["start_time"] or 0) + frame_time, 3),
                }
            )
            saved += 1
        frame_index += 1
    capture.release()
    return records


def _model() -> Any:
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        logger.info("embedding_model_loading model=%s", MODEL_NAME)
        _MODEL = SentenceTransformer(MODEL_NAME)
        logger.info("embedding_model_loaded model=%s", MODEL_NAME)
    return _MODEL


def _load_metadata(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    try:
        relative = Path(path).relative_to(settings.storage_dir)
    except ValueError:
        return None
    return f"{settings.media_url_prefix}/{relative.as_posix()}"
