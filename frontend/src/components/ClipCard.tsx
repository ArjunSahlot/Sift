"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import type { ClipItem } from "@/lib/types";
import { formatClipRange, formatDuration, formatScore } from "@/lib/utils";

type ClipCardProps = {
  clip: ClipItem;
  /** When set and matches `clip.videoId`, the source link is omitted (same page). */
  currentVideoId?: string;
};

export function ClipCard({ clip, currentVideoId }: ClipCardProps) {
  const showSourceLink = currentVideoId !== clip.videoId;
  const hasClipMedia = Boolean(clip.clipUrl?.trim());
  const hasTranscriptText = Boolean(clip.transcript?.trim());

  return (
    <article className="overflow-hidden rounded-xl border border-white/10 bg-panel shadow-lg shadow-black/25 transition hover:border-cyan-400/20">
      <div className="relative aspect-video overflow-hidden bg-zinc-950">
        {hasClipMedia ? (
          <video
            className="h-full w-full object-cover"
            controls
            playsInline
            preload="metadata"
            poster={clip.thumbnailUrl}
            src={clip.clipUrl}
            aria-label={`Clip from ${clip.sourceVideoTitle}`}
          />
        ) : clip.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={clip.thumbnailUrl} alt="" className="h-full w-full object-cover opacity-90" />
        ) : (
          <div className="sift-grid h-full w-full" />
        )}
        <div className="pointer-events-none absolute left-3 top-3 max-w-[min(100%-1.5rem,18rem)]">
          <span className="inline-block rounded-md bg-black/55 px-2 py-1 text-[11px] font-medium tabular-nums text-white backdrop-blur-sm">
            {formatClipRange(clip.startTime, clip.endTime)}
            <span className="text-white/65"> · </span>
            {formatDuration(clip.duration)}
          </span>
        </div>
      </div>

      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="min-w-0 flex-1 text-base font-semibold leading-snug tracking-tight text-zinc-50">
            {clip.sourceVideoTitle}
          </h3>
          {showSourceLink ? (
            <Link
              href={`/videos/${clip.videoId}`}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-cyan-200/95 transition hover:border-cyan-400/35 hover:bg-cyan-500/10 hover:text-cyan-50"
            >
              Source video
              <ExternalLink className="h-3.5 w-3.5 opacity-80" aria-hidden />
            </Link>
          ) : null}
        </div>

        <dl className="flex flex-wrap gap-1.5">
          <ClipStat label="Transcript" value={hasTranscriptText ? "Yes" : "No"} />
          <ClipStat label="Match" value={formatScore(clip.semanticScore)} />
          <ClipStat label="Quality" value={formatScore(clip.qualityScore)} />
          <ClipStat label="Speakers" value={speakersLabel(clip.speakerBucket)} />
        </dl>
      </div>
    </article>
  );
}

function ClipStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/[0.08] bg-white/[0.025] px-2 py-1">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-0.5 text-xs font-medium tabular-nums text-zinc-200">{value}</dd>
    </div>
  );
}

function speakersLabel(value?: string) {
  if (value === "0") return "0";
  if (value === "1") return "1";
  if (value === "2plus") return "2+";
  return value ?? "—";
}
