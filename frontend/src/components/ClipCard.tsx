"use client";

import { Check, Eye, Play, X } from "lucide-react";
import type { ClipItem, ClipQuality } from "@/lib/types";
import { cn, formatClipRange, formatDuration } from "@/lib/utils";
import { QualityBadge } from "./QualityBadge";
import { ScorePill } from "./ScorePill";

type ClipCardProps = {
  clip: ClipItem;
  reviewControls?: boolean;
  onQualityChange?: (clipId: string, quality: ClipQuality) => void;
};

export function ClipCard({ clip, reviewControls = false, onQualityChange }: ClipCardProps) {
  return (
    <article className="overflow-hidden rounded-lg border border-white/10 bg-panel transition hover:border-cyan-300/30">
      <div className="relative aspect-video overflow-hidden bg-zinc-900">
        {clip.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={clip.thumbnailUrl}
            alt=""
            className="h-full w-full object-cover opacity-85"
          />
        ) : (
          <div className="sift-grid h-full w-full" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
        <div className="absolute left-3 top-3">
          <QualityBadge quality={clip.quality} />
        </div>
        <button
          type="button"
          className="absolute left-1/2 top-1/2 grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-zinc-950 shadow-sm transition hover:scale-105"
          aria-label="Preview clip"
        >
          <Play className="h-4 w-4 fill-current" />
        </button>
        <span className="absolute bottom-3 left-3 rounded-md bg-black/60 px-2 py-1 text-xs font-medium text-white backdrop-blur">
          {formatClipRange(clip.startTime, clip.endTime)}
        </span>
        <span className="absolute bottom-3 right-3 rounded-md bg-black/60 px-2 py-1 text-xs font-medium text-white backdrop-blur">
          {formatDuration(clip.duration)}
        </span>
      </div>
      <div className="space-y-4 p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
            Source Video
          </p>
          <h3 className="mt-1 line-clamp-1 text-base font-semibold text-zinc-50">
            {clip.sourceVideoTitle}
          </h3>
        </div>
        {clip.transcript ? (
          <p className="line-clamp-3 text-sm leading-6 text-zinc-300">
            <span className="text-zinc-500">Transcript: </span>
            &ldquo;{clip.transcript}&rdquo;
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <ScorePill label="Speech" score={clip.speechScore} />
          <ScorePill label="Face" score={clip.faceScore} />
          <ScorePill label="Audio" score={clip.audioScore} />
          <ScorePill label="Semantic" score={clip.semanticScore} />
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400">
          <Meta label="Speech" value={clip.hasSpeech ? "detected" : "none"} />
          <Meta label="Speakers" value={speakerLabel(clip.speakerBucket)} />
          <Meta label="Face axis" value={clip.faceAxis ?? "unknown"} />
          <Meta label="Embeddings" value={clip.embeddingStatus ?? "pending"} />
        </div>
        {clip.bestFrameUrl ? (
          <div className="overflow-hidden rounded-md border border-white/10 bg-black/30">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={clip.bestFrameUrl} alt="" className="h-24 w-full object-cover" />
            <p className="px-2 py-1 text-[11px] text-zinc-500">
              Best semantic frame
              {clip.bestFrameTimeSeconds != null
                ? ` @ ${formatDuration(clip.bestFrameTimeSeconds)}`
                : ""}
            </p>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-1.5">
          {clip.tags.slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="rounded-md border border-white/10 bg-white/[0.035] px-2 py-1 text-xs text-zinc-400"
            >
              {tag}
            </span>
          ))}
        </div>
        {clip.rejectionReasons?.length ? (
          <div className="rounded-md border border-rose-400/20 bg-rose-400/10 p-3">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-rose-200">
              Rejection reasons
            </p>
            <p className="mt-2 text-sm text-rose-100">{clip.rejectionReasons.join(", ")}</p>
          </div>
        ) : null}
        {reviewControls ? (
          <div className="grid grid-cols-3 gap-2 border-t border-white/10 pt-3">
            <ReviewButton
              label="Accept"
              icon={Check}
              active={clip.quality === "good"}
              onClick={() => onQualityChange?.(clip.id, "good")}
            />
            <ReviewButton
              label="Needs Review"
              icon={Eye}
              active={clip.quality === "review"}
              onClick={() => onQualityChange?.(clip.id, "review")}
            />
            <ReviewButton
              label="Reject"
              icon={X}
              active={clip.quality === "rejected"}
              onClick={() => onQualityChange?.(clip.id, "rejected")}
            />
          </div>
        ) : null}
      </div>
    </article>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.025] px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-600">{label}</p>
      <p className="mt-1 truncate text-xs text-zinc-300">{value}</p>
    </div>
  );
}

function speakerLabel(value?: string) {
  if (value === "0") return "0";
  if (value === "1") return "1";
  if (value === "2plus") return "2+";
  return value ?? "unknown";
}

function ReviewButton({
  label,
  icon: Icon,
  active,
  onClick,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "inline-flex h-9 min-w-0 items-center justify-center gap-1.5 rounded-md border border-white/10 px-2 text-xs font-medium text-zinc-400 transition hover:bg-white/[0.04] hover:text-zinc-100",
        active && "border-cyan-300/35 bg-cyan-300/10 text-cyan-100",
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  );
}
