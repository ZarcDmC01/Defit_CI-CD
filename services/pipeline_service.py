from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

from processing.preprocessor import PreprocessingError, extract_text
from processing.inference.factory import engine
from services import job_service

# Shared thread pool for CPU-bound inference work
_executor = ThreadPoolExecutor(max_workers=4)


async def run_pipeline(
    job_id: str,
    file_content: bytes,
    filename: str,
    task: str,
    question: str = "",
) -> None:
    """
    Execute the full processing pipeline in the background.
    Stages: Preprocessing -> Inference -> Storage (result update)
    """
    loop = asyncio.get_event_loop()
    job_service.mark_running(job_id)

    try:
        # Stage 1: Preprocessing (I/O-like work, still run off-thread to avoid blocking)
        text = await loop.run_in_executor(
            _executor, extract_text, file_content, filename
        )

        # Stage 2: AI Inference (CPU-bound — must run in thread pool)
        result = await loop.run_in_executor(
            _executor, _run_inference, task, text, question
        )

        # Stage 3: Persist result
        job_service.mark_completed(job_id, result)

    except PreprocessingError as exc:
        job_service.mark_failed(job_id, f"Preprocessing failed: {exc}")
    except Exception as exc:
        job_service.mark_failed(job_id, f"Inference failed: {exc}")


def _run_inference(task: str, text: str, question: str) -> str:
    """Synchronous wrapper for thread-pool execution."""
    return engine().run(task, text, question)
