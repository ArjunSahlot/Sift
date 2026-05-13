"use client";

import {
  Bug,
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  CircleAlert,
  Copy,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getVideoDebug,
  type DebugStage,
  type DebugStageStatus,
  type VideoDebugPayload,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const POLL_STATUSES = new Set(["queued", "uploading", "processing"]);

export function DebugDropdown({
  videoId,
  videoStatus,
}: {
  videoId: string;
  videoStatus: string;
}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<VideoDebugPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showRaw, setShowRaw] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getVideoDebug(videoId);
      setData(next);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load debug data.",
      );
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  useEffect(() => {
    if (!open || !POLL_STATUSES.has(videoStatus)) return;
    const timer = window.setInterval(() => {
      void load();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [open, load, videoStatus]);

  const summary = useMemo(() => {
    if (!data) return null;
    const completed = data.stages.filter((s) => s.status === "complete").length;
    const failed = data.stages.filter((s) => s.status === "failed").length;
    const clipsStage = data.stages.find((s) => s.id === "extracting_clips");
    const clipsOut = clipsStage
      ? Number((clipsStage.outputs as { clipsOut?: number })?.clipsOut ?? 0)
      : 0;
    return { completed, failed, total: data.stages.length, clipsOut };
  }, [data]);

  async function copyJson() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  return (
    <section className="mt-8 overflow-hidden rounded-lg border border-white/10 bg-panel">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-white/[0.025]"
      >
        <span className="inline-flex items-center gap-3">
          <Bug className="h-4 w-4 text-cyan-200" />
          <span className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-200">
            Pipeline debug
          </span>
          {summary ? (
            <span className="text-xs text-zinc-500">
              {summary.completed}/{summary.total} stages
              {summary.failed ? ` · ${summary.failed} failed` : ""}
              {` · ${summary.clipsOut} clips`}
            </span>
          ) : (
            <span className="text-xs text-zinc-500">
              Inspect every input & output across the pipeline
            </span>
          )}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-zinc-500 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open ? (
        <div className="space-y-5 border-t border-white/10 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-zinc-500">
              Read-only view of pipeline state. Polls while the job is active.
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-white/10 px-2.5 text-xs text-zinc-300 transition hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                <RefreshCw
                  className={cn("h-3.5 w-3.5", loading && "animate-spin")}
                />
                Refresh
              </button>
              <button
                type="button"
                onClick={copyJson}
                disabled={!data}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-white/10 px-2.5 text-xs text-zinc-300 transition hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                <Copy className="h-3.5 w-3.5" />
                {copied ? "Copied" : "Copy JSON"}
              </button>
            </div>
          </div>

          {loading && !data ? (
            <p className="text-sm text-zinc-400">Loading pipeline data...</p>
          ) : error ? (
            <p className="rounded-md border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">
              {error}
            </p>
          ) : data ? (
            <>
              <DebugTopline data={data} />

              <div className="space-y-2">
                {data.stages.map((stage) => (
                  <StageRow
                    key={stage.id}
                    stage={stage}
                    expanded={expanded[stage.id] ?? false}
                    onToggle={() =>
                      setExpanded((prev) => ({
                        ...prev,
                        [stage.id]: !prev[stage.id],
                      }))
                    }
                  />
                ))}
              </div>

              <div className="rounded-md border border-white/10 bg-white/[0.025]">
                <button
                  type="button"
                  onClick={() => setShowRaw((value) => !value)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-xs text-zinc-400 transition hover:text-zinc-200"
                >
                  <span className="inline-flex items-center gap-2">
                    {showRaw ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    Raw JSON payload
                  </span>
                  <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-600">
                    GET /api/videos/{videoId}/debug
                  </span>
                </button>
                {showRaw ? (
                  <pre className="max-h-[28rem] overflow-auto border-t border-white/10 bg-zinc-950/60 p-4 text-[11px] leading-relaxed text-zinc-200">
                    {JSON.stringify(data, null, 2)}
                  </pre>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function DebugTopline({ data }: { data: VideoDebugPayload }) {
  const video = data.video as Record<string, unknown> & { id: string };
  const job = (data.job ?? {}) as Record<string, unknown>;
  const fields: Array<{ label: string; value: string; mono?: boolean }> = [
    { label: "Video ID", value: String(video.id ?? "—"), mono: true },
    { label: "Job ID", value: String(job.id ?? "—"), mono: true },
    { label: "Job status", value: String(job.status ?? video.status ?? "—") },
    {
      label: "Current stage",
      value: String(job.progress_stage ?? "—"),
    },
    {
      label: "Progress",
      value:
        job.progress_percent != null ? `${job.progress_percent}%` : "—",
    },
    {
      label: "Error",
      value: typeof job.error === "string" && job.error ? job.error : "none",
    },
  ];

  return (
    <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map((field) => (
        <DebugMetric
          key={field.label}
          label={field.label}
          value={field.value}
          mono={field.mono}
        />
      ))}
    </div>
  );
}

function DebugMetric({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.025] px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </p>
      <p
        className={cn(
          "mt-1.5 truncate text-sm text-zinc-100",
          mono && "font-mono text-xs text-zinc-300",
        )}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}

function StageRow({
  stage,
  expanded,
  onToggle,
}: {
  stage: DebugStage;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border border-white/10 bg-white/[0.02] transition",
        expanded && "bg-white/[0.035]",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/[0.035]"
      >
        <StageStatusDot status={stage.status} />
        <span className="text-sm font-medium text-zinc-100">{stage.label}</span>
        {stage.module ? (
          <span className="hidden truncate font-mono text-[11px] text-zinc-500 md:inline">
            {stage.module}
          </span>
        ) : null}
        <span className="ml-auto inline-flex items-center gap-2">
          <StageStatusBadge status={stage.status} />
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-zinc-500" />
          )}
        </span>
      </button>
      {expanded ? (
        <div className="grid gap-3 border-t border-white/10 bg-zinc-950/40 p-4 lg:grid-cols-2">
          <JsonBlock label="Inputs" value={stage.inputs} />
          <JsonBlock label="Outputs" value={stage.outputs} />
        </div>
      ) : null}
    </div>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/40">
      <p className="border-b border-white/5 px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </p>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words px-3 py-2.5 text-[11px] leading-relaxed text-zinc-200">
        {prettyJson(value)}
      </pre>
    </div>
  );
}

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function StageStatusDot({ status }: { status: DebugStageStatus }) {
  if (status === "complete")
    return <Check className="h-4 w-4 shrink-0 text-emerald-400" />;
  if (status === "running")
    return <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan-300" />;
  if (status === "failed")
    return <CircleAlert className="h-4 w-4 shrink-0 text-rose-400" />;
  return <Circle className="h-4 w-4 shrink-0 text-zinc-600" />;
}

function StageStatusBadge({ status }: { status: DebugStageStatus }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em]",
        status === "complete" && "bg-emerald-500/15 text-emerald-200",
        status === "running" && "bg-cyan-500/15 text-cyan-200",
        status === "failed" && "bg-rose-500/15 text-rose-200",
        status === "skipped" && "bg-zinc-500/15 text-zinc-300",
        status === "pending" && "bg-white/5 text-zinc-400",
      )}
    >
      {status}
    </span>
  );
}
