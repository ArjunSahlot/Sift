from __future__ import annotations

from pathlib import Path

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
    samples, sample_rate = read_wav_mono(audio_path)
    if samples.size == 0:
        return []

    frame_seconds = 0.03
    frame_size = max(1, int(sample_rate * frame_seconds))
    usable = samples[: samples.size - (samples.size % frame_size)]
    if usable.size == 0:
        return []
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
    return filtered[:max_segments]


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
