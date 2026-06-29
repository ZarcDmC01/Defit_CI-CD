from __future__ import annotations
import time
import uuid
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class Job:
    job_id: str
    task: str
    status: JobStatus = JobStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    filename: Optional[str] = None
    question: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class InMemoryJobStore:
    """Thread-safe in-memory job store (fallback when MongoDB is not configured)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    async def create(self, task: str, filename: str = "", question: str = "") -> Job:
        job = Job(
            job_id=str(uuid.uuid4()),
            task=task,
            filename=filename or None,
            question=question or None,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    async def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **kwargs) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = time.time()
            return job

    async def list_jobs(
        self,
        status: Optional[str] = None,
        task: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status.value == status]
        if task:
            jobs = [j for j in jobs if j.task == task]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[skip : skip + limit]

    async def get_stats(self) -> dict:
        with self._lock:
            jobs = list(self._jobs.values())
        stats: dict = {"by_status": {}, "by_task": {}, "total": len(jobs)}
        for job in jobs:
            s = job.status.value
            t = job.task
            stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
            stats["by_task"][t] = stats["by_task"].get(t, 0) + 1
        return stats

    async def delete(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
        return False


# Active store — replaced at startup when MongoDB is configured
active_store: InMemoryJobStore = InMemoryJobStore()
