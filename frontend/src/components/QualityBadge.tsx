import type { ClipQuality, JobStatus } from "@/lib/types";
import { cn, qualityLabels, statusLabels } from "@/lib/utils";

type QualityBadgeProps = {
  quality?: ClipQuality;
  status?: JobStatus;
  children?: React.ReactNode;
  className?: string;
};

const toneByQuality: Record<ClipQuality, string> = {
  good: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  review: "border-amber-400/35 bg-amber-400/10 text-amber-200",
  rejected: "border-zinc-500/40 bg-zinc-500/10 text-zinc-300",
};

const toneByStatus: Record<JobStatus, string> = {
  queued: "border-zinc-400/30 bg-zinc-400/10 text-zinc-200",
  uploading: "border-cyan-400/35 bg-cyan-400/10 text-cyan-200",
  processing: "border-sky-400/35 bg-sky-400/10 text-sky-200",
  complete: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  failed: "border-rose-400/35 bg-rose-400/10 text-rose-200",
};

export function QualityBadge({
  quality,
  status,
  children,
  className,
}: QualityBadgeProps) {
  const tone = quality
    ? toneByQuality[quality]
    : status
      ? toneByStatus[status]
      : "border-white/10 bg-white/5 text-zinc-200";
  const label =
    children ??
    (quality ? qualityLabels[quality] : status ? statusLabels[status] : "Unknown");

  return (
    <span
      className={cn(
        "inline-flex h-7 items-center rounded-md border px-2.5 text-xs font-medium",
        tone,
        className,
      )}
    >
      {label}
    </span>
  );
}
