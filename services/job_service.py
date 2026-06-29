from __future__ import annotations
from typing import Optional

import storage.job_store as store_module
from storage.job_store import Job, JobStatus


async def create_job(task: str, filename: str = "", question: str = "") -> Job:
    return await store_module.active_store.create(task, filename, question)


async def get_job(job_id: str) -> Optional[Job]:
    return await store_module.active_store.get(job_id)


async def mark_running(job_id: str) -> None:
    await store_module.active_store.update(job_id, status=JobStatus.RUNNING)


async def mark_completed(job_id: str, result: str) -> None:
    await store_module.active_store.update(job_id, status=JobStatus.COMPLETED, result=result)


async def mark_failed(job_id: str, error: str) -> None:
    await store_module.active_store.update(job_id, status=JobStatus.FAILED, error=error)


async def list_jobs(
    status: Optional[str] = None,
    task: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
) -> list[Job]:
    return await store_module.active_store.list_jobs(status=status, task=task, limit=limit, skip=skip)


async def get_stats() -> dict:
    return await store_module.active_store.get_stats()


async def delete_job(job_id: str) -> bool:
    return await store_module.active_store.delete(job_id)
