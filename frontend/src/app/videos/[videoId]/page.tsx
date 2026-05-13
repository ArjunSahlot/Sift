"use client";

import {
  ArrowLeft,
  Clock3,
  Download,
  FileArchive,
  Gauge,
  Play,
  RefreshCw,
  Rows3,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ClipCard } from "@/components/ClipCard";
import { DebugDropdown } from "@/components/DebugDropdown";
import { EmptyState } from "@/components/EmptyState";
import { ExportModal, type ExportSettings } from "@/components/ExportModal";
import { LoadingState } from "@/components/LoadingState";
import { ProgressStage } from "@/components/ProgressStage";
import { QualityBadge } from "@/components/QualityBadge";
import {
  createExport,
  getVideo as fetchVideo,
  getVideoClips,
  updateClipQuality as patchClipQuality,
  reprocessVideo,
} from "@/lib/api";
import type { ClipItem, ClipQuality, VideoItem } from "@/lib/types";
import {
  cn,
  formatDate,
  formatDuration,
  formatFileSize,
  formatScore,
} from "@/lib/utils";

type ClipTab = "good" | "review" | "rejected" | "all";

const tabs: Array<{ id: ClipTab; label: string }> = [
  { id: "good", label: "Good" },
  { id: "review", label: "Needs Review" },
  { id: "rejected", label: "Rejected" },
  { id: "all", label: "All" },
];

