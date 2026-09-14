"""POST /documents/upload, POST /documents/{id}/process (re-process = re-ingest not needed; process is part of upload)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from sahlha.app.database.database import get_db
from sahlha.app.services import services as svc

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
def upload_document(course_id: str = Form("general"), lesson_id: str = Form("lesson_1"),
                    skill_id: str = Form("general"), file: UploadFile = File(...),
                    db: Session = Depends(get_db)):
    data = file.file.read()
    return svc.upload_and_process(db, file_bytes=data, filename=file.filename or "upload.txt",
                                  course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)


@router.post("/{doc_id}/process")
def process_document(doc_id: str, db: Session = Depends(get_db)):
    from sahlha.app.database.repositories import repositories as repo

    doc = repo.get_document(db, doc_id)
    if not doc:
        return {"error": "not found"}
    chunks = repo.get_chunks(db, document_id=doc_id)
    return {"document_id": doc_id, "status": doc.status, "chunk_count": len(chunks)}
