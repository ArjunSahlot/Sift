from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings


def score_faces(
    clip_path: str | Path,
    *,
    include_samples: bool = False,
    absolute_start_time: float = 0.0,
) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
    except ImportError:
        return _empty_result("opencv_missing", include_samples)

    model_path = settings.face_model_path
    if not model_path.exists() or not hasattr(cv2, "FaceDetectorYN"):
        return _haar_fallback(
            cv2,
            clip_path,
            include_samples=include_samples,
            absolute_start_time=absolute_start_time,
            method="haar_fallback_no_yunet",
        )

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        return _empty_result("video_open_failed", include_samples)

    fps = capture.get(cv2.CAP_PROP_FPS) or 15
    sample_every = max(1, int(fps))
    sampled = 0
    frame_index = 0
    frames_with_faces = 0
    face_sizes: list[float] = []
    face_counts: list[int] = []
    on_axis = 0
    off_axis = 0
    samples: list[dict[str, Any]] = []
    detector: Any | None = None

    while sampled < 30:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % sample_every != 0:
            frame_index += 1
            continue

        sampled += 1
        height, width = frame.shape[:2]
        if detector is None:
            detector = cv2.FaceDetectorYN.create(
                str(model_path),
                "",
                (width, height),
                score_threshold=0.7,
                nms_threshold=0.3,
                top_k=5000,
            )
        else:
            detector.setInputSize((width, height))

        _, faces = detector.detect(frame)
        parsed_faces = [_parse_yunet_face(face, width, height) for face in faces] if faces is not None else []
        face_count = len(parsed_faces)
        largest = max((face["sizeRatio"] for face in parsed_faces), default=0.0)
        axes = [face["axis"] for face in parsed_faces]
        on_axis += axes.count("on-axis")
        off_axis += axes.count("off-axis")

        if face_count:
            frames_with_faces += 1
            face_counts.append(face_count)
            face_sizes.append(largest)

        if include_samples:
            time_offset = frame_index / fps if fps else sampled - 1
            samples.append(
                {
                    "frameIndex": frame_index,
                    "time": float(time_offset),
                    "absoluteTime": float(absolute_start_time + time_offset),
                    "hasFace": bool(face_count),
                    "faceCount": int(face_count),
                    "largestFaceSizeRatio": float(largest),
                    "axes": axes,
                    "boxes": parsed_faces[:4],
                }
            )

        frame_index += 1

    capture.release()
    return _summarize(
        method="yunet_onnx",
        sampled=sampled,
        frames_with_faces=frames_with_faces,
        face_sizes=face_sizes,
        face_counts=face_counts,
        on_axis=on_axis,
        off_axis=off_axis,
        samples=samples if include_samples else None,
    )


def classify_face_axis(face: Any, threshold: float = 0.22) -> str:
    right_eye_x = float(face[4])
    left_eye_x = float(face[6])
    nose_x = float(face[8])

    eye_min = min(right_eye_x, left_eye_x)
    eye_max = max(right_eye_x, left_eye_x)
    eye_span = eye_max - eye_min
    if eye_span <= 1:
        return "off-axis"

    nose_ratio = (nose_x - eye_min) / eye_span
    if 0.5 - threshold <= nose_ratio <= 0.5 + threshold:
        return "on-axis"
    return "off-axis"


def _parse_yunet_face(face: Any, frame_width: int, frame_height: int) -> dict[str, Any]:
    x, y, width, height = [float(value) for value in face[:4]]
    area = max(1, frame_width * frame_height)
    return {
        "x": x / frame_width,
        "y": y / frame_height,
        "width": width / frame_width,
        "height": height / frame_height,
        "sizeRatio": (width * height) / area,
        "score": float(face[-1]),
        "axis": classify_face_axis(face),
    }


