from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

from processing.preprocessor import PreprocessingError, extract_text
from processing.inference.factory import engine
from services import job_service

_executor = ThreadPoolExecutor(max_workers=4)


async def run_pipeline(
    job_id: str,
    file_content: bytes,
    filename: str,
    task: str,
    question: str = "",
) -> None:
    loop = asyncio.get_event_loop()
    await job_service.mark_running(job_id)

    try:
        text = await loop.run_in_executor(_executor, extract_text, file_content, filename)
        result = await loop.run_in_executor(_executor, _run_inference, task, text, question)
        await job_service.mark_completed(job_id, result)

    except PreprocessingError as exc:
        await job_service.mark_failed(job_id, f"Preprocessing failed: {exc}")
    except Exception as exc:
        await job_service.mark_failed(job_id, f"Inference failed: {exc}")


def _run_inference(task: str, text: str, question: str) -> str:
    return engine().run(task, text, question)
