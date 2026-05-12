export type JobStatus =
  | "queued"
  | "uploading"
  | "processing"
  | "complete"
  | "failed";

export type ClipQuality = "good" | "review" | "rejected";

export type VideoItem = {
  id: string;
  title: string;
  filename: string;
  sourceType: "upload" | "youtube" | "example";
  status: JobStatus;
  progressStage?: string;
  progressPercent?: number;
  thumbnailUrl?: string;
  videoUrl?: string;
  durationSeconds?: number;
  fileSizeMb?: number;
  resolution?: string;
  fps?: number;
  clipsFound?: number;
  goodClips?: number;
  reviewClips?: number;
  rejectedClips?: number;
  processingTimeSeconds?: number;
  mostCommonRejectionReason?: string;
  createdAt: string;
  error?: string;
};

export type ClipItem = {
  id: string;
  videoId: string;
  sourceVideoTitle: string;
  clipUrl: string;
  thumbnailUrl?: string;
  startTime: number;
  endTime: number;
  duration: number;
  quality: ClipQuality;
  qualityScore: number;
  speechScore?: number;
  faceScore?: number;
  audioScore?: number;
  transcript?: string;
  tags: string[];
  rejectionReasons?: string[];
  exportable: boolean;
};

export type Mode = "upload" | "query";

export type QueryFilters = {
  quality: "any" | ClipQuality;
  type: "any" | "speaking" | "human-visible" | "clean-audio" | "single-speaker";
  duration: "any" | "short" | "medium" | "long";
  faceVisible: boolean;
  audioClean: boolean;
  hasTranscript: boolean;
  exportableOnly: boolean;
};
