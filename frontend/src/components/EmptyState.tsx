import { Inbox } from "lucide-react";

type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="grid min-h-64 place-items-center rounded-lg border border-dashed border-white/15 bg-white/[0.025] p-8 text-center">
      <div>
        <div className="mx-auto grid h-11 w-11 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-zinc-400">
          <Inbox className="h-5 w-5" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-zinc-100">{title}</h3>
        <p className="mt-2 max-w-md text-sm leading-6 text-zinc-400">{description}</p>
      </div>
    </div>
  );
}
