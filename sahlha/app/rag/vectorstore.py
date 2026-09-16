"""Persistent vectors; the database remains authoritative and scope never widens."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
import threading

import numpy as np
from sqlalchemy.orm import Session
from sahlha.app.config import settings
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag.embeddings import get_embeddings, use_tfidf

_lock = threading.RLock()


def _matrix(value):
    return np.asarray(value.toarray() if hasattr(value, "toarray") else value, dtype=np.float32)


def _fingerprint(chunk):
    return hashlib.sha256(chunk.text.encode()).hexdigest()


def _read_cache():
    try:
        with np.load(settings.vector_cache_path, allow_pickle=False) as data:
            ids, hashes, vectors = data["ids"].tolist(), data["hashes"].tolist(), data["vectors"]
            if vectors.ndim != 2 or len(ids) != len(vectors) or len(hashes) != len(ids) or not np.isfinite(vectors).all():
                return None
            return str(data["backend"].item()), ids, hashes, vectors
    except (OSError, ValueError, KeyError, EOFError):
        return None


def _write_cache(backend, ids, hashes, vectors):
    folder = os.path.dirname(os.path.abspath(settings.vector_cache_path))
    os.makedirs(folder, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=folder, suffix=".npz")
    try:
        with os.fdopen(fd, "wb") as stream:
            np.savez_compressed(stream, backend=backend, ids=np.array(ids, dtype=str),
                                hashes=np.array(hashes, dtype=str), vectors=vectors)
        os.replace(path, settings.vector_cache_path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _index(chunks):
    emb = get_embeddings()
    ids, hashes = [c.id for c in chunks], [_fingerprint(c) for c in chunks]
    texts = [c.text for c in chunks]
    cache = _read_cache()
    try:
        if emb.dense and cache and cache[0] == emb.backend and cache[3].shape[1] == 384:
            old = {cid: (digest, vector) for cid, digest, vector in zip(cache[1], cache[2], cache[3])}
            missing = [i for i, (cid, digest) in enumerate(zip(ids, hashes)) if cid not in old or old[cid][0] != digest]
            removed = len(set(old) - set(ids))
            churn = (len(missing) + removed) / max(len(ids), len(old), 1)
            if not missing and not removed and cache[1] == ids:
                return emb, cache[3]
            if churn <= settings.vector_incremental_churn:
                added = dict(zip(missing, _matrix(emb.embed([texts[i] for i in missing])))) if missing else {}
                vectors = np.stack([added[i] if i in added else old[cid][1] for i, cid in enumerate(ids)])
            else:
                vectors = _matrix(emb.fit(texts))
        elif not emb.dense and cache and cache[0] == emb.backend and cache[1] == ids and cache[2] == hashes and getattr(emb, "corpus_signature", None) == (ids, hashes):
            return emb, cache[3]
        else:
            vectors = _matrix(emb.fit(texts))
    except Exception:
        if not emb.dense:
            raise
        logging.getLogger(__name__).warning("Dense encoding failed; rebuilding with TF-IDF")
        emb = use_tfidf()
        vectors = _matrix(emb.fit(texts))
    emb.corpus_signature = (ids, hashes)
    _write_cache(emb.backend, ids, hashes, vectors)
    return emb, vectors


def rebuild_index(db: Session) -> int:
    with _lock:
        chunks = repo.get_chunks(db)
        if chunks:
            _index(chunks)
        else:
            _write_cache(get_embeddings().backend, [], [], np.empty((0, 384)))
        return len(chunks)


def mmr_select(vectors, scores, count, diversity=0.7):
    candidates = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), i))[:count * 3]
    chosen = []
    while candidates and len(chosen) < count:
        best = max(candidates, key=lambda i: diversity * scores[i] - (1 - diversity) *
                   (max(float(vectors[i] @ vectors[j]) for j in chosen) if chosen else 0))
        chosen.append(best)
        candidates.remove(best)
    return chosen


def search(db: Session, query: str, *, top_k: int = 5, course_id=None, lesson_id=None, skill_id=None) -> list[dict]:
    top_k = max(1, top_k or settings.top_k_retrieval)
    chunks = repo.get_chunks(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if not chunks:
        return []
    with _lock:
        try:
            corpus = repo.get_chunks(db)
            emb, vectors = _index(corpus)
            positions = {c.id: i for i, c in enumerate(corpus)}
            vectors = vectors[[positions[c.id] for c in chunks]]
            scores = vectors @ _matrix(emb.embed_query(query))[0]
            floor = settings.dense_min_score if emb.dense else 0.000001
            chosen = mmr_select(vectors, scores, top_k, settings.mmr_lambda)
            selected = [i for i in chosen if scores[i] >= floor]
            if not selected and scores.max() >= floor * settings.retrieval_backoff_ratio:
                selected = [int(scores.argmax())]
        except Exception as exc:
            logging.getLogger(__name__).warning("Vector retrieval unavailable (%s)", type(exc).__name__)
            selected = []
        if not selected:
            terms = set(re.findall(r"\w+", query.lower()))
            scores = np.array([len(terms & set(re.findall(r"\w+", c.text.lower()))) for c in chunks], dtype=float)
            selected = [i for i in np.argsort(-scores, kind="stable")[:top_k] if scores[i] > 0]
    return [{"document_id": chunks[i].document_id, "course_id": chunks[i].course_id,
             "lesson_id": chunks[i].lesson_id, "skill_id": chunks[i].skill_id,
             "page": chunks[i].page, "chunk_id": chunks[i].id,
             "chunk_index": chunks[i].chunk_index, "text": chunks[i].text,
             "score": float(scores[i])} for i in selected]
