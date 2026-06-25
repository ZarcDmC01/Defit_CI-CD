from __future__ import annotations
import asyncio
from typing import Annotated, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from api.schemas import AITask, ErrorResponse, JobResult, UploadResponse
from processing.validator import ValidationError, validate_file
from services import job_service
from services.pipeline_service import run_pipeline
from storage.job_store import JobStatus

app = FastAPI(
    title="AI File Processing Pipeline",
    description="Upload TXT/PDF files and run asynchronous AI analysis.",
    version="1.0.0",
)


@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
    summary="Upload a file for AI processing",
)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(description="TXT or PDF file, max 5 MB")],
    task: Annotated[AITask, Form()] = "summarize",
    question: Annotated[Optional[str], Form()] = "",
):
    """
    Accept a file, validate it, create a job, and kick off background processing.
    Returns immediately with a job ID — no blocking inference on this endpoint.
    """
    try:
        content = await validate_file(file)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job = job_service.create_job(task)

    background_tasks.add_task(
        run_pipeline,
        job_id=job.job_id,
        file_content=content,
        filename=file.filename or "upload.txt",
        task=task,
        question=question or "",
    )

    return UploadResponse(
        job_id=job.job_id,
        status=JobStatus.PENDING,
        message="File accepted. Poll /result/{job_id} for status.",
    )


@app.get(
    "/result/{job_id}",
    response_model=JobResult,
    responses={404: {"model": ErrorResponse}},
    summary="Poll job status and retrieve AI output",
)
def get_result(job_id: str):
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobResult(
        job_id=job.job_id,
        status=job.status,
        task=job.task,
        result=job.result,
        error=job.error,
    )


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
