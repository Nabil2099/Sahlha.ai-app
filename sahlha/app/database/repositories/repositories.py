"""Repository helpers. Only place besides services that touches the ORM directly.

The agent/LLM must NEVER import these — it goes through tools.
"""
from __future__ import annotations

import datetime

from sqlalchemy import desc, select, update, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

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
    if course_id is not None:
        q = q.where(m.DocumentChunk.course_id == course_id)
    if lesson_id is not None:
        q = q.where(m.DocumentChunk.lesson_id == lesson_id)
    if skill_id is not None:
        q = q.where(m.DocumentChunk.skill_id == skill_id)
    if document_id is not None:
        q = q.where(m.DocumentChunk.document_id == document_id)
    return list(db.execute(q.order_by(m.DocumentChunk.document_id, m.DocumentChunk.chunk_index)).scalars().all())


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
        if row.explanation != explanation or (title and row.title != title):
            row.audio_path = ""
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
                 name: str = "", description: str = "", key_concepts: list | None = None,
                 educational_metadata: dict | None = None) -> m.Skill:
    q = select(m.Skill).where(m.Skill.course_id == course_id, m.Skill.lesson_id == lesson_id,
                              m.Skill.skill_id == skill_id)
    skill = db.execute(q).scalars().first()
    if skill is None:
        skill = m.Skill(course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
        db.add(skill)
        db.flush()
    skill.extraction_active = True
    if name:
        skill.name = name
    if description:
        skill.description = description
    if key_concepts is not None:
        skill.key_concepts = key_concepts
    for field, value in (educational_metadata or {}).items():
        if field in {"learning_objective", "prerequisites", "misconceptions", "difficulty", "source_section_ids", "evidence_chunk_ids", "learning_content"}:
            setattr(skill, field, value)
    skill.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(skill)
    return skill


def list_skills(db: Session, *, course_id: str, lesson_id: str) -> list[m.Skill]:
    q = select(m.Skill).where(m.Skill.course_id == course_id, m.Skill.lesson_id == lesson_id, m.Skill.extraction_active.is_(True))
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
    if skill.explanation != explanation:
        skill.audio_path = ""
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
                questions: list[dict], teacher_feedback: str = "",
                teacher_id: str | None = None, classroom_id: str | None = None,
                material_id: str | None = None) -> m.QuestionBank:
    # Counter UPDATE obtains the database write lock; concurrent writers cannot
    # allocate the same version, including on old banks lacking a unique index.
    for attempt in range(3):
        try:
            key = dict(course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
            counter = db.get(m.BankVersionCounter, (course_id, lesson_id, skill_id))
            if counter is None:
                with db.begin_nested():
                    db.add(m.BankVersionCounter(**key, version=next_bank_version(db, **key) - 1))
                    db.flush()
            version = db.execute(update(m.BankVersionCounter).where(
                m.BankVersionCounter.course_id == course_id, m.BankVersionCounter.lesson_id == lesson_id,
                m.BankVersionCounter.skill_id == skill_id).values(version=m.BankVersionCounter.version + 1)
                .returning(m.BankVersionCounter.version)).scalar_one()
            bank = m.QuestionBank(**key, version=version, status="pending_review", teacher_feedback=teacher_feedback,
                                  teacher_id=teacher_id, classroom_id=classroom_id, material_id=material_id)
            db.add(bank)
            db.flush()
            for qd in questions:
                db.add(m.Question(question_bank_id=bank.id, **qd))
            db.commit()
            db.refresh(bank)
            return bank
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise
    raise RuntimeError("Unable to allocate bank version")


def get_bank(db: Session, bank_id: str) -> m.QuestionBank | None:
    return db.get(m.QuestionBank, bank_id)


def list_banks(db: Session, *, status: str | None = None,
               teacher_id: str | None = None, classroom_id: str | None = None,
               material_id: str | None = None, skill_id: str | None = None,
               lesson_id: str | None = None) -> list[m.QuestionBank]:
    q = select(m.QuestionBank).order_by(desc(m.QuestionBank.created_at))
    if status:
        q = q.where(m.QuestionBank.status == status)
    if teacher_id:
        q = q.where(m.QuestionBank.teacher_id == teacher_id)
    if classroom_id:
        q = q.where(m.QuestionBank.classroom_id == classroom_id)
    if material_id:
        q = q.where(m.QuestionBank.material_id == material_id)
    if skill_id:
        q = q.where(m.QuestionBank.skill_id == skill_id)
    if lesson_id:
        q = q.where(m.QuestionBank.lesson_id == lesson_id)
    return list(db.execute(q).scalars().all())


def update_question(db: Session, question: m.Question, **fields) -> m.Question:
    for key, value in fields.items():
        if hasattr(question, key):
            setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question: m.Question) -> None:
    # Preserve attempt and feedback history while removing the question from use.
    question.retired = True
    db.commit()


