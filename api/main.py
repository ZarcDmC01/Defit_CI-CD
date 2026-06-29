from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Annotated, Optional

import gradio as gr
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse

from api.schemas import AITask, ErrorResponse, JobResult, UploadResponse
from api.routes.jobs import router as jobs_router
from processing.validator import ValidationError, validate_file
from services import job_service
from services.pipeline_service import run_pipeline
from storage.job_store import JobStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    from config import settings
    import storage.job_store as store_module

    if settings.mongodb_url:
        from storage.mongo_store import MongoJobStore
        store = MongoJobStore(settings.mongodb_url, settings.mongodb_db_name)
        await store.connect()
        store_module.active_store = store

    yield

    if hasattr(store_module.active_store, "close"):
        store_module.active_store.close()


app = FastAPI(
    title="AI File Processing Pipeline",
    description="Upload TXT/PDF files and run asynchronous AI analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs_router)


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
    try:
        content = await validate_file(file)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job = await job_service.create_job(
        task,
        filename=file.filename or "",
        question=question or "",
    )

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
async def get_result(job_id: str):
    job = await job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobResult(
        job_id=job.job_id,
        status=job.status,
        task=job.task,
        result=job.result,
        error=job.error,
        filename=job.filename,
        question=job.question,
    )


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui")


# Mount Gradio UI at /ui — same process, same port
from ui.gradio_app import demo as gradio_demo  # noqa: E402
app = gr.mount_gradio_app(app, gradio_demo, path="/ui")
