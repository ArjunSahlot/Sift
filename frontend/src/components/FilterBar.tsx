"use client";

import { SlidersHorizontal } from "lucide-react";
import type { QueryFilters } from "@/lib/types";
import { cn } from "@/lib/utils";

type FilterBarProps = {
  filters: QueryFilters;
  onChange: (filters: QueryFilters) => void;
};

const durationOptions = [
  { value: "any", label: "Any" },
  { value: "<1", label: "< 1s" },
  { value: "<5", label: "< 5s" },
  { value: "<10", label: "< 10s" },
  { value: "10+", label: "10+ s" },
] as const;

const speakerOptions = [
  { value: "any", label: "Any" },
  { value: "0", label: "0 speakers" },
  { value: "1", label: "1 speaker" },
  { value: "2plus", label: "2+ speakers" },
] as const;

const axisOptions = [
  { value: "any", label: "Any" },
  { value: "on-axis", label: "On-axis" },
  { value: "off-axis", label: "Off-axis" },
  { value: "mixed", label: "Mixed" },
] as const;

const speechOptions = [
  { value: "any", label: "Any" },
  { value: "detected", label: "Speech detected" },
  { value: "none", label: "No speech" },
] as const;

const transcriptOptions = [
  { value: "any", label: "Any" },
  { value: "has", label: "Has transcript" },
  { value: "none", label: "No transcript" },
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
          label="Duration"
          value={filters.duration}
          options={durationOptions}
          onSelect={(duration) => onChange({ ...filters, duration })}
        />
        <OptionGroup
          label="Speakers"
          value={filters.speaker}
          options={speakerOptions}
          onSelect={(speaker) =>
            onChange({
              ...filters,
              speaker,
              faceAxis: speaker === "1" ? filters.faceAxis : "any",
            })
          }
        />
        <OptionGroup
          label="Face axis"
          value={filters.faceAxis}
          options={axisOptions}
          disabled={filters.speaker !== "1"}
          helper={filters.speaker === "1" ? undefined : "Select 1 speaker first"}
          onSelect={(faceAxis) => onChange({ ...filters, faceAxis })}
        />
        <OptionGroup
          label="Speech"
          value={filters.speech}
          options={speechOptions}
          onSelect={(speech) => onChange({ ...filters, speech })}
        />
        <OptionGroup
          label="Transcript"
          value={filters.transcript}
          options={transcriptOptions}
          onSelect={(transcript) => onChange({ ...filters, transcript })}
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
  disabled?: boolean;
  helper?: string;
};

function OptionGroup<T extends string>({
  label,
  value,
  options,
  onSelect,
  disabled = false,
  helper,
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
              disabled={disabled}
              className={cn(
                "h-8 rounded-md border border-white/10 px-2.5 text-xs font-medium text-zinc-400 transition",
                active && "border-cyan-300/40 bg-cyan-300/10 text-cyan-100",
                !active && "hover:border-white/20 hover:bg-white/[0.04] hover:text-zinc-100",
                disabled && "cursor-not-allowed opacity-45 hover:border-white/10 hover:bg-transparent hover:text-zinc-400",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      {helper ? <p className="text-[11px] text-zinc-600">{helper}</p> : null}
    </div>
  );
}
