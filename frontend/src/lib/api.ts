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

export async function getPublicVideos() {
  const videos = await request<VideoItem[]>("/api/videos", { cache: "no-store" });
  return videos.map(normalizeVideo);
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

  if (filters.quality !== "any") {
    params.set("quality", filters.quality);
  }

  if (filters.type !== "any") {
    params.set("type", filters.type);
  }

  if (filters.duration !== "any") {
    params.set("duration", filters.duration);
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
  };
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
