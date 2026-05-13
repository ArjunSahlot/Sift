import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { ClipItem, ClipQuality, JobStatus, QueryFilters } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const qualityLabels: Record<ClipQuality, string> = {
  good: "Good",
  review: "Needs Review",
  rejected: "Rejected",
};

export const statusLabels: Record<JobStatus, string> = {
  queued: "Queued",
  uploading: "Uploading",
  processing: "Processing",
  complete: "Complete",
  failed: "Failed",
};

export function formatDuration(seconds = 0) {
  const safeSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;

  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  }

  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

export function formatTimestamp(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds - minutes * 60;
  return `${minutes.toString().padStart(2, "0")}:${remainder
    .toFixed(1)
    .padStart(4, "0")}`;
}

export function formatClipRange(start: number, end: number) {
  return `${formatTimestamp(start)} -> ${formatTimestamp(end)}`;
}

export function formatScore(score?: number) {
  if (typeof score !== "number") {
    return "n/a";
  }

  return `${Math.round(score * 100)}%`;
}

export function formatFileSize(size?: number) {
  if (!size) {
    return "n/a";
  }

  return `${size.toFixed(size >= 100 ? 0 : 1)} MB`;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function stageLabel(stage?: string) {
  const labels: Record<string, string> = {
    queued: "Queued for processing...",
    uploading: "Uploading video...",
    detecting_speech: "Detecting speech...",
    detecting_scenes: "Detecting scene changes...",
    extracting_clips: "Extracting clips...",
    running_face_detection: "Running face detection...",
    scoring_quality: "Scoring quality...",
    generating_thumbnails: "Generating thumbnails...",
    indexing_embeddings: "Indexing semantic embeddings...",
    complete: "Complete",
  };

  return labels[stage ?? ""] ?? stage ?? "Waiting for job...";
}

export function filterClips(clips: ClipItem[], query: string, filters: QueryFilters) {
  const normalizedQuery = query.trim().toLowerCase();

  return clips.filter((clip) => {
    const searchable = [
      clip.sourceVideoTitle,
      clip.transcript,
      clip.tags.join(" "),
      clip.quality,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    const matchesQuery = !normalizedQuery || searchable.includes(normalizedQuery);
    const matchesQuality =
      filters.quality === "any" || clip.quality === filters.quality;
    const matchesType =
      filters.type === "any" ||
      (filters.type === "speaking" && clip.tags.includes("human-speaking")) ||
      (filters.type === "human-visible" &&
        (clip.tags.includes("face-visible") || (clip.faceScore ?? 0) >= 0.7)) ||
      (filters.type === "clean-audio" &&
        (clip.tags.includes("clean-audio") || (clip.audioScore ?? 0) >= 0.82)) ||
      (filters.type === "single-speaker" && clip.tags.includes("single-speaker"));
    const matchesDuration =
      filters.duration === "any" ||
      (filters.duration === "short" && clip.duration < 10) ||
      (filters.duration === "medium" &&
        clip.duration >= 10 &&
        clip.duration <= 20) ||
      (filters.duration === "long" && clip.duration > 20);
    const matchesSpeaker =
      filters.speaker === "any" || clip.speakerBucket === filters.speaker;
    const matchesAxis =
      filters.faceAxis === "any" || clip.faceAxis === filters.faceAxis;
    const matchesSpeech =
      filters.speech === "any" ||
      (filters.speech === "detected" && clip.hasSpeech) ||
      (filters.speech === "none" && !clip.hasSpeech);
    const matchesEmbedding =
      filters.embedding === "any" ||
      (filters.embedding === "ready" && clip.embeddingStatus === "complete") ||
      (filters.embedding === "pending" && clip.embeddingStatus !== "complete");
    const matchesToggles =
      (!filters.faceVisible || clip.tags.includes("face-visible")) &&
      (!filters.audioClean || clip.tags.includes("clean-audio")) &&
      (!filters.hasTranscript || Boolean(clip.transcript)) &&
      (!filters.exportableOnly || clip.exportable);

    return (
      matchesQuery &&
      matchesQuality &&
      matchesType &&
      matchesDuration &&
      matchesSpeaker &&
      matchesAxis &&
      matchesSpeech &&
      matchesEmbedding &&
      matchesToggles
    );
  });
}