def _haar_fallback(
    cv2: Any,
    clip_path: str | Path,
    *,
    include_samples: bool,
    absolute_start_time: float,
    method: str,
) -> dict[str, Any]:
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        return _empty_result("face_detector_missing", include_samples)

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        return _empty_result("video_open_failed", include_samples)

    fps = capture.get(cv2.CAP_PROP_FPS) or 15
    sample_every = max(1, int(fps))
    sampled = 0
    frame_index = 0
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
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            area = frame.shape[0] * frame.shape[1]
            boxes = [
                {
                    "x": float(x / frame.shape[1]),
                    "y": float(y / frame.shape[0]),
                    "width": float(width / frame.shape[1]),
                    "height": float(height / frame.shape[0]),
                    "sizeRatio": float((width * height) / area),
                    "score": None,
                    "axis": "unknown",
                }
                for (x, y, width, height) in faces
            ]
            largest = max((box["sizeRatio"] for box in boxes), default=0.0)
            if len(faces):
                frames_with_faces += 1
                face_counts.append(len(faces))
                face_sizes.append(largest)
            if include_samples:
                time_offset = frame_index / fps if fps else sampled - 1
                samples.append(
                    {
                        "frameIndex": frame_index,
                        "time": float(time_offset),
                        "absoluteTime": float(absolute_start_time + time_offset),
                        "hasFace": bool(len(faces)),
                        "faceCount": int(len(faces)),
                        "largestFaceSizeRatio": float(largest),
                        "axes": ["unknown" for _ in faces],
                        "boxes": boxes[:4],
                    }
                )
        frame_index += 1

    capture.release()
    return _summarize(
        method=method,
        sampled=sampled,
        frames_with_faces=frames_with_faces,
        face_sizes=face_sizes,
        face_counts=face_counts,
        on_axis=0,
        off_axis=0,
        samples=samples if include_samples else None,
    )


def _summarize(
    *,
    method: str,
    sampled: int,
    frames_with_faces: int,
    face_sizes: list[float],
    face_counts: list[int],
    on_axis: int,
    off_axis: int,
    samples: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if sampled == 0:
        return _empty_result(method, samples is not None)

    presence = frames_with_faces / sampled
    average_size = sum(face_sizes) / len(face_sizes) if face_sizes else 0.0
    max_size = max(face_sizes) if face_sizes else 0.0
    max_faces = max(face_counts) if face_counts else 0
    speaker_bucket = "2plus" if max_faces >= 2 else str(max_faces)
    axis = _axis_label(on_axis, off_axis, speaker_bucket)
    size_score = min(1.0, average_size / 0.08) if average_size else 0.0
    face_score = max(0.0, min(1.0, presence * 0.7 + size_score * 0.3))
    result = {
        "method": method,
        "face_score": face_score,
        "face_presence_ratio": presence,
        "average_face_size_ratio": average_size,
        "max_face_size_ratio": max_size,
        "face_count_estimate": round(sum(face_counts) / len(face_counts)) if face_counts else 0,
        "speaker_count": max_faces,
        "speaker_bucket": speaker_bucket,
        "face_axis": axis,
        "on_axis_faces": on_axis,
        "off_axis_faces": off_axis,
    }
    if samples is not None:
        result["samples"] = samples
    return result


def _axis_label(on_axis: int, off_axis: int, speaker_bucket: str) -> str:
    total = on_axis + off_axis
    if speaker_bucket != "1" or total == 0:
        return "unknown"
    if on_axis / total >= 0.6:
        return "on-axis"
    if off_axis / total >= 0.6:
        return "off-axis"
    return "mixed"


def _empty_result(method: str, include_samples: bool) -> dict[str, Any]:
    result = {
        "method": method,
        "face_score": 0.0,
        "face_presence_ratio": 0.0,
        "average_face_size_ratio": 0.0,
        "max_face_size_ratio": 0.0,
        "face_count_estimate": 0,
        "speaker_count": 0,
        "speaker_bucket": "0",
        "face_axis": "unknown",
        "on_axis_faces": 0,
        "off_axis_faces": 0,
    }
    if include_samples:
        result["samples"] = []
    return result