export default function VideoDetailPage() {
  const router = useRouter();
  const params = useParams<{ videoId: string }>();
  const videoId = params.videoId;
  const [video, setVideo] = useState<VideoItem>();
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [activeTab, setActiveTab] = useState<ClipTab>("good");
  const [exportOpen, setExportOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewError, setReviewError] = useState("");

  const loadVideo = useCallback(async () => {
    try {
      const nextVideo = await fetchVideo(videoId);
      const nextClips = await getVideoClips(videoId, "all");
      setVideo(nextVideo);
      setClips(nextClips);
      setError("");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load video detail.",
      );
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    void loadVideo();
  }, [loadVideo]);

  useEffect(() => {
    if (!video || !["queued", "processing", "uploading"].includes(video.status)) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadVideo();
    }, 2000);

    return () => window.clearInterval(timer);
  }, [loadVideo, video]);

  const summary = useMemo(() => summarize(video, clips), [clips, video]);
  const visibleClips = useMemo(() => {
    if (activeTab === "all") {
      return clips;
    }

    return clips.filter((clip) => clip.quality === activeTab);
  }, [activeTab, clips]);

  async function updateClipQuality(clipId: string, quality: ClipQuality) {
    const previousClips = clips;
    setReviewError("");
    setClips((currentClips) =>
      currentClips.map((clip) =>
        clip.id === clipId
          ? {
              ...clip,
              quality,
              exportable: quality !== "rejected",
              rejectionReasons:
                quality === "rejected"
                  ? clip.rejectionReasons ?? ["manual_reviewer_rejected_clip"]
                  : [],
            }
          : clip,
      ),
    );

    try {
      const updatedClip = await patchClipQuality(clipId, quality);
      setClips((currentClips) =>
        currentClips.map((clip) => (clip.id === clipId ? updatedClip : clip)),
      );
      const nextVideo = await fetchVideo(videoId);
      setVideo(nextVideo);
    } catch (caughtError) {
      setClips(previousClips);
      setReviewError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not update clip quality.",
      );
    }
  }

  async function handleVideoExport(settings: ExportSettings) {
    return createExport({
      mode: "video",
      videoId,
      filters: {
        quality: selectedQuality(settings.quality) ?? "good",
      },
      ...settings.include,
      includeTranscripts: settings.metadata.transcript,
      includeQualityScores: settings.metadata.scores,
      includeTags: settings.metadata.tags,
      includeRejectionReasons: settings.metadata.rejectionReasons,
    });
  }

  async function handleReprocess() {
    try {
      setLoading(true);
      await reprocessVideo(videoId);
      await loadVideo();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not reprocess video.",
      );
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen px-5 py-6 text-zinc-100 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <LoadingState label="Loading video detail..." />
        </div>
      </main>
    );
  }

  if (!video) {
    return (
      <main className="min-h-screen px-5 py-6 text-zinc-100 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <button
            type="button"
            onClick={() => router.push("/")}
            className="mb-6 inline-flex h-10 items-center gap-2 rounded-md border border-white/10 px-3 text-sm text-zinc-300 transition hover:bg-white/5 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Public Videos
          </button>
          <EmptyState
            title="Video not found."
            description={error || "The backend does not have metadata for that video ID."}
          />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-5 py-6 text-zinc-100 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-5 border-b border-white/10 pb-6 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <button
              type="button"
              onClick={() => router.push("/")}
              className="mb-5 inline-flex h-10 items-center gap-2 rounded-md border border-white/10 px-3 text-sm text-zinc-300 transition hover:bg-white/5 hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Public Videos
            </button>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-tight text-white md:text-5xl">
                {video.title}
              </h1>
              <QualityBadge status={video.status} />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-zinc-400">
              <span>{video.filename}</span>
              <span>{formatDate(video.createdAt)}</span>
              <span>{formatDuration(video.durationSeconds)}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setExportOpen(true)}
              disabled={!summary.good}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              Export Good Clips
            </button>
            <button
              type="button"
              disabled={video.status === "queued" || video.status === "processing"}
              onClick={() => void handleReprocess()}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-white/10 px-4 text-sm font-medium text-zinc-300 transition hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className="h-4 w-4" />
              Reprocess
            </button>
          </div>
        </header>

        {error || reviewError ? (
          <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">
            {reviewError || error}
          </p>
        ) : null}

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <OriginalVideoPanel video={video} />
          <SummaryPanel video={video} summary={summary} />
        </section>

        <section>
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-white">
                Extracted clips
              </h2>
              <p className="mt-2 text-sm text-zinc-400">
                Review quality-filtered clips, transcripts, scores, and rejection reasons.
              </p>
            </div>
            <div className="inline-flex rounded-lg border border-white/10 bg-white/[0.035] p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "h-9 rounded-md px-3 text-sm font-medium text-zinc-400 transition",
                    activeTab === tab.id && "bg-white text-zinc-950",
                    activeTab !== tab.id && "hover:bg-white/5 hover:text-zinc-100",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {video.status === "processing" || video.status === "queued" ? (
            <LoadingState label="Processing video clips..." />
          ) : video.status === "failed" ? (
            <EmptyState
              title="Processing failed."
              description={video.error ?? "No clips were extracted for this video."}
            />
          ) : visibleClips.length ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleClips.map((clip) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  reviewControls
                  onQualityChange={updateClipQuality}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No clips in this tab."
              description="Change tabs or review decisions to see more extracted clips."
            />
          )}
        </section>
        
        <DebugDropdown videoId={videoId} videoStatus={video.status}/>
      </div>

      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        mode="video"
        resultCount={summary.good}
        onGenerate={handleVideoExport}
      />
    </main>
  );
}

function OriginalVideoPanel({ video }: { video: VideoItem }) {
  return (
    <div className="overflow-hidden rounded-lg border border-white/10 bg-panel">
      <div className="relative aspect-video bg-zinc-950">
        {video.videoUrl ? (
          <video src={video.videoUrl} controls className="h-full w-full object-cover" />
        ) : video.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={video.thumbnailUrl}
            alt=""
            className="h-full w-full object-cover opacity-85"
          />
        ) : (
          <div className="sift-grid h-full w-full" />
        )}
        {!video.videoUrl ? (
          <>
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-transparent" />
            <button
              type="button"
              className="absolute left-1/2 top-1/2 grid h-14 w-14 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-zinc-950 shadow-sm"
              aria-label="Preview original video"
            >
              <Play className="h-5 w-5 fill-current" />
            </button>
          </>
        ) : null}
      </div>
      <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <Metadata label="Duration" value={formatDuration(video.durationSeconds)} />
        <Metadata label="Resolution" value={video.resolution ?? "n/a"} />
        <Metadata label="FPS" value={video.fps ? video.fps.toString() : "n/a"} />
        <Metadata label="File size" value={formatFileSize(video.fileSizeMb)} />
        <Metadata label="Source type" value={video.sourceType} />
      </div>
    </div>
  );
}

