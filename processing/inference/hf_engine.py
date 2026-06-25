from __future__ import annotations
import math
import re
from typing import Any
from processing.inference.base import InferenceEngine
from config import settings


class HuggingFaceEngine(InferenceEngine):
    """
    HuggingFace transformers-backed engine with lazy model loading.
    Models are downloaded on first use and cached by transformers.
    """

    def __init__(self) -> None:
        self._summarizer: Any = None
        self._sentiment_pipe: Any = None
        self._qa_pipe: Any = None

    # ------------------------------------------------------------------ #
    #  Lazy loaders                                                         #
    # ------------------------------------------------------------------ #
    def _get_summarizer(self):
        if self._summarizer is None:
            from transformers import pipeline
            self._summarizer = pipeline(
                "summarization",
                model=settings.summarization_model,
                truncation=True,
            )
        return self._summarizer

    def _get_sentiment(self):
        if self._sentiment_pipe is None:
            from transformers import pipeline
            self._sentiment_pipe = pipeline(
                "sentiment-analysis",
                model=settings.sentiment_model,
            )
        return self._sentiment_pipe

    def _get_qa(self):
        if self._qa_pipe is None:
            from transformers import pipeline
            self._qa_pipe = pipeline(
                "question-answering",
                model=settings.qa_model,
            )
        return self._qa_pipe

    # ------------------------------------------------------------------ #
    #  Tasks                                                                #
    # ------------------------------------------------------------------ #
    def summarize(self, text: str) -> str:
        # distilbart input cap ≈ 1024 tokens; truncate by word count
        words = text.split()
        chunk = " ".join(words[:800])
        word_count = len(chunk.split())
        max_len = min(150, math.ceil(word_count * 0.4))
        min_len = min(40, max_len - 1)
        out = self._get_summarizer()(chunk, max_length=max_len, min_length=min_len, do_sample=False)
        return out[0]["summary_text"]

    def extract_keywords(self, text: str) -> str:
        # TF-IDF keyword extraction — no model download required
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
        if not sentences:
            sentences = [text]

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=500,
        )
        try:
            tfidf = vectorizer.fit_transform(sentences)
        except ValueError:
            return "Could not extract keywords from this text."

        scores = np.asarray(tfidf.sum(axis=0)).flatten()
        feature_names = vectorizer.get_feature_names_out()
        top_idx = scores.argsort()[-15:][::-1]
        keywords = [feature_names[i] for i in top_idx]
        return ", ".join(keywords)

    def sentiment(self, text: str) -> str:
        # Sentiment pipeline works on ≤512 tokens; use first 400 words
        snippet = " ".join(text.split()[:400])
        out = self._get_sentiment()(snippet, truncation=True)[0]
        label = out["label"].capitalize()
        score = out["score"]
        return f"{label} (confidence: {score:.2%})"

    def answer_question(self, text: str, question: str) -> str:
        if not question:
            return "No question provided for Q&A task."
        context = " ".join(text.split()[:500])
        out = self._get_qa()(question=question, context=context)
        answer = out["answer"]
        score = out["score"]
        return f"Answer: {answer} (confidence: {score:.2%})"
