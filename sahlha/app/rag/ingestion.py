"""Ingestion: bytes -> extract -> clean -> chunk -> persist -> reindex."""
from __future__ import annotations

import os
import re
from pathlib import Path

from sqlalchemy.orm import Session

from sahlha.app.config import settings
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag import vectorstore
from dataclasses import asdict
from sahlha.app.rag.chunking import chunk_blocks
from sahlha.app.rag.ocr import extract_document_text


def ingest_upload(db: Session, *, file_bytes: bytes, filename: str,
                  course_id: str = "general", lesson_id: str = "lesson_1",
                  skill_id: str = "general", defer_index: bool = False) -> dict:
    original_filename = filename
    filename = sanitize_filename(filename)
    doc = repo.create_document(db, filename=filename, course_id=course_id,
                               lesson_id=lesson_id, skill_id=skill_id)
    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(os.path.join(settings.upload_dir, f"{doc.id}_{filename}"), "wb") as fh:
        fh.write(file_bytes)

    extracted = extract_document_text(file_bytes, filename)
    doc.blocks = [asdict(b) for b in extracted.blocks]
    doc.extraction_quality = extracted.quality
    chunks = chunk_blocks(extracted.blocks, chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap, course_id=course_id,
                        lesson_id=lesson_id, skill_id=skill_id, document_id=doc.id)
    if chunks:
        repo.add_chunks(db, chunks)
    repo.mark_document_processed(db, doc, char_count=len(extracted.text), chunk_count=len(chunks))
    if chunks and not defer_index:
        vectorstore.rebuild_index(db)
    return {
        "document_id": doc.id,
        "filename": filename,
        "original_filename": original_filename,
        "title": derive_title(extracted.text, filename),
        "course_id": course_id,
        "lesson_id": lesson_id,
        "skill_id": skill_id,
        "quality": extracted.quality,
        "warnings": extracted.warnings,
        "method": extracted.method,
        "is_scanned": extracted.is_scanned,
        "num_pages": extracted.num_pages,
        "char_count": len(extracted.text),
        "chunk_count": len(chunks),
        "text_preview": extracted.text[:500],
    }


def sanitize_filename(filename: str) -> str:
    name = (filename or "upload.txt").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name:
        name = "upload.txt"
    stem, suffix = os.path.splitext(name)
    if stem.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        stem = "_" + stem
    return stem[:max(1, 140 - len(suffix[:16]))] + suffix[:16]


def derive_title(text: str, filename: str) -> str:
    for line in text.splitlines()[:20]:
        line = line.strip(" #\t")
        if re.fullmatch(r"(?:page\s*)?\d+|table of contents|contents", line, re.I):
            continue
        if 5 <= len(line) <= 100 and len(line.split()) >= 2:
            return line.rstrip(".:;")
    stem = Path(sanitize_filename(filename)).stem
    return re.sub(r"[_-]+", " ", stem).strip().capitalize() or "Learning material"
