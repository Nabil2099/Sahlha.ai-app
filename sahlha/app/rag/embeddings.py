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


class EmbeddingModel:
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


_embeddings = EmbeddingModel()


def get_embeddings() -> EmbeddingModel:
    return _embeddings
