"""Overlapping page-aware chunker with structure-aware oversize splitting."""
from __future__ import annotations

import re


def _split_code_lines(text: str, hard_limit: int) -> list[str]:
    """Line-aware split for code: keep whole lines together when possible."""
    lines = text.splitlines(keepends=True) or [text]
    parts, current = [], ""
    for line in lines:
        if len(line) > hard_limit:
            if current:
                parts.append(current)
                current = ""
            for i in range(0, len(line), hard_limit):
                parts.append(line[i:i + hard_limit])
        elif len(current) + len(line) > hard_limit and current:
            parts.append(current)
            current = line
        else:
            current += line
    if current:
        parts.append(current)
    return parts or [text]


def _split_table_rows(text: str, hard_limit: int) -> list[str]:
    """Row-aware split for tables: keep whole rows together."""
    rows = text.splitlines() or [text]
    parts, current = [], ""
    for row in rows:
        piece = row + "\n"
        if len(piece) > hard_limit:
            if current:
                parts.append(current)
                current = ""
            for i in range(0, len(piece), hard_limit):
                parts.append(piece[i:i + hard_limit])
        elif len(current) + len(piece) > hard_limit and current:
            parts.append(current)
            current = piece
        else:
            current += piece
    if current:
        parts.append(current.rstrip("\n") if len(parts) else current)
    return parts or [text]


def _split_formula_lines(text: str, hard_limit: int) -> list[str]:
    """Semantic/line split for formulas where possible, else bounded slices."""
    lines = [ln for ln in text.splitlines() if ln.strip()] or [text]
    if len(lines) > 1:
        return _split_table_rows(text, hard_limit)
    return [text[i:i + hard_limit] for i in range(0, len(text), hard_limit)] or [text]


def _split_prose_sentences(text: str, hard_limit: int) -> list[str]:
    """Sentence-aware split for prose oversize blocks."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?؟。])\s+", text.strip()) if s.strip()]
    if not sentences:
        return [text[i:i + hard_limit] for i in range(0, len(text), hard_limit)] or [text]
    parts, current = [], ""
    for sent in sentences:
        if len(sent) > hard_limit:
            if current:
                parts.append(current)
                current = ""
            for i in range(0, len(sent), hard_limit):
                parts.append(sent[i:i + hard_limit])
        elif current and len(current) + 1 + len(sent) > hard_limit:
            parts.append(current)
            current = sent
        else:
            current = (current + " " + sent).strip() if current else sent
    if current:
        parts.append(current)
    return parts or [text]


def split_oversized_block(block, hard_limit: int) -> list[str]:
    """Split an oversized structured block on structural boundaries."""
    text = block.text or ""
    if len(text) <= hard_limit:
        return [text]
    kind = (block.type or "paragraph").lower()
    if kind == "code":
        return _split_code_lines(text, hard_limit)
    if kind == "table":
        return _split_table_rows(text, hard_limit)
    if kind == "formula":
        return _split_formula_lines(text, hard_limit)
    return _split_prose_sentences(text, hard_limit)


def _overlap_tail(text: str, overlap: int) -> str:
    """Bounded overlap suffix cut at a sentence/bounded-text boundary."""
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    # Prefer starting at a sentence boundary inside the tail.
    boundaries = [m.end() for m in re.finditer(r"(?<=[.!?؟。])\s+", tail)]
    if boundaries:
        # Use the last boundary that still leaves a meaningful overlap.
        for pos in reversed(boundaries):
            if len(tail) - pos >= min(20, overlap // 3):
                return tail[pos:]
        return tail[boundaries[-1]:]
    # Fall back to a line/word boundary to avoid mid-word duplication.
    space = tail.find(" ")
    if 0 < space < len(tail) // 2:
        return tail[space + 1:]
    return tail


def chunk_blocks(blocks, *, chunk_size=800, chunk_overlap=120, course_id="general",
                 lesson_id="lesson_1", skill_id="general", document_id=""):
    """Pack structural units with REAL overlap and structure-aware splitting.

    - Paragraphs overlap at sentence/bounded-text boundaries.
    - Section IDs, page and block metadata are preserved; chunk IDs stay unique.
    - code/table/formula blocks remain atomic when they fit; oversize ones
      split on line/row/semantic boundaries with continuation metadata.
    - Oversize continuations of a SINGLE block do not gain overlap duplication
      (their join reconstructs the source exactly).
    """
    if chunk_size < 1 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require 0 <= overlap < chunk size")
    result: list[dict] = []
    pending: list = []
    pending_section = ""
    pending_section_id = f"{document_id}:section:0"
    pending_page = 0
    section, section_id = "", f"{document_id}:section:0"
    hard_limit = max(chunk_size, min(chunk_size * 4, 12000))
    carry_overlap = ""

    def _pending_text() -> str:
        return '\n\n'.join(b.text for b in pending)

    def emit():
        nonlocal carry_overlap, pending_section, pending_section_id, pending_page
        if not pending:
            return
        text = _pending_text()
        kinds = list(dict.fromkeys(b.type for b in pending))
        single_kind = kinds[0] if len(kinds) == 1 else 'mixed'
        atomic_structured = single_kind in ('code', 'table', 'formula') and len(text) <= hard_limit
        # Oversize single-block splits: no overlap duplication (exact join).
        if len(pending) == 1 and len(text) > hard_limit:
            for offset, piece in enumerate(split_oversized_block(pending[0], hard_limit)):
                result.append(dict(document_id=document_id, course_id=course_id, lesson_id=lesson_id,
                    skill_id=skill_id, page=pending[0].page, chunk_index=len(result),
                    section=pending_section, section_id=pending_section_id,
                    type=pending[0].type, text=piece, block_metadata={
                        'types': kinds, 'orders': [b.order for b in pending],
                        'continuation': offset > 0, 'oversize_split': True,
                        'source_block_index': pending[0].order,
                        'overlap_chars': 0, 'has_overlap': False}))
            pending.clear()
            carry_overlap = ""
            return
        # Normal chunk: prepend bounded overlap from the previous chunk unless
        # this chunk is an atomic structured block (no duplication).
        prefix = ""
        overlap_chars = 0
        if carry_overlap and not atomic_structured and single_kind not in ('code', 'table', 'formula'):
            prefix = carry_overlap
            overlap_chars = len(prefix)
        full_text = (prefix + "\n\n" + text).strip() if prefix else text
        # Enforce hard limit even after overlap (rare; split on sentences).
        pieces = [full_text] if len(full_text) <= hard_limit else _split_prose_sentences(full_text, hard_limit)
        for offset, piece in enumerate(pieces):
            result.append(dict(document_id=document_id, course_id=course_id, lesson_id=lesson_id,
                skill_id=skill_id, page=pending_page, chunk_index=len(result),
                section=pending_section, section_id=pending_section_id,
                type=single_kind, text=piece, block_metadata={
                    'types': kinds, 'orders': [b.order for b in pending],
                    'continuation': offset > 0, 'oversize_split': len(pieces) > 1,
                    'overlap_chars': overlap_chars if offset == 0 else 0,
                    'has_overlap': bool(overlap_chars) and offset == 0}))
        # Next chunk overlaps this chunk's prose tail (not structured atomics).
        if single_kind in ('code', 'table', 'formula') and len(kinds) == 1:
            carry_overlap = ""
        else:
            carry_overlap = _overlap_tail(text, chunk_overlap)
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
        if not pending:
            pending_section, pending_section_id, pending_page = section, section_id, block.page
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
