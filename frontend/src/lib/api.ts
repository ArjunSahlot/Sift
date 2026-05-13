import type { ClipItem, ClipQuality, JobStatus, QueryFilters, VideoItem } from "./types";

const rawApiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export const API_BASE_URL = rawApiBaseUrl;

export type UploadResponse = {
  jobId: string;
  videoId: string;
  status: JobStatus;
};

export type JobStatusResponse = {
  id: string;
  videoId: string;
  status: JobStatus;
  progressStage?: string;
  progressPercent?: number;
  clipsFound?: number;
  error?: string | null;
  createdAt?: string;
  updatedAt?: string;
};

export type ExportRequest = {
  mode: "query" | "video";
  query?: string;
  videoId?: string;
  filters?: Partial<QueryFilters> & Record<string, string | boolean | undefined>;
  includeClips: boolean;
  includeThumbnails: boolean;
  includeManifest: boolean;
  includeSummary: boolean;
  includeTranscripts?: boolean;
  includeQualityScores?: boolean;
  includeTags?: boolean;
  includeRejectionReasons?: boolean;
};

export type ExportResponse = {
  exportId: string;
  status: "processing" | "complete" | "failed";
  downloadUrl?: string;
};

export type DebugFileInfo = {
  path: string | null;
  exists: boolean;
  sizeBytes: number | null;
  url?: string | null;
};

export type DebugStageStatus =
  | "pending"
  | "running"
  | "complete"
  | "failed"
  | "skipped";

export type DebugStage = {
  id: string;
  label: string;
  status: DebugStageStatus;
  module?: string;
  startedAt?: string | null;
  completedAt?: string | null;
  error?: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
};

export type DebugTimelineSegment = {
  id: string;
  label: string;
  start: number;
  end: number;
  kind: "speech" | "clip" | "face" | "quality" | string;
  clipId?: string;
  quality?: ClipQuality | string;
  score?: number;
};

export type DebugTimelineTrack = {
  id: string;
  label: string;
  description?: string;
  segments: DebugTimelineSegment[];
};

export type DebugMediaClip = {
  id: string;
  index?: number;
  start?: number;
  end?: number;
  duration?: number;
  clipUrl?: string;
  thumbnailUrl?: string;
  quality?: ClipQuality | string;
  qualityScore?: number;
  speechScore?: number;
  faceScore?: number;
  audioScore?: number;
  hasSpeech?: boolean;
  speechCoverage?: number;
  speakerCount?: number;
  speakerBucket?: string;
  faceAxis?: string;
  embeddingStatus?: string;
  transcript?: string | null;
  tags?: string[];
  rejectionReasons?: string[];
  exportable?: boolean;
  faceStats?: Record<string, unknown>;
  audioStats?: Record<string, unknown>;
  files?: {
    clip?: DebugFileInfo;
    thumbnail?: DebugFileInfo;
  };
};

export type VideoDebugPayload = {
  schemaVersion?: number;
  video: Record<string, unknown> & {
    id: string;
    raw?: DebugFileInfo;
    normalized?: DebugFileInfo;
    coverThumbnail?: DebugFileInfo;
  };
  job: Record<string, unknown> | null;
  settings: Record<string, unknown>;
  media: {
    rawUrl?: string;
    normalizedUrl?: string;
    coverThumbnailUrl?: string;
    clips: DebugMediaClip[];
  };
  timeline: {
    durationSeconds: number;
    tracks: DebugTimelineTrack[];
  };
  stages: DebugStage[];
};


export function isApiConfigured() {
  return Boolean(process.env.NEXT_PUBLIC_API_URL);
}

export async function uploadVideo(file: File, title?: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("sourceType", "upload");

  if (title) {
    formData.append("title", title);
  }

  return request<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData,
  });
}

export async function uploadYouTube(url: string) {
  const formData = new FormData();
  formData.append("url", url);
  formData.append("sourceType", "youtube");

  return request<UploadResponse>("/api/youtube", {
    method: "POST",
    body: formData,
  });
}

export async function getPublicVideos() {
  const videos = await request<VideoItem[]>("/api/videos", { cache: "no-store" });
  return videos.map(normalizeVideo);
}

export async function reprocessVideo(videoId: string) {
  return request<UploadResponse>(`/api/videos/${videoId}/reprocess`, {
    method: "POST",
  });
}

export async function getVideo(videoId: string) {
  const video = await request<VideoItem>(`/api/videos/${videoId}`, {
    cache: "no-store",
  });
  return normalizeVideo(video);
}

export async function getVideoClips(videoId: string, quality: ClipQuality | "all" = "all") {
  const params = new URLSearchParams();
  params.set("quality", quality);
  const clips = await request<ClipItem[]>(
    `/api/videos/${videoId}/clips?${params.toString()}`,
    { cache: "no-store" },
  );
  return clips.map(normalizeClip);
}

