from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import queries

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = queries.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return queries.job_response(job)
