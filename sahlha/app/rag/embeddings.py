"""Embeddings via TF-IDF (offline, no API key needed).

Interface is swappable: `fit`, `embed`, `save/load` hide sklearn details.
A sentence-transformer backend can replace this later without touching callers.
"""
from __future__ import annotations

import os
import pickle

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


class TfidfEmbeddingModel:
    backend = "tfidf"
    dense = False

    def __init__(self) -> None:
        self.vectorizer: TfidfVectorizer | None = None

    def fit(self, texts: list[str]):
        from sahlha.app.config import settings

        self.vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), stop_words="english")
        mat = self.vectorizer.fit_transform(texts)
        os.makedirs(os.path.dirname(os.path.abspath(settings.vectorizer_path)), exist_ok=True)
        with open(settings.vectorizer_path, "wb") as fh:
            pickle.dump(self.vectorizer, fh)
        return mat

    def load(self) -> bool:
        from sahlha.app.config import settings

        if os.path.exists(settings.vectorizer_path):
            with open(settings.vectorizer_path, "rb") as fh:
                self.vectorizer = pickle.load(fh)
            return True
        return False

    def embed(self, texts: list[str]):
        if self.vectorizer is None and not self.load():
            self.fit(texts)
        assert self.vectorizer is not None
        return normalize(self.vectorizer.transform(texts))

    def embed_query(self, query: str):
        return self.embed([query])


# Dense dependencies are intentionally imported only on first use.
import logging
import threading


class DenseEmbeddingModel:
    dense = True

    def __init__(self, model_name=None):
        from sahlha.app.config import settings
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name or settings.embedding_model
        self.backend = f"dense:{self.model_name}"
        self.model = SentenceTransformer(self.model_name)

    def embed(self, texts):
        result = np.asarray(self.model.encode(texts, normalize_embeddings=True,
                            show_progress_bar=False), dtype=np.float32)
        if result.ndim != 2 or result.shape[1] != 384 or not np.isfinite(result).all():
            raise ValueError("Invalid dense embeddings")
        return result

    def fit(self, texts):
        return self.embed(texts)

    def embed_query(self, query):
        return self.embed([query])


EmbeddingModel = TfidfEmbeddingModel  # old imports remain valid
_embeddings = None
_lock = threading.RLock()


def get_embeddings():
    global _embeddings
    from sahlha.app.config import settings
    with _lock:
        if _embeddings is None:
            if settings.dense_embeddings_enabled:
                try:
                    _embeddings = DenseEmbeddingModel()
                except Exception as exc:
                    logging.getLogger(__name__).warning("Dense embeddings unavailable (%s); using TF-IDF", type(exc).__name__)
            if _embeddings is None:
                _embeddings = TfidfEmbeddingModel()
        return _embeddings


def use_tfidf():
    global _embeddings
    with _lock:
        _embeddings = TfidfEmbeddingModel()
        return _embeddings


def dense_available():
    return get_embeddings().dense
