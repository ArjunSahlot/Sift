"use client";

import { Search } from "lucide-react";
import { FormEvent } from "react";

type SearchBarProps = {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  loading?: boolean;
};

export function SearchBar({ value, onChange, onSearch, loading = false }: SearchBarProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-3 rounded-lg border border-white/10 bg-panel-strong p-3 shadow-glow md:grid-cols-[1fr_auto]"
    >
      <label className="flex h-14 items-center gap-3 rounded-md border border-white/10 bg-zinc-950/65 px-4">
        <Search className="h-5 w-5 text-cyan-200" />
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Search clips by transcript, scene, or concept..."
          className="min-w-0 flex-1 bg-transparent text-base text-zinc-50 outline-none placeholder:text-zinc-600"
        />
      </label>
      <button
        type="submit"
        className="inline-flex h-14 items-center justify-center gap-2 rounded-md bg-white px-5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-100 disabled:cursor-wait disabled:opacity-70"
        disabled={loading}
      >
        <Search className="h-4 w-4" />
        {loading ? "Searching" : "Search"}
      </button>
    </form>
  );
}
