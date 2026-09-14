"""Vector store abstraction over TF-IDF + cosine similarity.

Chunks live in the relational DB (source of truth). This module handles
fitting the vectorizer and ranking. A FAISS/Chroma backend can replace it
later behind the same `search` function signature.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session
from sklearn.metrics.pairwise import cosine_similarity

from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag.embeddings import get_embeddings


def rebuild_index(db: Session) -> int:
    chunks = repo.get_chunks(db)
    texts = [c.text for c in chunks]
    if not texts:
        return 0
    get_embeddings().fit(texts)
    return len(texts)


def search(db: Session, query: str, *, top_k: int = 5,
           course_id: str | None = None, lesson_id: str | None = None,
           skill_id: str | None = None) -> list[dict]:
    from sahlha.app.config import settings

    top_k = top_k or settings.top_k_retrieval
    chunks = repo.get_chunks(db, course_id=course_id or None, lesson_id=lesson_id or None,
                             skill_id=skill_id or None, document_id=None)
    if not chunks:
        chunks = repo.get_chunks(db)  # fall back to global search
    if not chunks:
        return []
    texts = [c.text for c in chunks]
    emb = get_embeddings()
    try:
        doc_mat = emb.embed(texts)
        q_vec = emb.embed_query(query)
        sims = cosine_similarity(q_vec, doc_mat)[0]
    except ValueError:
        # Unfitted / empty vocab: fall back to keyword overlap ranking
        q_terms = set(query.lower().split())
        sims = np.array([len(q_terms & set(t.lower().split())) for t in texts], dtype=float)
    ranked = sorted(zip(chunks, sims), key=lambda p: float(p[1]), reverse=True)[:top_k]
    return [{
        "document_id": c.document_id,
        "course_id": c.course_id,
        "lesson_id": c.lesson_id,
        "skill_id": c.skill_id,
        "page": c.page,
        "chunk_id": c.id,
        "chunk_index": c.chunk_index,
        "text": c.text,
        "score": float(s),
    } for c, s in ranked]
