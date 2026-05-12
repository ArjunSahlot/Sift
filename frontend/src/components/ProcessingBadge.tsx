import type { VideoItem } from "@/lib/types";
import { stageLabel } from "@/lib/utils";
import { QualityBadge } from "./QualityBadge";

type ProcessingBadgeProps = {
  video: VideoItem;
};

export function ProcessingBadge({ video }: ProcessingBadgeProps) {
  return (
    <div className="flex items-center gap-2">
      <QualityBadge status={video.status} />
      {video.status === "processing" || video.status === "uploading" ? (
        <span className="truncate text-xs text-zinc-400">
          {stageLabel(video.progressStage)}
        </span>
      ) : null}
    </div>
  );
}
