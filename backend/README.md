# Sift Backend

Sift is a VM-local FastAPI backend for a talking-head video dataset curation demo. It accepts short video uploads, queues a SQLite-backed processing job, cuts the full video into scene clips, attaches speech/face/audio/embedding metadata, supports search, and exports a training-ready ZIP.

## System Packages

Install these on the VM before installing Python dependencies:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg
```

The Python dependencies are managed by `uv` in `pyproject.toml`. The processing stack includes PySceneDetect, Silero VAD, OpenCV YuNet, sentence-transformers CLIP, and FAISS.

## Storage

```text
backend/local_data/
  data/sift.db
  storage/raw/
  storage/normalized/
  storage/clips/
  storage/thumbnails/
  storage/frames/
  storage/index/
  storage/debug/
  storage/exports/
  tmp/
  logs/
```

## Environment

```bash
cp .env.example .env
```

Useful variables:

```env
SIFT_MAX_UPLOAD_MB=250
SIFT_MAX_DURATION_SECONDS=300
SIFT_MAX_QUEUE_SIZE=5
SIFT_MAX_NON_EXAMPLE_VIDEOS=40
SIFT_CORS_ORIGINS=http://localhost:3000,https://your-vercel-app.vercel.app
SIFT_YUNET_MODEL_PATH=./models/yunet_fd.onnx
```

## Local Development Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync
python -m app.db.init
```

Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start the worker in a second shell:

```bash
cd backend
source .venv/bin/activate
python -m app.worker.run
```

## VM Deployment Setup

```bash
git clone <repo-url>
cd <repo>/backend
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync
cp .env.example .env
python -m app.db.init
```

Run the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the worker:

```bash
python -m app.worker.run
```

For production-ish VM usage, put Nginx in front of Uvicorn and serve `/media/` directly from `/opt/sift/storage/`. FastAPI also mounts `/media` for development and simple demos.

## API Overview

- `GET /api/health`
- `POST /api/upload`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `GET /api/jobs/{job_id}`
- `GET /api/videos/{video_id}/clips?quality=all`
- `GET /api/search?q=whiteboard&quality=good&type=speaking`
- `GET /api/videos/{video_id}/debug`
- `PATCH /api/clips/{clip_id}`
- `POST /api/export`

Media URLs are returned as `/media/raw/...`, `/media/clips/...`, `/media/thumbnails/...`, `/media/frames/...`, and `/media/exports/...`.

## Pipeline Notes

- Scene detection creates clips whose union covers the full normalized video.
- Silero VAD marks speech regions and speech coverage on each scene clip.
- YuNet face detection estimates speaker bucket (`0`, `1`, `2plus`) and face axis for single-speaker clips.
- The worker marks clips `embedding_status=pending` when the main job completes. A background embedding thread builds the CLIP/FAISS frame index without blocking the upload processing job.

## Add Example Videos

Examples are queued and processed by the normal worker:

```bash
cd backend
source .venv/bin/activate
python scripts/add_example.py /path/to/example.mp4 --title "Whiteboard Lecture"
python -m app.worker.run
```

Suggested examples:

- Whiteboard lecture
- Startup interview
- Noisy webcam recording
- Multi-speaker conversation
- Low-quality rejected example

## Cleanup

Cleanup rules are built in:

- Delete temporary job files after each job.
- Delete failed raw uploads older than 6 hours.
- Delete export ZIPs older than 24 hours.
- Keep example videos forever.
- Cap non-example videos at 40.

Manual cleanup:

```bash
cd backend
source .venv/bin/activate
python scripts/cleanup.py
```

Optional cron:

```cron
0 * * * * cd /path/to/repo/backend && . .venv/bin/activate && python scripts/cleanup.py
```

## Processing Pipeline

The worker runs one job at a time:

```text
queued
validating
probing_video
normalizing
extracting_audio
detecting_speech
extracting_clips
generating_thumbnails
running_face_detection
scoring_quality
saving_results
complete
```

The MVP uses FFmpeg/ffprobe, an energy-based speech detector, OpenCV Haar face detection, audio heuristics, and deterministic quality rules. Transcription is stubbed as `null` so the schema and export format are ready for a later `faster-whisper` pass without blocking the demo.
