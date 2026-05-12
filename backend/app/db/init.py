from __future__ import annotations

from app.db.session import get_connection
from app.utils.files import ensure_data_dirs


SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  title TEXT,
  filename TEXT,
  source_type TEXT,
  status TEXT,
  raw_path TEXT,
  normalized_path TEXT,
  thumbnail_path TEXT,
  duration_seconds REAL,
  file_size_mb REAL,
  width INTEGER,
  height INTEGER,
  fps REAL,
  created_at TEXT,
  updated_at TEXT,
  is_example INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  video_id TEXT,
  status TEXT,
  progress_stage TEXT,
  progress_percent INTEGER,
  clips_found INTEGER DEFAULT 0,
  error TEXT,
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT,
  updated_at TEXT,
  FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clips (
  id TEXT PRIMARY KEY,
  video_id TEXT,
  clip_path TEXT,
  thumbnail_path TEXT,
  start_time REAL,
  end_time REAL,
  duration REAL,
  quality TEXT,
  quality_score REAL,
  speech_score REAL,
  face_score REAL,
  audio_score REAL,
  transcript TEXT,
  tags_json TEXT,
  rejection_reasons_json TEXT,
  exportable INTEGER DEFAULT 1,
  created_at TEXT,
  updated_at TEXT,
  FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY,
  mode TEXT,
  query TEXT,
  filters_json TEXT,
  export_path TEXT,
  status TEXT,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_clips_quality ON clips(quality);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at);
"""


def init_db() -> None:
    ensure_data_dirs()
    with get_connection() as connection:
        connection.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print("Initialized Sift SQLite database.")
