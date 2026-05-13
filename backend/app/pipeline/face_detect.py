from __future__ import annotations

from pathlib import Path
from typing import Any


def score_faces(
    clip_path: str | Path,
    *,
    include_samples: bool = False,
    absolute_start_time: float = 0.0,
) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
    except ImportError:
        return {
            "face_score": 0.45,
            "face_presence_ratio": 0.0,
            "average_face_size_ratio": 0.0,
            "max_face_size_ratio": 0.0,
            "face_count_estimate": 0,
        }

    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        return {
            "face_score": 0.45,
            "face_presence_ratio": 0.0,
            "average_face_size_ratio": 0.0,
            "max_face_size_ratio": 0.0,
            "face_count_estimate": 0,
        }

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        return {
            "face_score": 0.0,
            "face_presence_ratio": 0.0,
            "average_face_size_ratio": 0.0,
            "max_face_size_ratio": 0.0,
            "face_count_estimate": 0,
        }

    fps = capture.get(cv2.CAP_PROP_FPS) or 15
    sample_every = max(1, int(fps))
    frame_index = 0
    sampled = 0
    frames_with_faces = 0
    face_sizes: list[float] = []
    face_counts: list[int] = []
    samples: list[dict[str, Any]] = []

    while sampled < 30:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % sample_every == 0:
            sampled += 1
            time_offset = frame_index / fps if fps else sampled - 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )
            area = frame.shape[0] * frame.shape[1]
            face_boxes = [
                {
                    "x": float(x / frame.shape[1]),
                    "y": float(y / frame.shape[0]),
                    "width": float(w / frame.shape[1]),
                    "height": float(h / frame.shape[0]),
                    "sizeRatio": float((w * h) / area),
                }
                for (x, y, w, h) in faces
            ]
            largest = max((box["sizeRatio"] for box in face_boxes), default=0.0)
            if include_samples:
                samples.append(
                    {
                        "frameIndex": frame_index,
                        "time": float(time_offset),
                        "absoluteTime": float(absolute_start_time + time_offset),
                        "hasFace": bool(len(faces)),
                        "faceCount": int(len(faces)),
                        "largestFaceSizeRatio": float(largest),
                        "boxes": face_boxes[:4],
                    }
                )
            if len(faces):
                frames_with_faces += 1
                face_sizes.append(float(largest))
                face_counts.append(len(faces))
        frame_index += 1

    capture.release()

    if sampled == 0:
        result = {
            "face_score": 0.0,
            "face_presence_ratio": 0.0,
            "average_face_size_ratio": 0.0,
            "max_face_size_ratio": 0.0,
            "face_count_estimate": 0,
        }
        if include_samples:
            result["samples"] = samples
        return result

    presence = frames_with_faces / sampled
    average_size = sum(face_sizes) / len(face_sizes) if face_sizes else 0.0
    max_size = max(face_sizes) if face_sizes else 0.0
    size_score = min(1.0, average_size / 0.08) if average_size else 0.0
    face_score = max(0.0, min(1.0, presence * 0.7 + size_score * 0.3))

    result = {
        "face_score": face_score,
        "face_presence_ratio": presence,
        "average_face_size_ratio": average_size,
        "max_face_size_ratio": max_size,
        "face_count_estimate": round(sum(face_counts) / len(face_counts)) if face_counts else 0,
    }
    if include_samples:
        result["samples"] = samples
    return result
