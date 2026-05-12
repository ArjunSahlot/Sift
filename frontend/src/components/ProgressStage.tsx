import type { VideoItem } from "@/lib/types";
import { cn, stageLabel } from "@/lib/utils";

type ProgressStageProps = {
  video: VideoItem;
  compact?: boolean;
};

export function ProgressStage({ video, compact = false }: ProgressStageProps) {
  const progress = Math.min(100, Math.max(0, video.progressPercent ?? 0));

  if (!["queued", "uploading", "processing"].includes(video.status)) {
    return null;
  }

  return (
    <div className={cn("space-y-2", compact && "space-y-1.5")}>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="truncate text-zinc-400">{stageLabel(video.progressStage)}</span>
        <span className="font-medium text-zinc-200">{progress}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-cyan-300 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      {typeof video.clipsFound === "number" ? (
        <p className="text-xs text-zinc-500">{video.clipsFound} clips found so far</p>
      ) : null}
    </div>
  );
}
