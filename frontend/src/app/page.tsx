"use client";

import {
  Archive,
  Database,
  Download,
  FileVideo,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { useMemo, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ClipCard } from "@/components/ClipCard";
import { EmptyState } from "@/components/EmptyState";
import { ExportModal } from "@/components/ExportModal";
import { FilterBar } from "@/components/FilterBar";
import { LoadingState } from "@/components/LoadingState";
import { ModeToggle } from "@/components/ModeToggle";
import { SearchBar } from "@/components/SearchBar";
import {
  UploadDropzone,
  type UploadState,
} from "@/components/UploadDropzone";
import { VideoCard } from "@/components/VideoCard";
import { YouTubeInput } from "@/components/YouTubeInput";
import { defaultFilters, mockClips, mockVideos } from "@/lib/mock-data";
import type { ClipItem, Mode, QueryFilters, VideoItem } from "@/lib/types";
import { cn, filterClips, formatDuration } from "@/lib/utils";

const processingStages = [
  "detecting_speech",
  "extracting_clips",
  "running_face_detection",
  "scoring_quality",
  "generating_thumbnails",
];

const initialFilters: QueryFilters = {
  ...defaultFilters,
  quality: "good",
  type: "speaking",
};

export default function Home() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("upload");
  const [videos, setVideos] = useState<VideoItem[]>(mockVideos);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadError, setUploadError] = useState("");
  const [youtubeNotice, setYoutubeNotice] = useState("");
  const [query, setQuery] = useState("whiteboard");
  const [filters, setFilters] = useState<QueryFilters>(initialFilters);
  const [results, setResults] = useState<ClipItem[]>(
    filterClips(mockClips, "whiteboard", initialFilters),
  );
  const [searching, setSearching] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setVideos((currentVideos) => currentVideos.map(advanceProcessingVideo));
    }, 2000);

    return () => window.clearInterval(timer);
  }, []);

  const publicStats = useMemo(() => {
    const completeVideos = videos.filter((video) => video.status === "complete");
    const clips = videos.reduce((total, video) => total + (video.clipsFound ?? 0), 0);
    const good = videos.reduce((total, video) => total + (video.goodClips ?? 0), 0);

    return {
      completeVideos: completeVideos.length,
      clips,
      good,
      duration: completeVideos.reduce(
        (total, video) => total + (video.durationSeconds ?? 0),
        0,
      ),
    };
  }, [videos]);

  function handleFileSelected(file: File) {
    const id = `video_upload_${Date.now()}`;
    const optimisticVideo: VideoItem = {
      id,
      title: file.name.replace(/\.[^/.]+$/, "") || "Uploaded Video",
      filename: file.name,
      sourceType: "upload",
      status: "uploading",
      progressStage: "uploading",
      progressPercent: 8,
      videoUrl: URL.createObjectURL(file),
      durationSeconds: 0,
      fileSizeMb: file.size / 1024 / 1024,
      clipsFound: 0,
      goodClips: 0,
      reviewClips: 0,
      rejectedClips: 0,
      createdAt: new Date().toISOString(),
    };

    setUploadError("");
    setUploadState("uploading");
    setVideos((currentVideos) => [optimisticVideo, ...currentVideos]);
    window.setTimeout(() => setUploadState("complete"), 1300);
  }

  function handleYouTubeSubmit(url: string) {
    setYoutubeNotice(
      `YouTube ingestion is ready for backend wiring. Captured URL: ${url}`,
    );
  }

  function handleSearch() {
    setSearching(true);
    window.setTimeout(() => {
      setResults(filterClips(mockClips, query, filters));
      setSearching(false);
    }, 450);
  }

  function handleVideoClick(video: VideoItem) {
    if (video.status === "failed") {
      return;
    }

    router.push(`/videos/${video.id}`);
  }

  return (
    <main className="min-h-screen px-5 py-6 text-zinc-100 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-6 border-b border-white/10 pb-7 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-300/10 px-2.5 py-1 text-xs font-medium text-cyan-100">
              <Sparkles className="h-3.5 w-3.5" />
              Sift
            </div>
            <h1 className="text-4xl font-semibold tracking-tight text-white md:text-6xl">
              Upload. Extract. Search.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-400 md:text-lg">
              Turn raw videos into searchable, quality-filtered human-speaking clips.
            </p>
          </div>
          <ModeToggle mode={mode} onModeChange={setMode} />
        </header>

        <section className="grid gap-3 py-6 md:grid-cols-4">
          <Stat
            icon={FileVideo}
            label="Processed videos"
            value={publicStats.completeVideos.toString()}
          />
          <Stat
            icon={Database}
            label="Extracted clips"
            value={publicStats.clips.toString()}
          />
          <Stat
            icon={Archive}
            label="Good clips"
            value={publicStats.good.toString()}
          />
          <Stat
            icon={UploadCloud}
            label="Accepted duration"
            value={formatDuration(publicStats.duration)}
          />
        </section>

        {mode === "upload" ? (
          <UploadMode
            videos={videos}
            uploadState={uploadState}
            uploadError={uploadError}
            youtubeNotice={youtubeNotice}
            onFileSelected={handleFileSelected}
            onYouTubeSubmit={handleYouTubeSubmit}
            onVideoClick={handleVideoClick}
          />
        ) : (
          <QueryMode
            query={query}
            filters={filters}
            results={results}
            searching={searching}
            onQueryChange={setQuery}
            onFiltersChange={setFilters}
            onSearch={handleSearch}
            onOpenExport={() => setExportOpen(true)}
          />
        )}
      </div>

      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        mode="query"
        resultCount={results.length}
      />
    </main>
  );
}

