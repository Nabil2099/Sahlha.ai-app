"""Repository helpers. Only place besides services that touches the ORM directly.

The agent/LLM must NEVER import these — it goes through tools.
"""
from __future__ import annotations

import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from sahlha.app.database import models as m


# ---- Documents ----
def create_document(db: Session, *, filename: str, course_id: str, lesson_id: str, skill_id: str) -> m.Document:
    doc = m.Document(filename=filename, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, doc_id: str) -> m.Document | None:
    return db.get(m.Document, doc_id)


def mark_document_processed(db: Session, doc: m.Document, *, char_count: int, chunk_count: int) -> None:
    doc.status = "processed"
    doc.char_count = char_count
    doc.chunk_count = chunk_count
    db.commit()


def add_chunks(db: Session, chunks: list[dict]) -> int:
    for c in chunks:
        db.add(m.DocumentChunk(**c))
    db.commit()
    return len(chunks)


def get_chunks(db: Session, *, course_id: str | None = None, lesson_id: str | None = None,
               skill_id: str | None = None, document_id: str | None = None) -> list[m.DocumentChunk]:
    q = select(m.DocumentChunk)
    if course_id:
        q = q.where(m.DocumentChunk.course_id == course_id)
    if lesson_id:
        q = q.where(m.DocumentChunk.lesson_id == lesson_id)
    if skill_id:
        q = q.where(m.DocumentChunk.skill_id == skill_id)
    if document_id:
        q = q.where(m.DocumentChunk.document_id == document_id)
    return list(db.execute(q).scalars().all())


# ---- Lesson explanations ----
def upsert_lesson_explanation(db: Session, *, course_id: str, lesson_id: str,
                              title: str = "", explanation: str = "",
                              key_concepts: list | None = None) -> m.LessonExplanation:
    q = select(m.LessonExplanation).where(m.LessonExplanation.course_id == course_id,
                                          m.LessonExplanation.lesson_id == lesson_id)
    row = db.execute(q).scalars().first()
    if row is None:
        row = m.LessonExplanation(course_id=course_id, lesson_id=lesson_id)
        db.add(row)
        db.flush()
    if title:
        row.title = title
    if explanation:
        row.explanation = explanation
    if key_concepts is not None:
        row.key_concepts = key_concepts
    row.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def get_lesson_explanation(db: Session, *, course_id: str, lesson_id: str) -> m.LessonExplanation | None:
    q = select(m.LessonExplanation).where(m.LessonExplanation.course_id == course_id,
                                          m.LessonExplanation.lesson_id == lesson_id)
    return db.execute(q).scalars().first()


