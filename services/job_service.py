from __future__ import annotations
from typing import Optional
from storage.job_store import Job, JobStatus, job_store


def create_job(task: str) -> Job:
    return job_store.create(task)


def get_job(job_id: str) -> Optional[Job]:
    return job_store.get(job_id)


def mark_running(job_id: str) -> None:
    job_store.update(job_id, status=JobStatus.RUNNING)


def mark_completed(job_id: str, result: str) -> None:
    job_store.update(job_id, status=JobStatus.COMPLETED, result=result)


def mark_failed(job_id: str, error: str) -> None:
    job_store.update(job_id, status=JobStatus.FAILED, error=error)