def set_bank_status(db: Session, bank: m.QuestionBank, status: str, feedback: str = "") -> None:
    bank.status = status
    if feedback:
        bank.teacher_feedback = feedback
    bank.updated_at = datetime.datetime.utcnow()
    db.commit()


def get_questions(db: Session, bank_id: str) -> list[m.Question]:
    q = select(m.Question).where(m.Question.question_bank_id == bank_id, m.Question.retired.is_(False))
    return list(db.execute(q).scalars().all())


def get_approved_questions(db: Session, *, course_id: str | None = None,
                           lesson_id: str | None = None, skill_id: str | None = None) -> list[m.Question]:
    q = select(m.Question).options(joinedload(m.Question.bank)).join(m.QuestionBank, m.Question.question_bank_id == m.QuestionBank.id).where(
        m.QuestionBank.status == "approved", m.Question.retired.is_(False),
        ~m.Question.id.in_(select(m.QuestionFeedback.question_id).where(m.QuestionFeedback.kind == "flag")))
    if course_id:
        q = q.where(m.QuestionBank.course_id == course_id)
    if lesson_id:
        q = q.where(m.QuestionBank.lesson_id == lesson_id)
    if skill_id:
        q = q.where(m.QuestionBank.skill_id == skill_id)
    return list(db.execute(q).scalars().all())


def latest_approved_banks(db: Session, *, course_id: str | None = None,
                          lesson_id: str | None = None,
                          skill_id: str | None = None) -> list[m.QuestionBank]:
    """Latest ACTIVE approved bank version per (course_id, lesson_id, skill_id).

    History is preserved in the database; older approved versions become
    historical/superseded for future selection purely by this query-time policy.
    Historical assessments keep referencing their original question IDs via
    get_question()/get_assessment() and are unaffected.
    """
    banks = scoped_banks(db, course_id=course_id, lesson_id=lesson_id,
                         skill_id=skill_id, status="approved")
    latest: dict[tuple[str, str, str], m.QuestionBank] = {}
    for b in banks:
        key = (b.course_id, b.lesson_id, b.skill_id)
        current = latest.get(key)
        if current is None or (b.version, str(b.created_at), str(b.id)) > (
                current.version, str(current.created_at), str(current.id)):
            latest[key] = b
    return sorted(latest.values(), key=lambda b: (b.course_id, b.lesson_id, b.skill_id))


