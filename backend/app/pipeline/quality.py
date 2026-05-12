from __future__ import annotations

from typing import Any


def classify_clip(
    *,
    duration: float,
    speech_score: float,
    face_score: float,
    audio_score: float,
    face_stats: dict[str, Any],
    audio_stats: dict[str, float],
) -> dict[str, Any]:
    quality_score = max(
        0.0,
        min(1.0, speech_score * 0.4 + face_score * 0.35 + audio_score * 0.25),
    )
    tags: list[str] = []
    reasons: list[str] = []

    if speech_score >= 0.45:
        tags.append("human-speaking")
    else:
        reasons.append("low_speech_coverage")

    if face_score >= 0.3:
        tags.append("face-visible")
    else:
        presence = float(face_stats.get("face_presence_ratio") or 0)
        reasons.append("no_face_detected" if presence == 0 else "face_too_small")

    if audio_score >= 0.65:
        tags.append("clean-audio")
    elif audio_score < 0.35:
        reasons.append("audio_quality_low")

    if int(face_stats.get("face_count_estimate") or 0) <= 1:
        tags.append("single-speaker-likely")

    if duration < 3:
        reasons.append("too_short")
    if duration > 20:
        reasons.append("too_long")
    if float(audio_stats.get("silence_ratio") or 0) > 0.65:
        reasons.append("too_much_silence")
    if float(audio_stats.get("audio_clipping_ratio") or 0) > 0.02:
        reasons.append("audio_clipping")

    if speech_score < 0.45:
        quality = "rejected"
    elif face_score < 0.30:
        quality = "rejected"
    elif audio_score < 0.35:
        quality = "review"
    elif quality_score >= 0.75:
        quality = "good"
    else:
        quality = "review"

    if quality != "rejected":
        reasons = [reason for reason in reasons if reason not in {"no_face_detected"}]

    return {
        "quality": quality,
        "quality_score": quality_score,
        "tags": sorted(set(tags)),
        "rejection_reasons": sorted(set(reasons)),
        "exportable": quality != "rejected",
    }
