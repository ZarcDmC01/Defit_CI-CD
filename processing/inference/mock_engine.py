from __future__ import annotations
import time
import random
from processing.inference.base import InferenceEngine


class MockEngine(InferenceEngine):
    """
    Deterministic fake engine — no model downloads.
    Use with INFERENCE_ENGINE=mock for local development or CI.
    """

    def summarize(self, text: str) -> str:
        time.sleep(0.5)  # simulate inference latency
        words = text.split()[:25]
        return "[MOCK SUMMARY] " + " ".join(words) + "..."

    def extract_keywords(self, text: str) -> str:
        time.sleep(0.3)
        sample = random.sample(text.split(), min(8, len(text.split())))
        return "[MOCK KEYWORDS] " + ", ".join(sample)

    def sentiment(self, text: str) -> str:
        time.sleep(0.2)
        label = random.choice(["Positive", "Negative", "Neutral"])
        score = random.uniform(0.7, 0.99)
        return f"[MOCK] {label} (confidence: {score:.2%})"

    def answer_question(self, text: str, question: str) -> str:
        time.sleep(0.4)
        words = text.split()
        snippet = " ".join(words[2:7]) if len(words) > 7 else text[:50]
        return f"[MOCK] Answer to '{question}': {snippet}"
