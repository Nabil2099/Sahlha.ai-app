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
    for idx, piece in enumerate(sentence_chunks(text, chunk_size, chunk_overlap), start_index):
        chunks.append({
            "document_id": document_id,
            "course_id": course_id,
            "lesson_id": lesson_id,
            "skill_id": skill_id,
            "page": page,
            "chunk_index": idx,
            "text": piece,
        })
    return chunks


def sentence_chunks(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Pack whole sentences; split only a sentence that exceeds the limit."""
    import re
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Require 0 <= overlap < chunk size")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text(text)) if s.strip()]
    units = [s[i:i + size] for s in sentences for i in range(0, len(s), size)]
    result, current = [], []
    for unit in units:
        if current and len(" ".join(current + [unit])) > size:
            result.append(" ".join(current))
            carry = []
            for sentence in reversed(current):
                if len(" ".join([sentence] + carry)) > overlap:
                    break
                carry.insert(0, sentence)
            while carry and len(" ".join(carry + [unit])) > size:
                carry.pop(0)
            current = carry
        current.append(unit)
    if current:
        result.append(" ".join(current))
    return result
