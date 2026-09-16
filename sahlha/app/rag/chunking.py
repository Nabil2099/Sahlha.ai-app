"""Overlapping character chunker (page-aware)."""
from __future__ import annotations


def chunk_blocks(blocks, *, chunk_size=800, chunk_overlap=120, course_id="general",
                 lesson_id="lesson_1", skill_id="general", document_id=""):
    """Pack structural units; oversize units use explicit continuation metadata.

    Normal atomic units can exceed the soft limit, up to a bounded hard limit.
    This preserves typical code/tables without unbounded model input.
    """
    if chunk_size < 1 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require 0 <= overlap < chunk size")
    result, pending = [], []
    section, section_id = "", f"{document_id}:section:0"
    hard_limit = max(chunk_size, min(chunk_size * 4, 12000))

    def emit():
        if not pending:
            return
        text = '\n\n'.join(b.text for b in pending)
        kinds = list(dict.fromkeys(b.type for b in pending))
        for offset in range(0, len(text), hard_limit):
            result.append(dict(document_id=document_id, course_id=course_id, lesson_id=lesson_id,
                skill_id=skill_id, page=pending[0].page, chunk_index=len(result),
                section=section, section_id=section_id, type=kinds[0] if len(kinds)==1 else 'mixed',
                text=text[offset:offset+hard_limit], block_metadata={
                    'types': kinds, 'orders': [b.order for b in pending],
                    'continuation': offset > 0, 'oversize_split': len(text) > hard_limit}))
        pending.clear()

    for block in blocks:
        if not block.text.strip():
            continue
        if block.type == 'heading':
            emit()
            section = block.text.strip(' #')
            section_id = f'{document_id}:section:{block.page}:{block.order}'
        elif pending and (pending[0].page != block.page or
                (sum(len(b.text)+2 for b in pending)+len(block.text) > chunk_size and pending[-1].type != 'heading')):
            emit()
        pending.append(block)
    emit()
    return result


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
