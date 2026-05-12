import type { ClipItem, JobStatus, QueryFilters, VideoItem } from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "https://api.example.com";

export type UploadResponse = {
  jobId: string;
  videoId: string;
};

export type JobStatusResponse = {
  id: string;
  status: JobStatus;
  progressStage?: string;
  progressPercent?: number;
  clipsFound?: number;
};

export type ExportRequest = {
  mode: "query" | "video";
  query?: string;
  videoId?: string;
  filters?: Partial<QueryFilters>;
  includeClips: boolean;
  includeThumbnails: boolean;
  includeManifest: boolean;
  includeSummary: boolean;
};

export type ExportResponse = {
  exportId: string;
  status: "processing" | "complete" | "failed";
  downloadUrl?: string;
};

export function isApiConfigured() {
  return API_BASE_URL !== "https://api.example.com";
}

export async function uploadVideo(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return request<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData,
  });
}

export function getPublicVideos() {
  return request<VideoItem[]>("/api/videos");
}

export function getVideo(videoId: string) {
  return request<VideoItem>(`/api/videos/${videoId}`);
}

export function getVideoClips(videoId: string) {
  return request<ClipItem[]>(`/api/videos/${videoId}/clips`);
}

export function getJobStatus(jobId: string) {
  return request<JobStatusResponse>(`/api/jobs/${jobId}`);
}

export function searchClips({
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

  return request<ClipItem[]>(`/api/search?${params.toString()}`);
}

export function createExport(payload: ExportRequest) {
  return request<ExportResponse>("/api/export", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function getExport(exportId: string) {
  return request<ExportResponse>(`/api/export/${exportId}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    throw new Error(`Sift API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}
