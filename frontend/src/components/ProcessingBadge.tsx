import type { VideoItem } from "@/lib/types";
import { stageLabel } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";

type ProcessingBadgeProps = {
  video: VideoItem;
};

export function ProcessingBadge({ video }: ProcessingBadgeProps) {
  return (
    <div className="flex items-center gap-2">
      <StatusBadge status={video.status} />
      {video.status === "processing" || video.status === "uploading" ? (
        <span className="truncate text-xs text-zinc-400">
          {stageLabel(video.progressStage)}
        </span>
      ) : null}
    </div>
  );
}
