"use client";

import {
  Bug,
  Captions,
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  CircleAlert,
  Copy,
  FileVideo,
  Gauge,
  Image as ImageIcon,
  Loader2,
  Play,
  RefreshCw,
  ScanFace,
  Scissors,
  Waves,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getVideoDebug,
  type DebugMediaClip,
  type DebugStage,
  type DebugStageStatus,
  type DebugTimelineSegment,
  type DebugTimelineTrack,
  type VideoDebugPayload,
} from "@/lib/api";
import { cn, formatDuration, formatScore } from "@/lib/utils";

const POLL_STATUSES = new Set(["queued", "uploading", "processing"]);

export function DebugDropdown({
  videoId,
  videoStatus,
}: {
  videoId: string;
  videoStatus: string;
}) {
  const [open, setOpen] = useState(true);
  const [data, setData] = useState<VideoDebugPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showRaw, setShowRaw] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getVideoDebug(videoId);
      setData(next);
      setExpanded((current) => expandRunningStage(current, next.stages));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load debug data.",
      );
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  useEffect(() => {
    if (!open || !POLL_STATUSES.has(videoStatus)) return;
    const timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [open, load, videoStatus]);

  const summary = useMemo(() => {
    if (!data) return null;
    const completed = data.stages.filter((stage) => stage.status === "complete").length;
    const failed = data.stages.filter((stage) => stage.status === "failed").length;
    return {
      completed,
      failed,
      total: data.stages.length,
      clipsOut: data.media.clips.length,
      speechSegments:
        data.timeline.tracks.find((track) => track.id === "speech")?.segments.length ?? 0,
      faceHits:
        data.timeline.tracks.find((track) => track.id === "faces")?.segments.length ?? 0,
    };
  }, [data]);

  async function copyJson() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard availability varies by browser origin.
    }
  }

  return (
    <section className="mt-8 overflow-hidden rounded-lg border border-white/10 bg-panel">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-white/[0.025]"
      >
        <span className="inline-flex min-w-0 items-center gap-3">
          <Bug className="h-4 w-4 shrink-0 text-cyan-200" />
          <span className="shrink-0 text-sm font-semibold uppercase tracking-[0.18em] text-zinc-200">
            Pipeline debug
          </span>
      {summary ? (
            <span className="truncate text-xs text-zinc-500">
              {summary.completed}/{summary.total} stages
              {summary.failed ? ` · ${summary.failed} failed` : ""}
              {` · ${summary.speechSegments} speech · ${summary.faceHits} face · ${summary.clipsOut} scene clips`}
            </span>
          ) : (
            <span className="truncate text-xs text-zinc-500">
              Visualize speech, faces, clips, quality, and media artifacts
            </span>
          )}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-zinc-500 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open ? (
        <div className="space-y-5 border-t border-white/10 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-zinc-500">
              Live artifacts from the worker. Polls while processing, then stays available
              for failed and completed runs.
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-white/10 px-2.5 text-xs text-zinc-300 transition hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                <RefreshCw
                  className={cn("h-3.5 w-3.5", loading && "animate-spin")}
                />
                Refresh
              </button>
              <button
                type="button"
                onClick={copyJson}
                disabled={!data}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-white/10 px-2.5 text-xs text-zinc-300 transition hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                <Copy className="h-3.5 w-3.5" />
                {copied ? "Copied" : "Copy JSON"}
              </button>
            </div>
          </div>

          {loading && !data ? (
            <p className="text-sm text-zinc-400">Loading pipeline artifacts...</p>
          ) : error ? (
            <p className="rounded-md border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">
              {error}
            </p>
          ) : data ? (
            <>
              <DebugTopline data={data} />
              <PipelineTimeline timeline={data.timeline} />
              <DebugClipGallery clips={data.media.clips} />

              <div className="space-y-2">
                {data.stages.map((stage) => (
                  <StageRow
                    key={stage.id}
                    stage={stage}
                    data={data}
                    expanded={expanded[stage.id] ?? false}
                    onToggle={() =>
                      setExpanded((prev) => ({
                        ...prev,
                        [stage.id]: !prev[stage.id],
                      }))
                    }
                  />
                ))}
              </div>

              <RawJsonPanel
                open={showRaw}
                onToggle={() => setShowRaw((value) => !value)}
                data={data}
              />
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function DebugTopline({ data }: { data: VideoDebugPayload }) {
  const video = data.video;
  const job = data.job ?? {};
  const fields: Array<{ label: string; value: string; mono?: boolean }> = [
    { label: "Video ID", value: String(video.id ?? "-"), mono: true },
    { label: "Job ID", value: String(job.id ?? "-"), mono: true },
    { label: "Job status", value: String(job.status ?? video.status ?? "-") },
    { label: "Stage", value: String(job.progressStage ?? "-") },
    {
      label: "Progress",
      value: job.progressPercent != null ? `${job.progressPercent}%` : "-",
    },
    {
      label: "Debug file",
      value: String(data.settings.debugArtifactPath ?? "-"),
      mono: true,
    },
  ];

  return (
    <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
      {fields.map((field) => (
        <DebugMetric
          key={field.label}
          label={field.label}
          value={field.value}
          mono={field.mono}
        />
      ))}
    </div>
  );
}

function PipelineTimeline({
  timeline,
}: {
  timeline: VideoDebugPayload["timeline"];
}) {
  const duration = Math.max(1, timeline.durationSeconds || 1);

  return (
    <div className="rounded-lg border border-white/10 bg-zinc-950/35 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-zinc-100">Extraction timeline</p>
          <p className="mt-1 text-xs text-zinc-500">
            Speech VAD, clip extraction, face detections, and final labels aligned
            against the source video.
          </p>
        </div>
        <span className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-zinc-400">
          {formatDuration(duration)}
        </span>
      </div>

      <div className="space-y-3">
        {timeline.tracks.map((track) => (
          <TimelineTrack key={track.id} duration={duration} track={track} />
        ))}
      </div>
    </div>
  );
}

function TimelineTrack({
  track,
  duration,
}: {
  track: DebugTimelineTrack;
  duration: number;
}) {
  return (
    <div className="grid gap-2 md:grid-cols-[9rem_1fr] md:items-center">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">
          {track.label}
        </p>
        {track.description ? (
          <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-zinc-600">
            {track.description}
          </p>
        ) : null}
      </div>
      <div className="relative h-9 overflow-hidden rounded-md border border-white/10 bg-black/35">
        <div className="absolute inset-y-0 left-1/4 w-px bg-white/[0.05]" />
        <div className="absolute inset-y-0 left-1/2 w-px bg-white/[0.05]" />
        <div className="absolute inset-y-0 left-3/4 w-px bg-white/[0.05]" />
        {track.segments.length ? (
          track.segments.map((segment) => (
            <TimelineSegment
              key={segment.id}
              duration={duration}
              segment={segment}
            />
          ))
        ) : (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[11px] text-zinc-600">
            No artifacts yet
          </span>
        )}
      </div>
    </div>
  );
}

function TimelineSegment({
  segment,
  duration,
}: {
  segment: DebugTimelineSegment;
  duration: number;
}) {
  const left = Math.max(0, Math.min(100, (segment.start / duration) * 100));
  const width = Math.max(0.7, Math.min(100 - left, ((segment.end - segment.start) / duration) * 100));
  const title = `${segment.label}: ${formatDuration(segment.start)} -> ${formatDuration(segment.end)}`;

  return (
    <span
      title={title}
      className={cn(
        "absolute top-1/2 h-5 -translate-y-1/2 rounded-sm border text-[10px] leading-5 shadow-sm",
        segmentClassName(segment),
      )}
      style={{ left: `${left}%`, width: `${width}%` }}
    >
      <span className="block truncate px-1.5">{segment.label}</span>
    </span>
  );
}

function DebugClipGallery({ clips }: { clips: DebugMediaClip[] }) {
  if (!clips.length) {
    return (
      <div className="rounded-lg border border-white/10 bg-white/[0.025] p-4">
        <p className="text-sm font-medium text-zinc-200">Clip previews</p>
        <p className="mt-1 text-xs text-zinc-500">
          Clips will appear here as soon as FFmpeg writes them.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.025] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-zinc-100">Extracted clip previews</p>
          <p className="mt-1 text-xs text-zinc-500">
            Actual media produced by the worker, visible before final DB rows exist.
          </p>
        </div>
        <span className="rounded-md border border-white/10 px-2 py-1 text-xs text-zinc-400">
          {clips.length} clips
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {clips.map((clip) => (
          <DebugClipPreview key={clip.id} clip={clip} />
        ))}
      </div>
    </div>
  );
}

function DebugClipPreview({ clip }: { clip: DebugMediaClip }) {
  const faceSamples = getFaceSamples(clip);

  return (
    <article className="overflow-hidden rounded-md border border-white/10 bg-black/30">
      <div className="relative aspect-video bg-zinc-950">
        {clip.clipUrl ? (
          <video
            src={clip.clipUrl}
            controls
            preload="metadata"
            className="h-full w-full object-cover"
          />
        ) : clip.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={clip.thumbnailUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="sift-grid flex h-full items-center justify-center">
            <Play className="h-6 w-6 text-zinc-700" />
          </div>
        )}
        {clip.quality ? (
          <span className={cn("absolute left-2 top-2 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]", qualityChipClass(clip.quality))}>
            {qualityLabel(clip.quality)}
          </span>
        ) : null}
      </div>
      <div className="space-y-3 p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="truncate font-mono text-xs text-zinc-300">{clip.id}</p>
          <p className="shrink-0 text-xs text-zinc-500">
            {formatRange(clip.start, clip.end)}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <MiniScore label="Speech" value={clip.speechScore} />
          <MiniScore label="Face" value={clip.faceScore} />
          <MiniScore label="Audio" value={clip.audioScore} />
        </div>
        {faceSamples.length ? <FaceSampleStrip samples={faceSamples} /> : null}
        {clip.rejectionReasons?.length ? (
          <p className="text-xs text-rose-200">
            {clip.rejectionReasons.join(", ")}
          </p>
        ) : null}
      </div>
    </article>
  );
}

function StageRow({
  stage,
  data,
  expanded,
  onToggle,
}: {
  stage: DebugStage;
  data: VideoDebugPayload;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border border-white/10 bg-white/[0.02] transition",
        expanded && "bg-white/[0.035]",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/[0.035]"
      >
        <StageIcon stageId={stage.id} status={stage.status} />
        <span className="text-sm font-medium text-zinc-100">{stage.label}</span>
        {stage.module ? (
          <span className="hidden truncate font-mono text-[11px] text-zinc-500 md:inline">
            {stage.module}
          </span>
        ) : null}
        <span className="ml-auto inline-flex items-center gap-2">
          <StageStatusBadge status={stage.status} />
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-zinc-500" />
          )}
        </span>
      </button>
      {expanded ? (
        <div className="space-y-4 border-t border-white/10 bg-zinc-950/40 p-4">
          {stage.error ? (
            <p className="rounded-md border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">
              {stage.error}
            </p>
          ) : null}
          <StageVisual stage={stage} data={data} />
          <div className="grid gap-3 lg:grid-cols-2">
            <JsonBlock label="Inputs" value={stage.inputs} />
            <JsonBlock label="Outputs" value={stage.outputs} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function StageVisual({
  stage,
  data,
}: {
  stage: DebugStage;
  data: VideoDebugPayload;
}) {
  if (stage.id === "probing_video" || stage.id === "normalizing") {
    return <MediaStageVisual data={data} />;
  }

  if (stage.id === "detecting_scenes") {
    return <SceneStageVisual data={data} />;
  }

  if (stage.id === "detecting_speech") {
    return <SpeechStageVisual data={data} stage={stage} />;
  }

  if (stage.id === "extracting_clips" || stage.id === "generating_thumbnails") {
    return <DebugClipGallery clips={data.media.clips} />;
  }

  if (stage.id === "running_face_detection") {
    return <FaceStageVisual clips={data.media.clips} />;
  }

  if (stage.id === "scoring_quality") {
    return <QualityStageVisual clips={data.media.clips} />;
  }

  if (stage.id === "transcribing") {
    return <TranscriptStageVisual clips={data.media.clips} />;
  }

  if (stage.id === "indexing_embeddings") {
    return <EmbeddingStageVisual clips={data.media.clips} />;
  }

  return (
    <p className="rounded-md border border-white/10 bg-white/[0.025] p-3 text-xs text-zinc-500">
      This stage has no visual artifact yet.
    </p>
  );
}

function MediaStageVisual({ data }: { data: VideoDebugPayload }) {
  const items = [
    { label: "Raw upload", url: data.media.rawUrl, type: "video" },
    { label: "Normalized copy", url: data.media.normalizedUrl, type: "video" },
    { label: "Cover thumbnail", url: data.media.coverThumbnailUrl, type: "image" },
  ];

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="overflow-hidden rounded-md border border-white/10 bg-black/30">
          <div className="relative aspect-video bg-zinc-950">
            {item.url && item.type === "video" ? (
              <video src={item.url} controls preload="metadata" className="h-full w-full object-cover" />
            ) : item.url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.url} alt="" className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center text-zinc-700">
                <FileVideo className="h-6 w-6" />
              </div>
            )}
          </div>
          <p className="border-t border-white/10 px-3 py-2 text-xs font-medium text-zinc-300">
            {item.label}
          </p>
        </div>
      ))}
    </div>
  );
}

