import { formatScore } from "@/lib/utils";

type ScorePillProps = {
  label: string;
  score?: number;
};

export function ScorePill({ label, score }: ScorePillProps) {
  return (
    <span className="inline-flex h-7 items-center gap-1 rounded-md border border-white/10 bg-white/[0.04] px-2 text-xs text-zinc-300">
      <span className="text-zinc-500">{label}</span>
      <span className="font-medium text-zinc-100">{formatScore(score)}</span>
    </span>
  );
}