def get_latest_approved_questions(db: Session, *, course_id: str | None = None,
                                  lesson_id: str | None = None,
                                  skill_id: str | None = None) -> list[m.Question]:
    """Questions from the latest approved bank version per skill scope only.

    Flagged and retired questions are still excluded. Older approved versions
    remain in history but never leak into new student-facing selection.
    """
    banks = latest_approved_banks(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if not banks:
        return []
    allowed = {b.id for b in banks}
    flagged = set(db.scalars(select(m.QuestionFeedback.question_id).where(
        m.QuestionFeedback.kind == "flag")))
    q = select(m.Question).options(joinedload(m.Question.bank)).where(
        m.Question.question_bank_id.in_(allowed),
        m.Question.retired.is_(False))
    rows = list(db.execute(q).scalars().all())
    return [r for r in rows if r.id not in flagged]


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


def create_assessment(db: Session, *, student_id: str, question_bank_id: str, question_ids: list[str],
                      course_id: str = "", lesson_id: str = "", selection_meta: dict | None = None) -> m.Assessment:
    a = m.Assessment(student_id=student_id, question_bank_id=question_bank_id,
                     question_ids=question_ids, status="started", course_id=course_id or "",
                     lesson_id=lesson_id or "", selection_meta=selection_meta or {})
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


def get_attempt_for(db: Session, assessment_id: str, question_id: str) -> m.StudentAttempt | None:
    q = select(m.StudentAttempt).where(
        m.StudentAttempt.assessment_id == assessment_id,
        m.StudentAttempt.question_id == question_id)
    return db.execute(q).scalars().first()


def get_failed_question_ids(db: Session, student_id: str) -> list[str]:
    q = select(m.StudentAttempt).where(m.StudentAttempt.student_id == student_id,
                                       m.StudentAttempt.correct.is_(False))
    return [a.question_id for a in db.execute(q).scalars().all()]


def upsert_skill_performance(db: Session, *, student_id: str, skill_id: str, correct: bool,
                             course_id: str = "", lesson_id: str = "",
                             skill_row_id: str | None = None) -> m.StudentSkillPerformance:
    # Prefer the scoped row (student+course+lesson+skill); fall back to the legacy
    # unscoped row for backwards compatibility with pre-platform data.
    perf = None
    if course_id or lesson_id:
        q = select(m.StudentSkillPerformance).where(
            m.StudentSkillPerformance.student_id == student_id,
            m.StudentSkillPerformance.course_id == course_id,
            m.StudentSkillPerformance.lesson_id == lesson_id,
            m.StudentSkillPerformance.skill_id == skill_id)
        perf = db.execute(q).scalars().first()
    if perf is None:
        legacy = db.scalar(select(m.StudentSkillPerformance).where(
            m.StudentSkillPerformance.student_id == student_id,
            m.StudentSkillPerformance.skill_id == skill_id,
            or_(m.StudentSkillPerformance.course_id == "", m.StudentSkillPerformance.course_id.is_(None)),
            or_(m.StudentSkillPerformance.lesson_id == "", m.StudentSkillPerformance.lesson_id.is_(None))))
        if legacy is not None:
            scopes = set(db.execute(select(m.QuestionBank.course_id, m.QuestionBank.lesson_id)
                .join(m.Question, m.Question.question_bank_id == m.QuestionBank.id)
                .join(m.StudentAttempt, m.StudentAttempt.question_id == m.Question.id)
                .where(m.StudentAttempt.student_id == student_id, m.Question.skill_id == skill_id)).all())
            if not scopes:
                scopes = {(r.course_id, r.lesson_id) for r in scoped_skills(db, skill_id=skill_id)}
            if not course_id and not lesson_id or scopes == {(course_id, lesson_id)}:
                perf = legacy
    if perf is None:
        perf = m.StudentSkillPerformance(student_id=student_id, skill_id=skill_id,
                                         course_id=course_id or "", lesson_id=lesson_id or "",
                                         skill_row_id=skill_row_id)
        db.add(perf)
        db.flush()
    else:
        # Heal legacy rows: adopt scope once known (prevents cross-lesson collisions).
        if course_id and not perf.course_id:
            perf.course_id = course_id
        if lesson_id and not perf.lesson_id:
            perf.lesson_id = lesson_id
        if skill_row_id and not perf.skill_row_id:
            perf.skill_row_id = skill_row_id
    perf.total_attempts += 1
    if correct:
        perf.correct_attempts += 1
    perf.accuracy = perf.correct_attempts / perf.total_attempts if perf.total_attempts else 0.0
    perf.last_updated = datetime.datetime.utcnow()
    db.commit()
    db.refresh(perf)
    return perf


def get_skill_performance(db: Session, student_id: str, *,
                           course_id: str | None = None,
                           lesson_id: str | None = None) -> list[m.StudentSkillPerformance]:
    q = select(m.StudentSkillPerformance).where(m.StudentSkillPerformance.student_id == student_id)
    if course_id:
        q = q.where(m.StudentSkillPerformance.course_id == course_id)
    if lesson_id:
        q = q.where(m.StudentSkillPerformance.lesson_id == lesson_id)
    return list(db.execute(q).scalars().all())


# Append-only quality feedback; approval/rejection are separate workflow actions.
def flag_question(db, question_id, reason, teacher_id=None):
    if not db.get(m.Question, question_id):
        raise ValueError("Question not found")
    if not reason or not reason.strip():
        raise ValueError("A flag reason is required")
    row = m.QuestionFeedback(question_id=question_id, reason=reason.strip(), teacher_id=teacher_id, kind="flag")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_flags(db, *, bank_id=None):
    query = select(m.QuestionFeedback).join(m.Question, m.Question.id == m.QuestionFeedback.question_id)
    if bank_id:
        query = query.where(m.Question.question_bank_id == bank_id)
    return list(db.scalars(query.order_by(m.QuestionFeedback.created_at)))


def get_flagged_question_ids(db):
    return set(db.scalars(select(m.QuestionFeedback.question_id).where(m.QuestionFeedback.kind == "flag")))


def get_flag_reasons_for_skill(db, *, course_id, lesson_id, skill_id):
    return list(db.scalars(select(m.QuestionFeedback.reason).join(m.Question,
        m.Question.id == m.QuestionFeedback.question_id).join(m.QuestionBank,
        m.QuestionBank.id == m.Question.question_bank_id).where(m.QuestionFeedback.kind == "flag",
        m.QuestionBank.course_id == course_id, m.QuestionBank.lesson_id == lesson_id,
        m.QuestionBank.skill_id == skill_id).order_by(m.QuestionFeedback.created_at.desc()).limit(20)))


def set_media(db, row, **fields):
    for name in ("audio_path", "image_path", "image_url", "image_alt"):
        if name in fields:
            setattr(row, name, fields[name])
    db.commit()


def get_question(db, question_id):
    return db.get(m.Question, question_id)


def scoped_banks(db, *, course_id=None, lesson_id=None, skill_id=None, status=None):
    query = select(m.QuestionBank).order_by(m.QuestionBank.created_at, m.QuestionBank.id)
    for name, value in (("course_id", course_id), ("lesson_id", lesson_id), ("skill_id", skill_id), ("status", status)):
        if value:
            query = query.where(getattr(m.QuestionBank, name) == value)
    return list(db.scalars(query))


def scoped_skills(db, *, course_id=None, lesson_id=None, skill_id=None):
    query = select(m.Skill).where(m.Skill.extraction_active.is_(True))
    for name, value in (("course_id", course_id), ("lesson_id", lesson_id), ("skill_id", skill_id)):
        if value:
            query = query.where(getattr(m.Skill, name) == value)
    return list(db.scalars(query))


def study_rows(db, *, course_id, lesson_id):
    banks = latest_approved_banks(db, course_id=course_id, lesson_id=lesson_id)
    questions = get_latest_approved_questions(db, course_id=course_id, lesson_id=lesson_id)
    return get_lesson_explanation(db, course_id=course_id, lesson_id=lesson_id), list_skills(db, course_id=course_id, lesson_id=lesson_id), banks, questions


def finish_assessment(db, assessment, score):
    assessment.status = "submitted"
    assessment.score = score
    db.commit()