function UploadMode({
  videos,
  uploadState,
  uploadError,
  youtubeNotice,
  onFileSelected,
  onYouTubeSubmit,
  onVideoClick,
}: {
  videos: VideoItem[];
  uploadState: UploadState;
  uploadError: string;
  youtubeNotice: string;
  onFileSelected: (file: File) => void;
  onYouTubeSubmit: (url: string) => void;
  onVideoClick: (video: VideoItem) => void;
}) {
  return (
    <div className="space-y-8">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <UploadDropzone
          state={uploadState}
          onFileSelected={onFileSelected}
          error={uploadError}
        />
        <div className="space-y-4">
          <YouTubeInput onSubmit={onYouTubeSubmit} />
          {youtubeNotice ? (
            <p className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
              {youtubeNotice}
            </p>
          ) : null}
          <div className="rounded-lg border border-white/10 bg-panel p-5">
            <h2 className="text-base font-semibold text-zinc-100">Pipeline preview</h2>
            <div className="mt-4 space-y-3">
              {processingStages.map((stage, index) => (
                <div key={stage} className="flex items-center gap-3">
                  <span
                    className={cn(
                      "grid h-7 w-7 place-items-center rounded-md border text-xs font-semibold",
                      index === 0
                        ? "border-cyan-300/35 bg-cyan-300/10 text-cyan-100"
                        : "border-white/10 bg-white/[0.035] text-zinc-500",
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="text-sm text-zinc-300">
                    {stage.replaceAll("_", " ")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-white">
              Public Videos
            </h2>
            <p className="mt-2 text-sm text-zinc-400">
              Example and uploaded videos processed into the shared clip dataset.
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onClick={video.status === "failed" ? undefined : () => onVideoClick(video)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function QueryMode({
  query,
  filters,
  results,
  searching,
  onQueryChange,
  onFiltersChange,
  onSearch,
  onOpenExport,
}: {
  query: string;
  filters: QueryFilters;
  results: ClipItem[];
  searching: boolean;
  onQueryChange: (query: string) => void;
  onFiltersChange: (filters: QueryFilters) => void;
  onSearch: () => void;
  onOpenExport: () => void;
}) {
  return (
    <div className="space-y-6">
      <section>
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-white">
              Search the clip dataset
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
              Find clips by transcript, quality, visual concepts, and speaking conditions.
            </p>
          </div>
          {results.length ? (
            <button
              type="button"
              onClick={onOpenExport}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-100"
            >
              <Download className="h-4 w-4" />
              Export Current Results
            </button>
          ) : null}
        </div>
        <SearchBar
          value={query}
          onChange={onQueryChange}
          onSearch={onSearch}
          loading={searching}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {["person explaining code", "startup pitch", "good lighting", "office interview"].map(
            (example) => (
              <button
                key={example}
                type="button"
                onClick={() => onQueryChange(example)}
                className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-xs text-zinc-400 transition hover:border-cyan-300/30 hover:text-cyan-100"
              >
                {example}
              </button>
            ),
          )}
        </div>
      </section>

      <FilterBar filters={filters} onChange={onFiltersChange} />

      <section>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-zinc-100">Matching clips</h3>
          <p className="text-sm text-zinc-500">{results.length} results</p>
        </div>
        {searching ? (
          <LoadingState label="Searching clips..." />
        ) : results.length ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {results.map((clip) => (
              <ClipCard key={clip.id} clip={clip} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No clips found."
            description="Try a broader query or remove filters."
          />
        )}
      </section>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-md border border-white/10 bg-zinc-950/65 text-cyan-100">
          <Icon className="h-4 w-4" />
        </span>
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
            {label}
          </p>
          <p className="mt-1 text-xl font-semibold text-white">{value}</p>
        </div>
      </div>
    </div>
  );
}

function advanceProcessingVideo(video: VideoItem): VideoItem {
  if (!["queued", "uploading", "processing"].includes(video.status)) {
    return video;
  }

  const currentProgress = video.progressPercent ?? 0;
  const nextProgress = Math.min(
    100,
    currentProgress + (video.status === "uploading" ? 18 : 9),
  );

  if (nextProgress >= 100) {
    return {
      ...video,
      status: "complete",
      progressStage: "complete",
      progressPercent: 100,
      durationSeconds: video.durationSeconds || 166,
      clipsFound: Math.max(video.clipsFound ?? 0, 18),
      goodClips: Math.max(video.goodClips ?? 0, 11),
      reviewClips: Math.max(video.reviewClips ?? 0, 4),
      rejectedClips: Math.max(video.rejectedClips ?? 0, 3),
    };
  }

  const stageIndex = Math.min(
    processingStages.length - 1,
    Math.floor((nextProgress / 100) * processingStages.length),
  );

  return {
    ...video,
    status: nextProgress > 32 ? "processing" : video.status,
    progressStage: processingStages[stageIndex],
    progressPercent: nextProgress,
    clipsFound:
      nextProgress > 34
        ? Math.max(video.clipsFound ?? 0, Math.floor(nextProgress / 5))
        : video.clipsFound,
  };
}
