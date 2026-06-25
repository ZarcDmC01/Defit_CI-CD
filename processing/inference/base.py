from __future__ import annotations
from abc import ABC, abstractmethod


class InferenceEngine(ABC):
    """Contract for all inference engines. Swap implementations via config."""

    @abstractmethod
    def summarize(self, text: str) -> str: ...

    @abstractmethod
    def extract_keywords(self, text: str) -> str: ...

    @abstractmethod
    def sentiment(self, text: str) -> str: ...

    @abstractmethod
    def answer_question(self, text: str, question: str) -> str: ...

    def run(self, task: str, text: str, question: str = "") -> str:
        dispatch = {
            "summarize": lambda: self.summarize(text),
            "keywords": lambda: self.extract_keywords(text),
            "sentiment": lambda: self.sentiment(text),
            "qa": lambda: self.answer_question(text, question),
        }
        handler = dispatch.get(task)
        if handler is None:
            raise ValueError(f"Unknown task '{task}'.")
        return handler()
