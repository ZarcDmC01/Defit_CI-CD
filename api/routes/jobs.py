from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas import ErrorResponse, JobListResponse, JobResult, JobStats
from services import job_service
from storage.job_store import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])

_VALID_STATUSES = {s.value for s in JobStatus}
_VALID_TASKS = {"summarize", "keywords", "sentiment", "qa"}


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs with optional filters",
)
async def list_jobs(
    status: Optional[str] = Query(None, description="PENDING | RUNNING | COMPLETED | FAILED"),
    task: Optional[str] = Query(None, description="summarize | keywords | sentiment | qa"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    if status and status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}")
    if task and task not in _VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task '{task}'. Valid: {sorted(_VALID_TASKS)}")

    jobs = await job_service.list_jobs(status=status, task=task, limit=limit, skip=skip)
    return JobListResponse(
        jobs=[
            JobResult(
                job_id=j.job_id,
                status=j.status,
                task=j.task,
                result=j.result,
                error=j.error,
                filename=j.filename,
                question=j.question,
            )
            for j in jobs
        ],
        total=len(jobs),
    )


@router.get(
    "/stats",
    response_model=JobStats,
    summary="Aggregated job statistics by status and task type",
)
async def get_stats():
    return await job_service.get_stats()


@router.delete(
    "/{job_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a job",
)
async def delete_job(job_id: str):
    deleted = await job_service.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
