import type { JobStatus } from "@/lib/types";
import { cn, statusLabels } from "@/lib/utils";

type StatusBadgeProps = {
  status?: JobStatus;
  children?: React.ReactNode;
  className?: string;
};

const toneByStatus: Record<JobStatus, string> = {
  queued: "border-zinc-400/30 bg-zinc-400/10 text-zinc-200",
  uploading: "border-cyan-400/35 bg-cyan-400/10 text-cyan-200",
  processing: "border-sky-400/35 bg-sky-400/10 text-sky-200",
  complete: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  failed: "border-rose-400/35 bg-rose-400/10 text-rose-200",
};

export function StatusBadge({ status, children, className }: StatusBadgeProps) {
  const tone = status
    ? toneByStatus[status]
    : "border-white/10 bg-white/5 text-zinc-200";
  const label = children ?? (status ? statusLabels[status] : "Unknown");

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
