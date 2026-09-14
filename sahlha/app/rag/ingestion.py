"""Ingestion: bytes -> extract -> clean -> chunk -> persist -> reindex."""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from sahlha.app.config import settings
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag import vectorstore
from sahlha.app.rag.chunking import chunk_text
from sahlha.app.rag.ocr import extract_document_text


def ingest_upload(db: Session, *, file_bytes: bytes, filename: str,
                  course_id: str = "general", lesson_id: str = "lesson_1",
                  skill_id: str = "general") -> dict:
    doc = repo.create_document(db, filename=filename, course_id=course_id,
                               lesson_id=lesson_id, skill_id=skill_id)
    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(os.path.join(settings.upload_dir, f"{doc.id}_{filename}"), "wb") as fh:
        fh.write(file_bytes)

    extracted = extract_document_text(file_bytes, filename)
    chunks = chunk_text(extracted.text, chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap, course_id=course_id,
                        lesson_id=lesson_id, skill_id=skill_id, document_id=doc.id)
    if chunks:
        repo.add_chunks(db, chunks)
    repo.mark_document_processed(db, doc, char_count=len(extracted.text), chunk_count=len(chunks))
    if chunks:
        try:
            vectorstore.rebuild_index(db)
        except Exception:
            pass  # retrieval falls back to keyword ranking
    return {
        "document_id": doc.id,
        "filename": filename,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "skill_id": skill_id,
        "method": extracted.method,
        "is_scanned": extracted.is_scanned,
        "num_pages": extracted.num_pages,
        "char_count": len(extracted.text),
        "chunk_count": len(chunks),
        "text_preview": extracted.text[:500],
    }
