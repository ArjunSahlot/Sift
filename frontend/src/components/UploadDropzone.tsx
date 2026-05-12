"use client";

import { UploadCloud, Video } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type UploadState =
  | "idle"
  | "dragging"
  | "uploading"
  | "complete"
  | "failed";

type UploadDropzoneProps = {
  state: UploadState;
  onFileSelected: (file: File) => void;
  error?: string;
};

export function UploadDropzone({ state, onFileSelected, error }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const activeState = isDragging ? "dragging" : state;

  function handleFiles(files: FileList | null) {
    const file = files?.[0];

    if (file) {
      onFileSelected(file);
    }
  }

  return (
    <div
      onDragEnter={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        handleFiles(event.dataTransfer.files);
      }}
      className={cn(
        "relative flex min-h-72 flex-col items-center justify-center rounded-lg border border-dashed border-white/15 bg-white/[0.035] px-6 text-center transition",
        activeState === "dragging" && "border-cyan-300 bg-cyan-300/10",
        activeState === "uploading" && "border-cyan-300/50",
        activeState === "failed" && "border-rose-300/50 bg-rose-400/5",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
        className="hidden"
        onChange={(event) => handleFiles(event.target.files)}
      />
      <div className="mb-5 grid h-14 w-14 place-items-center rounded-lg border border-white/10 bg-zinc-950/70">
        {activeState === "uploading" ? (
          <Video className="h-6 w-6 text-cyan-200" />
        ) : (
          <UploadCloud className="h-6 w-6 text-cyan-200" />
        )}
      </div>
      <h2 className="text-xl font-semibold tracking-tight">
        {activeState === "dragging"
          ? "Drop the video to start extraction"
          : "Drag and drop a video file"}
      </h2>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="mt-2 text-sm font-medium text-cyan-200 underline-offset-4 hover:underline"
      >
        or click to upload
      </button>
      <p className="mt-4 max-w-xl text-sm leading-6 text-zinc-400">
        Demo limits: MP4, MOV, WebM, or MKV. Max 250 MB / 5 minutes.
      </p>
      {activeState === "uploading" ? (
        <p className="mt-4 text-sm text-cyan-100">Uploading and creating a dataset job...</p>
      ) : null}
      {error ? <p className="mt-4 text-sm text-rose-200">{error}</p> : null}
    </div>
  );
}
