from __future__ import annotations
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel
from storage.job_store import JobStatus


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    task: str
    result: Optional[str] = None
    error: Optional[str] = None
    filename: Optional[str] = None
    question: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: List[JobResult]
    total: int


class JobStats(BaseModel):
    by_status: Dict[str, int]
    by_task: Dict[str, int]
    total: int


class ErrorResponse(BaseModel):
    detail: str


AITask = Literal["summarize", "keywords", "sentiment", "qa"]
