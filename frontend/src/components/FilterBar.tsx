"use client";

import { CheckCircle2, FileText, SlidersHorizontal, Volume2, UserRoundCheck } from "lucide-react";
import type { QueryFilters } from "@/lib/types";
import { cn } from "@/lib/utils";

type FilterBarProps = {
  filters: QueryFilters;
  onChange: (filters: QueryFilters) => void;
};

const qualityOptions = [
  { value: "any", label: "Any" },
  { value: "good", label: "Good" },
  { value: "review", label: "Needs Review" },
  { value: "rejected", label: "Rejected" },
] as const;

const typeOptions = [
  { value: "any", label: "Any" },
  { value: "speaking", label: "Speaking Clips" },
  { value: "human-visible", label: "Human Visible" },
  { value: "clean-audio", label: "Clean Audio" },
  { value: "single-speaker", label: "Single Speaker" },
] as const;

const durationOptions = [
  { value: "any", label: "Any" },
  { value: "short", label: "< 10s" },
  { value: "medium", label: "10-20s" },
  { value: "long", label: "> 20s" },
] as const;

export function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="space-y-4 rounded-lg border border-white/10 bg-panel p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
        <SlidersHorizontal className="h-4 w-4 text-cyan-200" />
        Filters
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <OptionGroup
          label="Quality"
          value={filters.quality}
          options={qualityOptions}
          onSelect={(quality) => onChange({ ...filters, quality })}
        />
        <OptionGroup
          label="Type"
          value={filters.type}
          options={typeOptions}
          onSelect={(type) => onChange({ ...filters, type })}
        />
        <OptionGroup
          label="Duration"
          value={filters.duration}
          options={durationOptions}
          onSelect={(duration) => onChange({ ...filters, duration })}
        />
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Toggle
          label="Face visible"
          icon={UserRoundCheck}
          checked={filters.faceVisible}
          onChange={(faceVisible) => onChange({ ...filters, faceVisible })}
        />
        <Toggle
          label="Audio clean"
          icon={Volume2}
          checked={filters.audioClean}
          onChange={(audioClean) => onChange({ ...filters, audioClean })}
        />
        <Toggle
          label="Has transcript"
          icon={FileText}
          checked={filters.hasTranscript}
          onChange={(hasTranscript) => onChange({ ...filters, hasTranscript })}
        />
        <Toggle
          label="Only exportable clips"
          icon={CheckCircle2}
          checked={filters.exportableOnly}
          onChange={(exportableOnly) => onChange({ ...filters, exportableOnly })}
        />
      </div>
    </div>
  );
}

type OptionGroupProps<T extends string> = {
  label: string;
  value: T;
  options: ReadonlyArray<{ value: T; label: string }>;
  onSelect: (value: T) => void;
};

function OptionGroup<T extends string>({
  label,
  value,
  options,
  onSelect,
}: OptionGroupProps<T>) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const active = option.value === value;

          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onSelect(option.value)}
              className={cn(
                "h-8 rounded-md border border-white/10 px-2.5 text-xs font-medium text-zinc-400 transition",
                active && "border-cyan-300/40 bg-cyan-300/10 text-cyan-100",
                !active && "hover:border-white/20 hover:bg-white/[0.04] hover:text-zinc-100",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Toggle({
  label,
  icon: Icon,
  checked,
  onChange,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={cn(
        "flex h-10 items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 text-sm text-zinc-400 transition",
        checked && "border-emerald-300/35 bg-emerald-300/10 text-emerald-100",
      )}
    >
      <span className="inline-flex min-w-0 items-center gap-2">
        <Icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{label}</span>
      </span>
      <span
        className={cn(
          "h-4 w-4 shrink-0 rounded border border-white/20",
          checked && "border-emerald-200 bg-emerald-200",
        )}
      />
    </button>
  );
}