# ---- Skills ----
def upsert_skill(db: Session, *, course_id: str, lesson_id: str, skill_id: str,
                 name: str = "", description: str = "", key_concepts: list | None = None) -> m.Skill:
    q = select(m.Skill).where(m.Skill.course_id == course_id, m.Skill.lesson_id == lesson_id,
                              m.Skill.skill_id == skill_id)
    skill = db.execute(q).scalars().first()
    if skill is None:
        skill = m.Skill(course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
        db.add(skill)
        db.flush()
    if name:
        skill.name = name
    if description:
        skill.description = description
    if key_concepts is not None:
        skill.key_concepts = key_concepts
    skill.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(skill)
    return skill


def list_skills(db: Session, *, course_id: str, lesson_id: str) -> list[m.Skill]:
    q = select(m.Skill).where(m.Skill.course_id == course_id, m.Skill.lesson_id == lesson_id)
    return list(db.execute(q).scalars().all())


def get_skill(db: Session, *, course_id: str, lesson_id: str, skill_id: str) -> m.Skill | None:
    q = select(m.Skill).where(m.Skill.course_id == course_id, m.Skill.lesson_id == lesson_id,
                              m.Skill.skill_id == skill_id)
    return db.execute(q).scalars().first()


def get_skill_by_slug(db: Session, skill_id: str) -> m.Skill | None:
    """Lesson-agnostic lookup (slugs embed the lesson, e.g. cond_lesson__condition)."""
    q = select(m.Skill).where(m.Skill.skill_id == skill_id).limit(1)
    return db.execute(q).scalars().first()


def set_skill_explanation(db: Session, skill: m.Skill, explanation: str) -> None:
    skill.explanation = explanation
    skill.updated_at = datetime.datetime.utcnow()
    db.commit()


# ---- Question banks ----
def next_bank_version(db: Session, *, course_id: str, lesson_id: str, skill_id: str) -> int:
    q = (
        select(m.QuestionBank)
        .where(m.QuestionBank.course_id == course_id, m.QuestionBank.lesson_id == lesson_id,
               m.QuestionBank.skill_id == skill_id)
        .order_by(desc(m.QuestionBank.version))
        .limit(1)
    )
    latest = db.execute(q).scalars().first()
    return (latest.version + 1) if latest else 1


def create_bank(db: Session, *, course_id: str, lesson_id: str, skill_id: str,
                questions: list[dict], teacher_feedback: str = "") -> m.QuestionBank:
    version = next_bank_version(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    bank = m.QuestionBank(course_id=course_id, lesson_id=lesson_id, skill_id=skill_id,
                          version=version, status="pending_review", teacher_feedback=teacher_feedback)
    db.add(bank)
    db.flush()
    for qd in questions:
        db.add(m.Question(question_bank_id=bank.id, **qd))
    db.commit()
    db.refresh(bank)
    return bank


def get_bank(db: Session, bank_id: str) -> m.QuestionBank | None:
    return db.get(m.QuestionBank, bank_id)


def list_banks(db: Session, *, status: str | None = None) -> list[m.QuestionBank]:
    q = select(m.QuestionBank).order_by(desc(m.QuestionBank.created_at))
    if status:
        q = q.where(m.QuestionBank.status == status)
    return list(db.execute(q).scalars().all())


def set_bank_status(db: Session, bank: m.QuestionBank, status: str, feedback: str = "") -> None:
    bank.status = status
    if feedback:
        bank.teacher_feedback = feedback
    bank.updated_at = datetime.datetime.utcnow()
    db.commit()


def get_questions(db: Session, bank_id: str) -> list[m.Question]:
    q = select(m.Question).where(m.Question.question_bank_id == bank_id)
    return list(db.execute(q).scalars().all())


def get_approved_questions(db: Session, *, course_id: str | None = None,
                           lesson_id: str | None = None, skill_id: str | None = None) -> list[m.Question]:
    q = select(m.Question).join(m.QuestionBank, m.Question.question_bank_id == m.QuestionBank.id).where(
        m.QuestionBank.status == "approved")
    if course_id:
        q = q.where(m.QuestionBank.course_id == course_id)
    if lesson_id:
        q = q.where(m.QuestionBank.lesson_id == lesson_id)
    if skill_id:
        q = q.where(m.QuestionBank.skill_id == skill_id)
    return list(db.execute(q).scalars().all())


# ---- Students / attempts ----
def get_or_create_student(db: Session, student_id: str | None, name: str = "Student") -> m.Student:
    if student_id:
        s = db.get(m.Student, student_id)
        if s:
            return s
        s = m.Student(id=student_id, name=name)
    else:
        s = m.Student(name=name)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_student(db: Session, student_id: str) -> m.Student | None:
    return db.get(m.Student, student_id)


def create_assessment(db: Session, *, student_id: str, question_bank_id: str, question_ids: list[str]) -> m.Assessment:
    a = m.Assessment(student_id=student_id, question_bank_id=question_bank_id,
                     question_ids=question_ids, status="started")
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def get_assessment(db: Session, assessment_id: str) -> m.Assessment | None:
    return db.get(m.Assessment, assessment_id)


def record_attempt(db: Session, *, student_id: str, question_id: str, assessment_id: str,
                   answer, correct: bool) -> m.StudentAttempt:
    att = m.StudentAttempt(student_id=student_id, question_id=question_id,
                           assessment_id=assessment_id, answer=answer, correct=correct)
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def get_attempts(db: Session, student_id: str, limit: int = 200) -> list[m.StudentAttempt]:
    q = (select(m.StudentAttempt).where(m.StudentAttempt.student_id == student_id)
         .order_by(desc(m.StudentAttempt.timestamp)).limit(limit))
    return list(db.execute(q).scalars().all())


def get_failed_question_ids(db: Session, student_id: str) -> list[str]:
    q = select(m.StudentAttempt).where(m.StudentAttempt.student_id == student_id,
                                       m.StudentAttempt.correct.is_(False))
    return [a.question_id for a in db.execute(q).scalars().all()]


def upsert_skill_performance(db: Session, *, student_id: str, skill_id: str, correct: bool) -> m.StudentSkillPerformance:
    q = select(m.StudentSkillPerformance).where(
        m.StudentSkillPerformance.student_id == student_id,
        m.StudentSkillPerformance.skill_id == skill_id)
    perf = db.execute(q).scalars().first()
    if perf is None:
        perf = m.StudentSkillPerformance(student_id=student_id, skill_id=skill_id)
        db.add(perf)
        db.flush()
    perf.total_attempts += 1
    if correct:
        perf.correct_attempts += 1
    perf.accuracy = perf.correct_attempts / perf.total_attempts if perf.total_attempts else 0.0
    perf.last_updated = datetime.datetime.utcnow()
    db.commit()
    db.refresh(perf)
    return perf


def get_skill_performance(db: Session, student_id: str) -> list[m.StudentSkillPerformance]:
    q = select(m.StudentSkillPerformance).where(m.StudentSkillPerformance.student_id == student_id)
    return list(db.execute(q).scalars().all())
