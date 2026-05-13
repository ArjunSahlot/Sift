from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.pipeline.audio import read_wav_mono


def detect_speech_segments(
    audio_path: str | Path,
    *,
    min_segment_seconds: float = 3.0,
    merge_gap_seconds: float = 0.5,
    max_segment_seconds: float = 20.0,
    max_segments: int = 30,
) -> list[dict[str, float]]:
    return analyze_speech_segments(
        audio_path,
        min_segment_seconds=min_segment_seconds,
        merge_gap_seconds=merge_gap_seconds,
        max_segment_seconds=max_segment_seconds,
        max_segments=max_segments,
    )["segments"]


def analyze_speech_segments(
    audio_path: str | Path,
    *,
    min_segment_seconds: float = 3.0,
    merge_gap_seconds: float = 0.5,
    max_segment_seconds: float = 20.0,
    max_segments: int = 30,
) -> dict[str, Any]:
    samples, sample_rate = read_wav_mono(audio_path)
    if samples.size == 0:
        return {
            "segments": [],
            "raw_segments": [],
            "merged_segments": [],
            "frame_seconds": 0.03,
            "sample_rate": sample_rate,
            "threshold": 0.0,
            "frame_count": 0,
            "active_frame_count": 0,
            "active_coverage": 0.0,
            "rms_samples": [],
        }

    frame_seconds = 0.03
    frame_size = max(1, int(sample_rate * frame_seconds))
    usable = samples[: samples.size - (samples.size % frame_size)]
    if usable.size == 0:
        return {
            "segments": [],
            "raw_segments": [],
            "merged_segments": [],
            "frame_seconds": frame_seconds,
            "sample_rate": sample_rate,
            "threshold": 0.0,
            "frame_count": 0,
            "active_frame_count": 0,
            "active_coverage": 0.0,
            "rms_samples": [],
        }
    frames = usable.reshape(-1, frame_size)
    rms = np.sqrt(np.mean(np.square(frames), axis=1))
    threshold = max(0.012, float(np.percentile(rms, 60)) * 2.0, float(np.mean(rms)) * 0.55)
    active = rms > threshold

    raw_segments: list[dict[str, float]] = []
    start_index: int | None = None
    for index, is_active in enumerate(active):
        if is_active and start_index is None:
            start_index = index
        elif not is_active and start_index is not None:
            raw_segments.append(
                {
                    "start": start_index * frame_seconds,
                    "end": index * frame_seconds,
                }
            )
            start_index = None
    if start_index is not None:
        raw_segments.append(
            {
                "start": start_index * frame_seconds,
                "end": len(active) * frame_seconds,
            }
        )

    merged = _merge_segments(raw_segments, merge_gap_seconds)
    split = _split_segments(merged, max_segment_seconds)
    filtered = [
        segment
        for segment in split
        if segment["end"] - segment["start"] >= min_segment_seconds
    ]
    segments = filtered[:max_segments]
    return {
        "segments": segments,
        "raw_segments": raw_segments,
        "merged_segments": merged,
        "frame_seconds": frame_seconds,
        "sample_rate": sample_rate,
        "threshold": float(threshold),
        "frame_count": int(len(active)),
        "active_frame_count": int(np.sum(active)),
        "active_coverage": float(np.mean(active)),
        "rms_samples": _downsample_rms(rms, threshold),
    }


def _downsample_rms(
    rms: np.ndarray,
    threshold: float,
    *,
    max_points: int = 160,
) -> list[dict[str, float | bool]]:
    if rms.size == 0:
        return []
    step = max(1, int(np.ceil(rms.size / max_points)))
    samples: list[dict[str, float | bool]] = []
    for index in range(0, rms.size, step):
        window = rms[index : index + step]
        value = float(np.mean(window))
        samples.append(
            {
                "frame": float(index),
                "rms": value,
                "active": value > threshold,
            }
        )
    return samples


def _merge_segments(
    segments: list[dict[str, float]], merge_gap_seconds: float
) -> list[dict[str, float]]:
    merged: list[dict[str, float]] = []
    for segment in segments:
        if not merged or segment["start"] - merged[-1]["end"] > merge_gap_seconds:
            merged.append(dict(segment))
        else:
            merged[-1]["end"] = segment["end"]
    return merged


def _split_segments(
    segments: list[dict[str, float]], max_segment_seconds: float
) -> list[dict[str, float]]:
    split: list[dict[str, float]] = []
    for segment in segments:
        start = segment["start"]
        end = segment["end"]
        while end - start > max_segment_seconds:
            split.append({"start": start, "end": start + max_segment_seconds})
            start += max_segment_seconds
        split.append({"start": start, "end": end})
    return split
