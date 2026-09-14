from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sahlha.app.database.database import get_db
from sahlha.app.schemas.api import ReviewRequest
from sahlha.app.services import services as svc

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/question-banks/pending")
def pending(db: Session = Depends(get_db)):
    return svc.pending_banks(db)


@router.get("/question-banks/{bank_id}")
def bank_detail(bank_id: str, db: Session = Depends(get_db)):
    bank = svc.bank_detail(db, bank_id)
    if not bank:
        raise HTTPException(404, "Question bank not found")
    return bank


@router.post("/question-banks/{bank_id}/approve")
def approve(bank_id: str, db: Session = Depends(get_db)):
    try:
        return svc.approve_bank(db, bank_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/question-banks/{bank_id}/reject")
def reject(bank_id: str, req: ReviewRequest, db: Session = Depends(get_db)):
    try:
        return svc.reject_bank(db, bank_id, req.feedback)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
