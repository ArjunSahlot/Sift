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
  sceneIndex?: number;
  startTime: number;
  endTime: number;
  duration: number;
  quality: ClipQuality;
  qualityScore: number;
  speechScore?: number;
  faceScore?: number;
  audioScore?: number;
  hasSpeech?: boolean;
  speechCoverage?: number;
  speakerCount?: number;
  speakerBucket?: "0" | "1" | "2plus" | string;
  faceAxis?: "on-axis" | "off-axis" | "mixed" | "unknown" | string;
  embeddingStatus?: "pending" | "indexing" | "complete" | "failed" | string;
  semanticScore?: number;
  bestFrameUrl?: string;
  bestFrameTimeSeconds?: number;
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
  speaker: "any" | "0" | "1" | "2plus";
  faceAxis: "any" | "on-axis" | "off-axis" | "mixed";
  speech: "any" | "detected" | "none";
  embedding: "any" | "ready" | "pending";
  faceVisible: boolean;
  audioClean: boolean;
  hasTranscript: boolean;
  exportableOnly: boolean;
};
