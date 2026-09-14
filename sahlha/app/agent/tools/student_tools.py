"""Student-memory tools — read/update relational memory, never a vector summary as truth."""
from __future__ import annotations

from sqlalchemy.orm import Session

from sahlha.app.database.repositories import repositories as repo


def get_student_history(db: Session, student_id: str, limit: int = 200) -> list[dict]:
    return [{"question_id": a.question_id, "assessment_id": a.assessment_id,
             "answer": a.answer, "correct": a.correct,
             "timestamp": a.timestamp.isoformat()} for a in repo.get_attempts(db, student_id, limit)]


def get_failed_questions(db: Session, student_id: str) -> list[str]:
    return repo.get_failed_question_ids(db, student_id)


def get_student_skill_performance(db: Session, student_id: str) -> list[dict]:
    return [{"skill_id": p.skill_id, "total": p.total_attempts, "correct": p.correct_attempts,
             "accuracy": p.accuracy} for p in repo.get_skill_performance(db, student_id)]


def update_student_memory(db: Session, *, student_id: str, skill_id: str, correct: bool) -> dict:
    perf = repo.upsert_skill_performance(db, student_id=student_id, skill_id=skill_id, correct=correct)
    return {"skill_id": perf.skill_id, "total": perf.total_attempts,
            "correct": perf.correct_attempts, "accuracy": perf.accuracy}
