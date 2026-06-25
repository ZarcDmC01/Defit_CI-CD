from __future__ import annotations
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    max_file_size_mb: int = 5
    allowed_extensions: frozenset[str] = frozenset({".txt", ".pdf"})
    inference_engine: Literal["huggingface", "mock"] = "huggingface"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    gradio_port: int = 7860
    # HuggingFace model IDs — change here to swap models globally
    summarization_model: str = "sshleifer/distilbart-cnn-12-6"
    sentiment_model: str = "distilbert-base-uncased-finetuned-sst-2-english"
    qa_model: str = "deepset/minilm-uncased-squad2"

    model_config = {"env_file": ".env"}


settings = Settings()
