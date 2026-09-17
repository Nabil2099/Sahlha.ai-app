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
        if emb.dense and cache and cache[0] == emb.backend and cache[3].shape[1] == (getattr(emb, "dimension", None) or cache[3].shape[1]):
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
            _write_cache(get_embeddings().backend, [], [], np.empty((0, 0)))
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


def lexical_scores(query, chunks):
    """BM25 ranks on the authorized candidate corpus, including code identifiers.

    Uses multilingual tokenization (Arabic/Latin/code/numbers) so Arabic and
    mixed lessons retrieve correctly. Never widens scope: scores only the
    supplied scoped chunks.
    """
    from collections import Counter
    from sahlha.app.rag.textnorm import multilingual_tokens
    terms = multilingual_tokens(query, drop_stop=True)
    documents = [Counter(multilingual_tokens(c.text, drop_stop=True)) for c in chunks]
    lengths = [sum(d.values()) for d in documents]
    average = sum(lengths) / max(1, len(lengths)) or 1
    scores = np.zeros(len(chunks))
    for term in set(terms):
        frequency = sum(term in d for d in documents)
        inverse = np.log(1 + (len(chunks) - frequency + .5) / (frequency + .5))
        for i, doc in enumerate(documents):
            tf = doc[term]
            scores[i] += inverse * tf * 2.5 / (tf + 1.5 * (.25 + .75 * lengths[i] / average))
    return scores


_rerankers = {}


def _rerank_bounded(query, chunks, candidates):
    """Bounded rerank returning (ordered, applied_bool). Internal."""
    if not settings.reranker_enabled or not candidates:
        return list(candidates), False
    try:
        # Bound candidates: capped, never the full corpus.
        limit = max(1, min(len(candidates), settings.reranker_max_candidates))
        bounded = list(candidates[:limit])
        # Preserve any candidates beyond the rerank window in original order.
        tail = list(candidates[limit:])
        if settings.reranker_model not in _rerankers:
            from sentence_transformers import CrossEncoder
            _rerankers[settings.reranker_model] = CrossEncoder(settings.reranker_model)
        values = np.asarray(_rerankers[settings.reranker_model].predict(
            [(query, chunks[i].text) for i in bounded]), dtype=float)
        if values.shape != (len(bounded),) or not np.isfinite(values).all():
            raise ValueError("Invalid reranker scores")
        ordered = [bounded[i] for i in np.argsort(-values, kind='stable')]
        return ordered + tail, True
    except Exception as exc:
        logging.getLogger(__name__).warning("Optional reranker unavailable (%s)", type(exc).__name__)
        return list(candidates), False


def rerank(query, chunks, candidates):
    """Bounded optional cross-encoder reranking (never the full corpus).

    Backwards-compatible: returns the ordered candidate list. Use
    _rerank_bounded() when the applied flag is needed.
    """
    ordered, _ = _rerank_bounded(query, chunks, candidates)
    return ordered


def search(db: Session, query: str, *, top_k: int = 5, course_id=None, lesson_id=None, skill_id=None) -> list[dict]:
    """Hybrid retrieval: lexical BM25 + dense/TF-IDF, RRF fusion, MMR diversity,
    optional bounded cross-encoder rerank. Strict scope: only the filtered
    chunks are ever scored; scope never widens implicitly."""
    top_k = max(1, top_k or settings.top_k_retrieval)
    chunks = repo.get_chunks(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if skill_id is not None and course_id is not None and lesson_id is not None:
        skill = repo.get_skill(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
        if skill and skill.evidence_chunk_ids:
            evidence_ids = set(skill.evidence_chunk_ids)
            chunks = [c for c in repo.get_chunks(db, course_id=course_id, lesson_id=lesson_id) if c.id in evidence_ids]
    if not chunks:
        return []
    with _lock:
        lexical = lexical_scores(query, chunks)
        ranks = {'lexical': [int(i) for i in np.argsort(-lexical, kind='stable') if lexical[i] > 0]}
        dense_vectors = None
        dense_backend = "lexical"
        try:
            corpus = repo.get_chunks(db)
            emb, vectors = _index(corpus)
            positions = {c.id: i for i, c in enumerate(corpus)}
            vectors = vectors[[positions[c.id] for c in chunks]]
            scores = vectors @ _matrix(emb.embed_query(query))[0]
            if emb.dense:
                dense_vectors = vectors
            dense_backend = emb.backend
            floor = settings.dense_min_score if emb.dense else .000001
            selected = [int(i) for i in np.argsort(-scores, kind='stable') if scores[i] >= floor]
            if not selected and scores.max() >= floor * settings.retrieval_backoff_ratio:
                selected = [int(scores.argmax())]
            ranks['dense' if emb.dense else 'tfidf'] = selected
        except Exception as exc:
            logging.getLogger(__name__).warning("Vector retrieval unavailable (%s)", type(exc).__name__)
        fused, sources = {}, {}
        for source, ranking in ranks.items():
            for rank, index in enumerate(ranking, 1):
                fused[index] = fused.get(index, 0) + 1 / (60 + rank)
                sources.setdefault(index, []).append(source)
        multiplier = max(1, settings.reranker_candidate_multiplier)
        candidates = sorted(fused, key=lambda i: (-fused[i], i))[:top_k * multiplier]
        mmr_applied = False
        if dense_vectors is not None and candidates:
            relevance = np.array([fused[i] for i in candidates])
            relevance /= relevance.max()
            diverse = mmr_select(dense_vectors[candidates], relevance, len(candidates), settings.mmr_lambda)
            candidates = [candidates[i] for i in diverse]
            mmr_applied = True
        ranked, reranked = _rerank_bounded(query, chunks, candidates)
        selected = ranked[:top_k]
        stages = ["lexical"] + ([dense_backend] if any(k in ranks for k in ("dense", "tfidf")) else []) + ["rrf"]
        if mmr_applied:
            stages.append("mmr")
        stages.append("rerank" if reranked else "no-rerank")
    return [{"document_id": chunks[i].document_id, "course_id": chunks[i].course_id,
             "lesson_id": chunks[i].lesson_id, "skill_id": chunks[i].skill_id,
             "page": chunks[i].page, "chunk_id": chunks[i].id,
             "section": chunks[i].section, "section_id": chunks[i].section_id,
             "type": chunks[i].type, "chunk_index": chunks[i].chunk_index, "text": chunks[i].text,
             "score": float(fused[i]), "retrieval_source": 'hybrid' if len(sources[i]) > 1 else sources[i][0],
             "retrieval_sources": sources[i], "retrieval_stages": stages,
             "rerank_applied": reranked} for i in selected]
