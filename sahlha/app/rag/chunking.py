"""Overlapping character chunker (page-aware)."""
from __future__ import annotations


def clean_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(" ".join(" ".join(lines).split()).splitlines()).strip()


def chunk_text(text: str, *, chunk_size: int = 800, chunk_overlap: int = 120,
               course_id: str = "general", lesson_id: str = "lesson_1",
               skill_id: str = "general", document_id: str = "", page: int = 0,
               start_index: int = 0) -> list[dict]:
    text = clean_text(text)
    chunks: list[dict] = []
    if not text:
        return chunks
    step = max(1, chunk_size - chunk_overlap)
    idx = start_index
    for start in range(0, len(text), step):
        piece = text[start:start + chunk_size].strip()
        if not piece:
            break
        chunks.append({
            "document_id": document_id,
            "course_id": course_id,
            "lesson_id": lesson_id,
            "skill_id": skill_id,
            "page": page,
            "chunk_index": idx,
            "text": piece,
        })
        idx += 1
        if start + chunk_size >= len(text):
            break
    return chunks
