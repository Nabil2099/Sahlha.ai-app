"""Relational schema for the MVP learning loop."""
import datetime
import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sahlha.app.database.database import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    filename: Mapped[str] = mapped_column(String(512))
    course_id: Mapped[str] = mapped_column(String(128), default="general")
    lesson_id: Mapped[str] = mapped_column(String(128), default="lesson_1")
    skill_id: Mapped[str] = mapped_column(String(128), default="general")
    status: Mapped[str] = mapped_column(String(32), default="uploaded")  # uploaded|processed|failed
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    document_id: Mapped[str] = mapped_column(String(32), ForeignKey("documents.id"))
    course_id: Mapped[str] = mapped_column(String(128), default="general")
    lesson_id: Mapped[str] = mapped_column(String(128), default="lesson_1")
    skill_id: Mapped[str] = mapped_column(String(128), default="general")
    page: Mapped[int] = mapped_column(Integer, default=0)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)


class LessonExplanation(Base):
    """Agent-written overview of a whole lesson (one per lesson).

    Shown to the student first, before the per-skill explanations and the exercise.
    """
    __tablename__ = "lesson_explanations"
    __table_args__ = (UniqueConstraint("course_id", "lesson_id", name="uq_lesson_explanation"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    course_id: Mapped[str] = mapped_column(String(128), default="general")
    lesson_id: Mapped[str] = mapped_column(String(128), default="lesson_1")
    title: Mapped[str] = mapped_column(String(256), default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    key_concepts: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Skill(Base):
    """A skill extracted by the agent from a lesson.

    Each skill gets an agent-written explanation and its own question bank(s).
    """
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("course_id", "lesson_id", "skill_id", name="uq_lesson_skill"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    course_id: Mapped[str] = mapped_column(String(128), default="general")
    lesson_id: Mapped[str] = mapped_column(String(128), default="lesson_1")
    skill_id: Mapped[str] = mapped_column(String(128))  # agent-generated slug, e.g. python_elif_basics
    name: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")  # agent-written, grounded in lesson chunks
    key_concepts: Mapped[list] = mapped_column(JSON, default=list)
    image_url: Mapped[str] = mapped_column(String(1024), default="")  # Pexels source page
    image_path: Mapped[str] = mapped_column(String(1024), default="")  # local cached file
    image_alt: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class QuestionBank(Base):
    __tablename__ = "question_banks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    course_id: Mapped[str] = mapped_column(String(128), default="general")
    lesson_id: Mapped[str] = mapped_column(String(128), default="lesson_1")
    skill_id: Mapped[str] = mapped_column(String(128), default="general")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    # pending_review | approved | rejected
    teacher_feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    questions: Mapped[list["Question"]] = relationship("Question", back_populates="bank", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    question_bank_id: Mapped[str] = mapped_column(String(32), ForeignKey("question_banks.id"))
    skill_id: Mapped[str] = mapped_column(String(128), default="general")
    question_type: Mapped[str] = mapped_column(String(32), default="multiple_choice")
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    correct_answer: Mapped[int | str] = mapped_column(JSON, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(32), default="medium")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    bank: Mapped[QuestionBank] = relationship("QuestionBank", back_populates="questions")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(256), default="Student")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"))
    question_bank_id: Mapped[str] = mapped_column(String(32), ForeignKey("question_banks.id"))
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="started")  # started|submitted
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class StudentAttempt(Base):
    __tablename__ = "student_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"))
    question_id: Mapped[str] = mapped_column(String(32), ForeignKey("questions.id"))
    assessment_id: Mapped[str] = mapped_column(String(32), ForeignKey("assessments.id"))
    answer: Mapped[int | str | None] = mapped_column(JSON, default=None)
    correct: Mapped[bool] = mapped_column(default=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class StudentSkillPerformance(Base):
    __tablename__ = "student_skill_performance"
    __table_args__ = (UniqueConstraint("student_id", "skill_id", name="uq_student_skill"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"))
    skill_id: Mapped[str] = mapped_column(String(128))
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