function SummaryPanel({
  video,
  summary,
}: {
  video: VideoItem;
  summary: ReturnType<typeof summarize>;
}) {
  return (
    <aside className="rounded-lg border border-white/10 bg-panel p-5">
      <div className="flex items-center gap-2">
        <Rows3 className="h-4 w-4 text-cyan-200" />
        <h2 className="font-semibold text-zinc-100">Processing summary</h2>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-3">
        <SummaryMetric label="Candidate clips" value={summary.candidates.toString()} />
        <SummaryMetric label="Good clips" value={summary.good.toString()} />
        <SummaryMetric label="Needs review" value={summary.review.toString()} />
        <SummaryMetric label="Rejected" value={summary.rejected.toString()} />
      </div>
      <div className="mt-4 space-y-3 rounded-lg border border-white/10 bg-white/[0.035] p-4">
        <SummaryLine
          icon={Clock3}
          label="Accepted duration"
          value={formatDuration(summary.acceptedDuration)}
        />
        <SummaryLine
          icon={Gauge}
          label="Top rejection"
          value={summary.topRejectionReason}
        />
        <SummaryLine
          icon={FileArchive}
          label="Processing time"
          value={
            video.processingTimeSeconds
              ? formatDuration(video.processingTimeSeconds)
              : "n/a"
          }
        />
      </div>
      <div className="mt-5">
        <ProgressStage video={video} />
      </div>
      <div className="mt-5 rounded-lg border border-white/10 bg-zinc-950/45 p-4">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
          Average quality score
        </p>
        <p className="mt-2 text-3xl font-semibold text-white">
          {formatScore(summary.averageQuality)}
        </p>
      </div>
    </aside>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.035] p-3">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </p>
      <p className="mt-2 truncate text-sm font-medium text-zinc-100 capitalize">{value}</p>
    </div>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.035] p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function SummaryLine({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="inline-flex min-w-0 items-center gap-2 text-zinc-400">
        <Icon className="h-4 w-4 shrink-0 text-zinc-500" />
        <span className="truncate">{label}</span>
      </span>
      <span className="max-w-[12rem] truncate font-medium text-zinc-100">{value}</span>
    </div>
  );
}

function summarize(video: VideoItem | undefined, clips: ClipItem[]) {
  const candidates = clips.length || video?.clipsFound || 0;
  const good = clips.filter((clip) => clip.quality === "good").length || video?.goodClips || 0;
  const review =
    clips.filter((clip) => clip.quality === "review").length || video?.reviewClips || 0;
  const rejected =
    clips.filter((clip) => clip.quality === "rejected").length || video?.rejectedClips || 0;
  const acceptedDuration = clips
    .filter((clip) => clip.quality === "good")
    .reduce((total, clip) => total + clip.duration, 0);
  const rejectionReasons = clips.flatMap((clip) => clip.rejectionReasons ?? []);
  const topRejectionReason =
    rejectionReasons[0] ?? video?.mostCommonRejectionReason ?? "n/a";
  const averageQuality =
    clips.length > 0
      ? clips.reduce((total, clip) => total + clip.qualityScore, 0) / clips.length
      : undefined;

  return {
    candidates,
    good,
    review,
    rejected,
    acceptedDuration,
    topRejectionReason,
    averageQuality,
  };
}

function selectedQuality(quality: ExportSettings["quality"]): ClipQuality | "any" | undefined {
  const selected = Object.entries(quality)
    .filter(([, enabled]) => enabled)
    .map(([key]) => key as ClipQuality);

  if (selected.length === 0) {
    return "any";
  }

  return selected.length === 1 ? selected[0] : undefined;
}
