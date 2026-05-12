import { Loader2 } from "lucide-react";

type LoadingStateProps = {
  label: string;
};

export function LoadingState({ label }: LoadingStateProps) {
  return (
    <div className="grid min-h-48 place-items-center rounded-lg border border-white/10 bg-panel p-8 text-center">
      <div>
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-cyan-200" />
        <p className="mt-4 text-sm font-medium text-zinc-300">{label}</p>
      </div>
    </div>
  );
}
