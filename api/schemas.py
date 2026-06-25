from __future__ import annotations
from typing import Literal, Optional
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


class ErrorResponse(BaseModel):
    detail: str


AITask = Literal["summarize", "keywords", "sentiment", "qa"]
