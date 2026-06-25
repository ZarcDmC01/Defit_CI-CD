from __future__ import annotations
from processing.inference.base import InferenceEngine


def get_engine() -> InferenceEngine:
    """Return the configured inference engine singleton."""
    from config import settings

    if settings.inference_engine == "mock":
        from processing.inference.mock_engine import MockEngine
        return MockEngine()

    if settings.inference_engine == "huggingface":
        from processing.inference.hf_engine import HuggingFaceEngine
        return HuggingFaceEngine()

    raise ValueError(f"Unknown inference engine: '{settings.inference_engine}'")


# Module-level singleton — loaded once per worker process
_engine: InferenceEngine | None = None


def engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine
