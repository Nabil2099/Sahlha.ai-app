"""Business logic lives here; routes stay thin. All DB writes happen here."""
from __future__ import annotations

from sqlalchemy.orm import Session

from sahlha.app.agent.agent import SahlhaAgent
from sahlha.app.agent.state import AgentState
from sahlha.app.agent.tools import question_tools
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag import ingestion


def upload_and_process(db: Session, *, file_bytes: bytes, filename: str,
                       course_id: str, lesson_id: str, skill_id: str) -> dict:
    return ingestion.ingest_upload(db, file_bytes=file_bytes, filename=filename,
                                   course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)


def generate_bank(db: Session, *, course_id: str, lesson_id: str, skill_id: str,
                  teacher_feedback: str = "", n_questions: int = 8) -> dict:
    agent = SahlhaAgent(db, AgentState())
    return agent.generate_question_bank(course_id=course_id, lesson_id=lesson_id, skill_id=skill_id,
                                        teacher_feedback=teacher_feedback, n_questions=n_questions)


def extract_skills(db: Session, *, course_id: str, lesson_id: str,
                   n_skills: int | None = None, max_skills: int | None = None, force: bool = False) -> dict:
    """Agent splits the lesson into skills AND writes an explanation per skill.

    Also ensures the whole-lesson overview explanation exists.
    `max_skills=None` (default) uses the dynamic lesson-complexity cap.
    """
    agent = SahlhaAgent(db, AgentState())
    out = agent.extract_skills(course_id=course_id, lesson_id=lesson_id,
                               max_skills=n_skills if n_skills is not None else max_skills,
                               force=force)
    explained = agent.explain_skills(course_id=course_id, lesson_id=lesson_id,
                                     force=force or out.get("backend") != "existing")
    lesson = agent.explain_lesson(course_id=course_id, lesson_id=lesson_id, force=force)
    return {"skills": explained["skills"], "lesson": lesson["lesson"],
            "extraction_backend": out.get("backend"), "trace": lesson["trace"]}


def explain_lesson(db: Session, *, course_id: str, lesson_id: str, force: bool = False) -> dict:
    """Agent writes (or returns) the overview explanation for a whole lesson."""
    return SahlhaAgent(db, AgentState()).explain_lesson(course_id=course_id,
                                                        lesson_id=lesson_id, force=force)


def get_lesson(db: Session, *, course_id: str, lesson_id: str) -> dict:
    """Student-facing study bundle: lesson overview + per-skill explanations."""
    from sahlha.app.services.platform import study_bundle
    return study_bundle(db, course_id=course_id, lesson_id=lesson_id)


def list_skills(db: Session, *, course_id: str, lesson_id: str,
                skill_id: str | None = None) -> list[dict]:
    rows = repo.list_skills(db, course_id=course_id, lesson_id=lesson_id)
    if skill_id:
        rows = [s for s in rows if s.skill_id == skill_id]
    from sahlha.app.agent.tools.skill_tools import serialize_skill
    return [serialize_skill(s) for s in rows]


def generate_lesson_banks(db: Session, *, course_id: str, lesson_id: str,
                          teacher_feedback: str = "", n_questions: int = 10) -> dict:
    """One question bank (n_questions each) per skill of the lesson."""
    agent = SahlhaAgent(db, AgentState())
    return agent.generate_lesson_banks(course_id=course_id, lesson_id=lesson_id,
                                       teacher_feedback=teacher_feedback, n_questions=n_questions)


def approve_bank(db: Session, bank_id: str) -> dict:
    bank = repo.get_bank(db, bank_id)
    if not bank:
        raise ValueError("Question bank not found")
    repo.set_bank_status(db, bank, "approved")
    return {"id": bank.id, "status": "approved", "version": bank.version}


def reject_bank(db: Session, bank_id: str, feedback: str = "") -> dict:
    bank = repo.get_bank(db, bank_id)
    if not bank:
        raise ValueError("Question bank not found")
    repo.set_bank_status(db, bank, "rejected", feedback)
    return {"id": bank.id, "status": "rejected", "version": bank.version, "feedback": feedback}


def start_assessment(db: Session, *, student_id: str, student_name: str = "Student",
                     course_id: str | None = None, lesson_id: str | None = None,
                     skill_id: str | None = None, learned_only: bool = False) -> dict:
    repo.get_or_create_student(db, student_id, student_name)
    agent = SahlhaAgent(db, AgentState())
    return agent.start_assessment(student_id=student_id, course_id=course_id,
                                  lesson_id=lesson_id, skill_id=skill_id, learned_only=learned_only)


def submit_assessment(db: Session, *, assessment_id: str, answers: dict) -> dict:
    agent = SahlhaAgent(db, AgentState())
    return agent.submit_assessment(assessment_id=assessment_id, answers=answers)


def student_performance(db: Session, student_id: str) -> dict:
    student = repo.get_student(db, student_id)
    if not student:
        raise ValueError("Student not found")
    attempts = repo.get_attempts(db, student_id)
    perf = repo.get_skill_performance(db, student_id)
    return {
        "student_id": student.id, "name": student.name,
        "attempts": [{"question_id": a.question_id, "assessment_id": a.assessment_id,
                      "answer": a.answer, "correct": a.correct,
                      "timestamp": a.timestamp.isoformat()} for a in attempts],
        "failed_questions": [a.question_id for a in attempts if not a.correct],
        "skill_performance": [{"skill_id": p.skill_id, "total": p.total_attempts,
                               "correct": p.correct_attempts, "accuracy": p.accuracy} for p in perf],
    }


def pending_banks(db: Session) -> list[dict]:
    return [{"id": b.id, "course_id": b.course_id, "lesson_id": b.lesson_id,
             "skill_id": b.skill_id, "version": b.version, "status": b.status,
             "feedback": b.teacher_feedback,
             "num_questions": len(repo.get_questions(db, b.id))} for b in repo.list_banks(db, status="pending_review")]


def bank_detail(db: Session, bank_id: str) -> dict | None:
    return question_tools.get_question_bank(db, bank_id)


def skill_audio(db: Session, *, course_id: str, lesson_id: str,
                skill_id: str, voice: str | None = None) -> dict:
    from sahlha.app.agent.tools import audio_tools

    return audio_tools.skill_explanation_to_audio(db, course_id=course_id, lesson_id=lesson_id,
                                                  skill_id=skill_id, voice=voice)


def lesson_audio(db: Session, *, course_id: str, lesson_id: str,
                 voice: str | None = None) -> dict:
    from sahlha.app.agent.tools import audio_tools

    return audio_tools.lesson_explanation_to_audio(db, course_id=course_id,
                                                   lesson_id=lesson_id, voice=voice)


def skill_image(db: Session, *, course_id: str, lesson_id: str,
                skill_id: str, force: bool = False) -> dict:
    from sahlha.app.agent.tools import image_tools

    return image_tools.fetch_skill_image(db, course_id=course_id, lesson_id=lesson_id,
                                         skill_id=skill_id, force=force)


def skill_progress(db: Session, *, student_id: str, course_id: str, lesson_id: str) -> dict:
    """Skill = explanation + exercise: per-skill study/exercise status for one student.

    completed = student has attempted at least one full 4-question exercise for the skill.
    """
    from sahlha.app.config import settings

    student = repo.get_student(db, student_id)
    if not student:
        raise ValueError("Student not found")
    # Readiness uses the latest active approved bank per skill; attempt mapping
    # keeps history so old progress is preserved.
    latest = repo.get_latest_approved_questions(db, course_id=course_id, lesson_id=lesson_id)
    history = repo.get_approved_questions(db, course_id=course_id, lesson_id=lesson_id)
    by_skill: dict[str, list] = {}
    for q in latest:
        by_skill.setdefault(q.skill_id, []).append(q)
    # Map the student's attempts onto skills via question -> bank -> skill.
    q_to_skill: dict[str, str] = {}
    for q in history:
        q_to_skill[q.id] = q.skill_id
    per_skill_attempts: dict[str, list] = {}
    for a in repo.get_attempts(db, student_id, limit=10000):
        skid = q_to_skill.get(a.question_id)
        if skid:
            per_skill_attempts.setdefault(skid, []).append(a)

    skills = []
    for s in repo.list_skills(db, course_id=course_id, lesson_id=lesson_id):
        atts = per_skill_attempts.get(s.skill_id, [])
        correct = sum(1 for a in atts if a.correct)
        bank_questions = len(by_skill.get(s.skill_id, []))
        skills.append({
            "skill_id": s.skill_id, "name": s.name, "description": s.description,
            "has_explanation": bool(s.explanation),
            "bank_questions": bank_questions,  # approved questions available
            "exercise_ready": bank_questions >= settings.assessment_num_questions,
            "attempted": len(atts), "correct": correct,
            "accuracy": (correct / len(atts)) if atts else None,
            "completed": len(atts) >= settings.assessment_num_questions,
        })
    done = sum(1 for s in skills if s["completed"])
    return {"student_id": student_id, "course_id": course_id, "lesson_id": lesson_id,
            "skills": skills, "completed": done, "total": len(skills)}
