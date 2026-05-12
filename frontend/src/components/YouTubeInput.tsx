"use client";

import { Link2, Youtube } from "lucide-react";
import { FormEvent, useState } from "react";

type YouTubeInputProps = {
  onSubmit: (url: string) => void;
};

export function YouTubeInput({ onSubmit }: YouTubeInputProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!value.trim()) {
      return;
    }

    onSubmit(value.trim());
    setValue("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-3 rounded-lg border border-white/10 bg-panel p-3 sm:grid-cols-[1fr_auto]"
    >
      <label className="flex h-11 items-center gap-3 rounded-md border border-white/10 bg-zinc-950/60 px-3">
        <Youtube className="h-5 w-5 text-rose-300" />
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Paste a YouTube URL"
          className="min-w-0 flex-1 bg-transparent text-sm text-zinc-100 outline-none placeholder:text-zinc-600"
        />
      </label>
      <button
        type="submit"
        className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-white px-4 text-sm font-medium text-zinc-950 transition hover:bg-cyan-100"
      >
        <Link2 className="h-4 w-4" />
        Add YouTube
      </button>
    </form>
  );
}
