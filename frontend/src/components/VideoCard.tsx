"use client";

import { AlertCircle, Clock3, FileVideo, Play, ScissorsLineDashed } from "lucide-react";
import type { KeyboardEvent } from "react";
import type { VideoItem } from "@/lib/types";
import { cn, formatDate, formatDuration } from "@/lib/utils";
import { ProcessingBadge } from "./ProcessingBadge";
import { ProgressStage } from "./ProgressStage";

type VideoCardProps = {
  video: VideoItem;
  onClick?: () => void;
};

export function VideoCard({ video, onClick }: VideoCardProps) {
  const isInteractive = Boolean(onClick);

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (!isInteractive) {
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClick?.();
    }
  }

  return (
    <article
      role={isInteractive ? "button" : undefined}
      tabIndex={isInteractive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className={cn(
        "group overflow-hidden rounded-lg border border-white/10 bg-panel transition",
        isInteractive && "cursor-pointer hover:-translate-y-0.5 hover:border-cyan-300/35 hover:shadow-glow",
      )}
    >
      <div className="relative aspect-video overflow-hidden bg-zinc-900">
        {video.videoUrl ? (
          <video src={video.videoUrl} muted playsInline className="h-full w-full object-cover" />
        ) : video.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={video.thumbnailUrl}
            alt=""
            className="h-full w-full object-cover opacity-85 transition duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="sift-grid grid h-full w-full place-items-center">
            <FileVideo className="h-10 w-10 text-zinc-500" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
        <div className="absolute left-3 top-3">
          <ProcessingBadge video={video} />
        </div>
        <div className="absolute bottom-3 left-3 flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-white text-zinc-950 shadow-sm">
            {video.status === "failed" ? (
              <AlertCircle className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4 fill-current" />
            )}
          </span>
          <span className="rounded-md bg-black/55 px-2 py-1 text-xs font-medium text-white backdrop-blur">
            {formatDuration(video.durationSeconds)}
          </span>
        </div>
      </div>
      <div className="space-y-4 p-4">
        <div>
          <h3 className="line-clamp-1 text-base font-semibold text-zinc-50">{video.title}</h3>
          <p className="mt-1 line-clamp-1 text-sm text-zinc-500">{video.filename}</p>
        </div>
        <div className="grid grid-cols-1 gap-2 text-xs">
          <Metric label="Clips extracted" value={video.clipsFound ?? 0} />
        </div>
        <ProgressStage video={video} compact />
        {video.error ? (
          <p className="rounded-md border border-rose-400/20 bg-rose-400/10 p-2 text-xs leading-5 text-rose-100">
            {video.error}
          </p>
        ) : null}
        <div className="flex items-center justify-between gap-3 border-t border-white/10 pt-3 text-xs text-zinc-500">
          <span className="inline-flex items-center gap-1.5">
            <Clock3 className="h-3.5 w-3.5" />
            {formatDate(video.createdAt)}
          </span>
          <span className="inline-flex items-center gap-1.5 capitalize">
            <ScissorsLineDashed className="h-3.5 w-3.5" />
            {video.sourceType}
          </span>
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.035] px-2 py-2">
      <p className="text-zinc-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-zinc-100">{value}</p>
    </div>
  );
}