function SpeechStageVisual({
  data,
  stage,
}: {
  data: VideoDebugPayload;
  stage: DebugStage;
}) {
  const track = data.timeline.tracks.find((item) => item.id === "speech");
  const activeCoverage = numberFromPath(stage.outputs, "active_coverage");
  const threshold = numberFromPath(stage.outputs, "threshold");

  return (
    <div className="rounded-md border border-cyan-400/15 bg-cyan-400/[0.04] p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 text-sm font-medium text-cyan-100">
          <Waves className="h-4 w-4" />
          Speech regions over scene clips
        </div>
        <div className="flex gap-2 text-xs text-cyan-200/75">
          {activeCoverage != null ? <span>{Math.round(activeCoverage * 100)}% active</span> : null}
          {threshold != null ? <span>threshold {threshold.toFixed(4)}</span> : null}
        </div>
      </div>
      {track ? <TimelineTrack duration={data.timeline.durationSeconds} track={track} /> : null}
    </div>
  );
}

function SceneStageVisual({ data }: { data: VideoDebugPayload }) {
  const track = data.timeline.tracks.find((item) => item.id === "clips");

  return (
    <div className="rounded-md border border-violet-400/15 bg-violet-400/[0.04] p-3">
      <div className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-violet-100">
        <Scissors className="h-4 w-4" />
        Scene boundaries cover the full video
      </div>
      {track ? <TimelineTrack duration={data.timeline.durationSeconds} track={track} /> : null}
    </div>
  );
}