export async function getVideoDebug(videoId: string) {
  const debug = await request<VideoDebugPayload>(`/api/videos/${videoId}/debug`, {
    cache: "no-store",
  });
  return normalizeDebug(debug);
}

export function getJobStatus(jobId: string) {
  return request<JobStatusResponse>(`/api/jobs/${jobId}`, { cache: "no-store" });
}

export async function searchClips({
  query,
  filters,
}: {
  query: string;
  filters: QueryFilters;
}) {
  const params = new URLSearchParams();
  params.set("q", query);

  if (filters.duration !== "any") {
    params.set("duration", filters.duration);
  }
  if (filters.speaker !== "any") {
    params.set("speaker", filters.speaker);
  }
  if (filters.faceAxis !== "any") {
    params.set("axis", filters.faceAxis);
  }
  if (filters.speech !== "any") {
    params.set("speech", filters.speech);
  }

  const clips = await request<ClipItem[]>(`/api/search?${params.toString()}`, {
    cache: "no-store",
  });
  return clips.map(normalizeClip).filter((clip) => {
    return (
      (!filters.faceVisible || clip.tags.includes("face-visible")) &&
      (!filters.audioClean || clip.tags.includes("clean-audio")) &&
    (!filters.hasTranscript || Boolean(clip.transcript)) &&
      (!filters.exportableOnly || clip.exportable)
    );
  });
}

export async function updateClipQuality(clipId: string, quality: ClipQuality) {
  const clip = await request<ClipItem>(`/api/clips/${clipId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ quality }),
  });
  return normalizeClip(clip);
}

export async function createExport(payload: ExportRequest) {
  const response = await request<ExportResponse>("/api/export", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return {
    ...response,
    downloadUrl: resolveMediaUrl(response.downloadUrl),
  };
}

export async function getExport(exportId: string) {
  const response = await request<ExportResponse>(`/api/export/${exportId}`, {
    cache: "no-store",
  });
  return {
    ...response,
    downloadUrl: resolveMediaUrl(response.downloadUrl),
  };
}

export function resolveMediaUrl(value?: string | null) {
  if (!value) {
    return undefined;
  }

  if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("blob:")) {
    return value;
  }

  if (value.startsWith("/")) {
    return `${API_BASE_URL}${value}`;
  }

  return value;
}

function normalizeVideo(video: VideoItem): VideoItem {
  return {
    ...video,
    thumbnailUrl: resolveMediaUrl(video.thumbnailUrl),
    videoUrl: resolveMediaUrl(video.videoUrl),
  };
}

function normalizeClip(clip: ClipItem): ClipItem {
  return {
    ...clip,
    clipUrl: resolveMediaUrl(clip.clipUrl) ?? clip.clipUrl,
    thumbnailUrl: resolveMediaUrl(clip.thumbnailUrl),
    bestFrameUrl: resolveMediaUrl(clip.bestFrameUrl),
  };
}

function normalizeDebug(debug: VideoDebugPayload): VideoDebugPayload {
  return {
    ...debug,
    video: normalizeDebugValue(debug.video) as VideoDebugPayload["video"],
    media: {
      ...debug.media,
      rawUrl: resolveMediaUrl(debug.media?.rawUrl),
      normalizedUrl: resolveMediaUrl(debug.media?.normalizedUrl),
      coverThumbnailUrl: resolveMediaUrl(debug.media?.coverThumbnailUrl),
      clips: (debug.media?.clips ?? []).map((clip) => ({
        ...clip,
        clipUrl: resolveMediaUrl(clip.clipUrl),
        thumbnailUrl: resolveMediaUrl(clip.thumbnailUrl),
        files: normalizeDebugValue(clip.files) as DebugMediaClip["files"],
      })),
    },
    stages: (debug.stages ?? []).map((stage) => ({
      ...stage,
      inputs: normalizeDebugValue(stage.inputs) as Record<string, unknown>,
      outputs: normalizeDebugValue(stage.outputs) as Record<string, unknown>,
    })),
  };
}

function normalizeDebugValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(normalizeDebugValue);
  }

  if (value && typeof value === "object") {
    const next: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      next[key] = key === "url" && typeof item === "string" ? resolveMediaUrl(item) : normalizeDebugValue(item);
    }
    return next;
  }

  return value;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    throw new Error(
      `Could not reach the Sift API at ${API_BASE_URL}. Check NEXT_PUBLIC_API_URL and backend CORS origins.`,
      { cause: error },
    );
  }

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function errorMessage(response: Response) {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String(item.msg)
            : "Request validation failed",
        )
        .join(", ");
    }
  } catch {
    // Fall through to a compact HTTP error.
  }

  return `Sift API request failed: ${response.status}`;
}
