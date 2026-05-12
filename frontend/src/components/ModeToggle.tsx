"use client";

import { Database, UploadCloud } from "lucide-react";
import type { Mode } from "@/lib/types";
import { cn } from "@/lib/utils";

type ModeToggleProps = {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
};

const modes: Array<{ id: Mode; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: "upload", label: "Upload", icon: UploadCloud },
  { id: "query", label: "Query", icon: Database },
];

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="inline-flex rounded-lg border border-white/10 bg-white/[0.04] p-1">
      {modes.map((item) => {
        const Icon = item.icon;
        const active = item.id === mode;

        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onModeChange(item.id)}
            className={cn(
              "inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-zinc-400 transition",
              active && "bg-white text-zinc-950 shadow-sm",
              !active && "hover:bg-white/5 hover:text-zinc-100",
            )}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
