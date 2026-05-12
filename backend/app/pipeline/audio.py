from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from app.utils.ffmpeg import run_command


def extract_audio(input_path: str | Path, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output),
        ],
        timeout=300,
    )
    return output


def read_wav_mono(path: str | Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())

    if sample_width == 2:
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 1:
        samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        samples = np.zeros(0, dtype=np.float32)
    return samples, sample_rate


def audio_metrics_from_wav(path: str | Path) -> dict[str, float]:
    samples, sample_rate = read_wav_mono(path)
    if samples.size == 0:
        return {
            "speech_coverage_ratio": 0.0,
            "silence_ratio": 1.0,
            "audio_clipping_ratio": 0.0,
            "mean_volume": 0.0,
            "audio_score": 0.0,
        }

    frame_size = max(1, int(sample_rate * 0.1))
    usable = samples[: samples.size - (samples.size % frame_size)]
    frames = usable.reshape(-1, frame_size) if usable.size else samples.reshape(1, -1)
    rms = np.sqrt(np.mean(np.square(frames), axis=1))
    noise_floor = float(np.percentile(rms, 35))
    speech_threshold = max(0.015, noise_floor * 2.4)
    speech_coverage = float(np.mean(rms > speech_threshold))
    silence_ratio = 1.0 - speech_coverage
    clipping_ratio = float(np.mean(np.abs(samples) > 0.98))
    mean_volume = float(np.mean(np.abs(samples)))

    volume_score = min(1.0, mean_volume / 0.08)
    clipping_penalty = min(0.8, clipping_ratio * 12.0)
    silence_penalty = max(0.0, silence_ratio - 0.35) * 0.8
    audio_score = max(0.0, min(1.0, 0.35 + volume_score * 0.55 - clipping_penalty - silence_penalty))

    return {
        "speech_coverage_ratio": speech_coverage,
        "silence_ratio": silence_ratio,
        "audio_clipping_ratio": clipping_ratio,
        "mean_volume": mean_volume,
        "audio_score": audio_score,
    }


def score_clip_audio(clip_path: str | Path, tmp_wav_path: str | Path) -> dict[str, float]:
    extract_audio(clip_path, tmp_wav_path)
    return audio_metrics_from_wav(tmp_wav_path)