function FaceStageVisual({ clips }: { clips: DebugMediaClip[] }) {
  const withSamples = clips.filter((clip) => getFaceSamples(clip).length);

  return (
    <div className="space-y-3 rounded-md border border-amber-400/15 bg-amber-400/[0.04] p-3">
      <div className="inline-flex items-center gap-2 text-sm font-medium text-amber-100">
        <ScanFace className="h-4 w-4" />
        Face detection samples
      </div>
      {withSamples.length ? (
        <div className="space-y-2">
          {withSamples.map((clip) => (
            <div key={clip.id} className="rounded-md border border-white/10 bg-black/25 p-2">
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="font-mono text-zinc-300">{clip.id}</span>
                <span className="text-zinc-500">
                  {formatScore(clip.faceScore)} face score
                </span>
              </div>
              <FaceSampleStrip samples={getFaceSamples(clip)} />
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-zinc-500">No face samples have been emitted yet.</p>
      )}
    </div>
  );
}

function QualityStageVisual({ clips }: { clips: DebugMediaClip[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {clips.map((clip) => (
        <div key={clip.id} className="rounded-md border border-white/10 bg-black/25 p-3">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="font-mono text-xs text-zinc-300">{clip.id}</span>
            {clip.quality ? (
              <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]", qualityChipClass(clip.quality))}>
                {qualityLabel(clip.quality)}
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-4 gap-2">
            <MiniScore label="Quality" value={clip.qualityScore} />
          <MiniScore label="Speech" value={clip.speechScore} />
          <MiniScore label="Face" value={clip.faceScore} />
          <MiniScore label="Audio" value={clip.audioScore} />
        </div>
        <div className="grid grid-cols-3 gap-2 text-[11px] text-zinc-500">
          <span>{clip.hasSpeech ? "speech" : "no speech"}</span>
          <span>{speakerLabel(clip.speakerBucket)}</span>
          <span>{clip.faceAxis ?? "unknown"}</span>
        </div>
          {clip.tags?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {clip.tags.slice(0, 6).map((tag) => (
                <span key={tag} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-zinc-400">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function EmbeddingStageVisual({ clips }: { clips: DebugMediaClip[] }) {
  const counts = clips.reduce<Record<string, number>>((acc, clip) => {
    const status = clip.embeddingStatus ?? "pending";
    acc[status] = (acc[status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="rounded-md border border-sky-400/15 bg-sky-400/[0.04] p-3">
      <div className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-sky-100">
        <Gauge className="h-4 w-4" />
        Background semantic embedding index
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.entries(counts).map(([status, count]) => (
          <span key={status} className="rounded-md border border-white/10 bg-black/25 px-2 py-1 text-xs text-zinc-300">
            {status}: {count}
          </span>
        ))}
      </div>
    </div>
  );
}

function TranscriptStageVisual({ clips }: { clips: DebugMediaClip[] }) {
  const transcriptClips = clips.filter((clip) => clip.transcript || clip.quality);

  return (
    <div className="space-y-2">
      {transcriptClips.length ? (
        transcriptClips.map((clip) => (
          <div key={clip.id} className="rounded-md border border-white/10 bg-black/25 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs text-zinc-500">
              <Captions className="h-3.5 w-3.5" />
              <span className="font-mono text-zinc-300">{clip.id}</span>
              <span>{qualityLabel(clip.quality)}</span>
            </div>
            <p className="text-sm text-zinc-300">
              {clip.transcript || "No transcript emitted for this clip."}
            </p>
          </div>
        ))
      ) : (
        <p className="rounded-md border border-white/10 bg-white/[0.025] p-3 text-xs text-zinc-500">
          Transcripts will show here for good and needs-review clips when ASR is enabled.
        </p>
      )}
    </div>
  );
}

function FaceSampleStrip({ samples }: { samples: FaceSample[] }) {
  const maxTime = Math.max(1, ...samples.map((sample) => sample.time ?? 0));

  return (
    <div className="relative h-6 rounded-sm border border-white/10 bg-zinc-950/70">
      {samples.map((sample, index) => {
        const left = Math.max(0, Math.min(98, ((sample.time ?? index) / maxTime) * 100));
        return (
          <span
            key={`${sample.frameIndex}-${index}`}
            title={`${sample.faceCount ?? 0} faces at ${formatDuration(sample.time ?? 0)}`}
            className={cn(
              "absolute top-1/2 h-4 w-1 -translate-y-1/2 rounded-full",
              sample.hasFace ? "bg-amber-300" : "bg-zinc-700",
            )}
            style={{ left: `${left}%` }}
          />
        );
      })}
    </div>
  );
}

function MiniScore({ label, value }: { label: string; value?: number }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.025] px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-600">{label}</p>
      <p className="mt-1 text-xs font-semibold text-zinc-200">{formatScore(value)}</p>
    </div>
  );
}

function DebugMetric({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.025] px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </p>
      <p
        className={cn(
          "mt-1.5 truncate text-sm text-zinc-100",
          mono && "font-mono text-xs text-zinc-300",
        )}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}

function RawJsonPanel({
  open,
  onToggle,
  data,
}: {
  open: boolean;
  onToggle: () => void;
  data: VideoDebugPayload;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.025]">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-xs text-zinc-400 transition hover:text-zinc-200"
      >
        <span className="inline-flex items-center gap-2">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Raw JSON payload
        </span>
        <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-600">
          GET /api/videos/:videoId/debug
        </span>
      </button>
      {open ? (
        <pre className="max-h-[28rem] overflow-auto border-t border-white/10 bg-zinc-950/60 p-4 text-[11px] leading-relaxed text-zinc-200">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/40">
      <p className="border-b border-white/5 px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </p>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words px-3 py-2.5 text-[11px] leading-relaxed text-zinc-200">
        {prettyJson(value)}
      </pre>
    </div>
  );
}

function StageIcon({
  stageId,
  status,
}: {
  stageId: string;
  status: DebugStageStatus;
}) {
  if (status === "complete") return <Check className="h-4 w-4 shrink-0 text-emerald-400" />;
  if (status === "running") return <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan-300" />;
  if (status === "failed") return <CircleAlert className="h-4 w-4 shrink-0 text-rose-400" />;

  const className = "h-4 w-4 shrink-0 text-zinc-600";
  if (stageId === "detecting_speech") return <Waves className={className} />;
  if (stageId === "extracting_clips") return <Scissors className={className} />;
  if (stageId === "generating_thumbnails") return <ImageIcon className={className} />;
  if (stageId === "running_face_detection") return <ScanFace className={className} />;
  if (stageId === "scoring_quality") return <Gauge className={className} />;
  if (stageId === "transcribing") return <Captions className={className} />;
  if (stageId === "normalizing" || stageId === "probing_video") return <FileVideo className={className} />;
  return <Circle className={className} />;
}

function StageStatusBadge({ status }: { status: DebugStageStatus }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em]",
        status === "complete" && "bg-emerald-500/15 text-emerald-200",
        status === "running" && "bg-cyan-500/15 text-cyan-200",
        status === "failed" && "bg-rose-500/15 text-rose-200",
        status === "skipped" && "bg-zinc-500/15 text-zinc-300",
        status === "pending" && "bg-white/5 text-zinc-400",
      )}
    >
      {status}
    </span>
  );
}

function segmentClassName(segment: DebugTimelineSegment) {
  if (segment.kind === "speech") return "border-cyan-300/40 bg-cyan-300/30 text-cyan-50";
  if (segment.kind === "clip") return "border-violet-300/40 bg-violet-300/25 text-violet-50";
  if (segment.kind === "face") return "border-amber-300/40 bg-amber-300/30 text-amber-50";
  if (segment.kind === "embedding") return "border-sky-300/40 bg-sky-300/25 text-sky-50";
  if (segment.quality === "good") return "border-emerald-300/40 bg-emerald-300/30 text-emerald-50";
  if (segment.quality === "review") return "border-yellow-300/40 bg-yellow-300/30 text-yellow-50";
  if (segment.quality === "rejected") return "border-rose-300/40 bg-rose-300/30 text-rose-50";
  return "border-zinc-300/30 bg-zinc-300/20 text-zinc-100";
}

function qualityChipClass(quality?: string) {
  if (quality === "good") return "bg-emerald-500/20 text-emerald-100";
  if (quality === "review") return "bg-yellow-500/20 text-yellow-100";
  if (quality === "rejected") return "bg-rose-500/20 text-rose-100";
  return "bg-white/10 text-zinc-200";
}

function qualityLabel(quality?: string) {
  if (quality === "good") return "Good";
  if (quality === "review") return "Needs Review";
  if (quality === "rejected") return "Rejected";
  return quality ?? "Pending";
}

function speakerLabel(value?: string) {
  if (value === "0") return "0 speakers";
  if (value === "1") return "1 speaker";
  if (value === "2plus") return "2+ speakers";
  return value ?? "unknown";
}

function formatRange(start?: number, end?: number) {
  if (start == null || end == null) return "-";
  return `${formatDuration(start)} -> ${formatDuration(end)}`;
}

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function expandRunningStage(
  current: Record<string, boolean>,
  stages: DebugStage[],
) {
  const active = stages.find((stage) => stage.status === "running" || stage.status === "failed");
  if (!active || current[active.id] != null) return current;
  return { ...current, [active.id]: true };
}

type FaceSample = {
  frameIndex?: number;
  time?: number;
  absoluteTime?: number;
  hasFace?: boolean;
  faceCount?: number;
  largestFaceSizeRatio?: number;
};

function getFaceSamples(clip: DebugMediaClip): FaceSample[] {
  const samples = clip.faceStats?.samples;
  if (!Array.isArray(samples)) return [];
  return samples.filter((sample): sample is FaceSample => Boolean(sample && typeof sample === "object"));
}

function numberFromPath(source: Record<string, unknown>, key: string) {
  const value = source[key];
  return typeof value === "number" ? value : undefined;
}
