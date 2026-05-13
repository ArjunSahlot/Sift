"use client";

import { Download, Loader2, Package, X } from "lucide-react";
import { useState } from "react";
import type { ExportResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export type ExportSettings = {
  include: {
    includeClips: boolean;
    includeThumbnails: boolean;
    includeManifest: boolean;
    includeSummary: boolean;
  };
  metadata: {
    transcript: boolean;
    scores: boolean;
    tags: boolean;
    source: boolean;
    rejectionReasons: boolean;
  };
};

type ExportModalProps = {
  open: boolean;
  onClose: () => void;
  mode: "query" | "video";
  resultCount?: number;
  onGenerate: (settings: ExportSettings) => Promise<ExportResponse>;
};

type ExportStage = "settings" | "preparing" | "complete";

const includeOptions = [
  ["includeClips", "Video clips"],
  ["includeThumbnails", "Thumbnails"],
  ["includeManifest", "Manifest JSONL"],
  ["includeSummary", "Summary report"],
] as const;


const metadataOptions = [
  ["transcript", "Transcript"],
  ["scores", "Quality scores"],
  ["tags", "Tags"],
  ["source", "Source video info"],
  ["rejectionReasons", "Rejection reasons"],
] as const;

export function ExportModal({
  open,
  onClose,
  mode,
  resultCount = 0,
  onGenerate,
}: ExportModalProps) {
  const [stage, setStage] = useState<ExportStage>("settings");
  const [downloadUrl, setDownloadUrl] = useState<string>();
  const [error, setError] = useState("");
  const [include, setInclude] = useState({
    includeClips: true,
    includeThumbnails: true,
    includeManifest: true,
    includeSummary: true,
  });
  const [metadata, setMetadata] = useState({
    transcript: true,
    scores: true,
    tags: true,
    source: true,
    rejectionReasons: false,
  });

  if (!open) {
    return null;
  }

  function resetModal() {
    setStage("settings");
    setDownloadUrl(undefined);
    setError("");
  }

  function handleClose() {
    resetModal();
    onClose();
  }

  async function generateExport() {
    setStage("preparing");
    setError("");

    try {
      const response = await onGenerate({ include, metadata });
      setDownloadUrl(response.downloadUrl);
      setStage("complete");
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Export failed. Try again shortly.",
      );
      setStage("settings");
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 px-4 backdrop-blur-sm">
      <section className="w-full max-w-2xl overflow-hidden rounded-lg border border-white/10 bg-zinc-950 shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-white/10 p-5">
          <div>
            <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg border border-cyan-300/25 bg-cyan-300/10 text-cyan-100">
              <Package className="h-5 w-5" />
            </div>
            <h2 className="text-xl font-semibold tracking-tight">
              Export a training-ready dataset
            </h2>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              Package selected clips with transcripts, quality scores, and metadata.
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="grid h-9 w-9 place-items-center rounded-md border border-white/10 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
            aria-label="Close export modal"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="space-y-5 p-5">
          {stage === "settings" ? (
            <>
              <p className="rounded-md border border-white/10 bg-white/[0.035] p-3 text-sm text-zinc-300">
                {mode === "query"
                  ? `Exporting ${resultCount} clips matching the current query and filters.`
                  : `Exporting good clips from this video. ${resultCount} clips are currently selected.`}
              </p>
              {error ? (
                <p className="rounded-md border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">
                  {error}
                </p>
              ) : null}
            </>
          ) : (
            <div className="grid min-h-56 place-items-center text-center">
              {stage === "preparing" ? (
                <div>
                  <Loader2 className="mx-auto h-9 w-9 animate-spin text-cyan-200" />
                  <p className="mt-4 text-sm font-medium text-zinc-100">
                    Preparing export...
                  </p>
                </div>
              ) : (
                <div>
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-lg border border-emerald-300/30 bg-emerald-300/10 text-emerald-100">
                    <Download className="h-5 w-5" />
                  </div>
                  <p className="mt-4 text-sm font-medium text-zinc-100">
                    Export package is ready.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
        <footer className="flex items-center justify-end gap-3 border-t border-white/10 p-5">
          <button
            type="button"
            onClick={handleClose}
            className="inline-flex h-10 items-center justify-center rounded-md border border-white/10 px-4 text-sm font-medium text-zinc-300 transition hover:bg-white/5 hover:text-white"
          >
            Cancel
          </button>
          {stage === "settings" ? (
            <button
              type="button"
              onClick={generateExport}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-100"
            >
              <Package className="h-4 w-4" />
              Generate Export
            </button>
          ) : stage === "complete" ? (
            <a
              href={downloadUrl}
              className={cn(
                "inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-200 px-4 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-100",
                !downloadUrl && "pointer-events-none opacity-60",
              )}
            >
              <Download className="h-4 w-4" />
              Download ZIP
            </a>
          ) : null}
        </footer>
      </section>
    </div>
  );
}

function Checklist<T extends Record<string, boolean>>({
  title,
  options,
  values,
  onChange,
}: {
  title: string;
  options: ReadonlyArray<readonly [keyof T & string, string]>;
  values: T;
  onChange: (key: keyof T & string, value: boolean) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
        {title}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key, !values[key])}
            className={cn(
              "flex h-10 items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 text-sm text-zinc-400 transition hover:bg-white/[0.05]",
              values[key] && "border-cyan-300/35 bg-cyan-300/10 text-cyan-100",
            )}
          >
            <span>{label}</span>
            <span
              className={cn(
                "h-4 w-4 rounded border border-white/20",
                values[key] && "border-cyan-200 bg-cyan-200",
              )}
            />
          </button>
        ))}
      </div>
    </div>
  );
}
