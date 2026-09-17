"""Assessment tools: deterministic selection + evaluation + attempt recording.

The LLM reasons over memory; THIS module controls IDs, scoring, persistence.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from sahlha.app.config import settings
from sahlha.app.database.repositories import repositories as repo


class SelectionError(ValueError):
    def __init__(self, message, metadata):
        super().__init__(message)
        self.metadata = metadata


def select_questions(db: Session, *, student_id: str, course_id=None, lesson_id=None,
                     skill_id=None, n_per_bank=None, learned_only=False):
    from collections import Counter
    from sahlha.app.agent.tools import question_tools
    n = n_per_bank or settings.assessment_num_questions
    # Student-facing selection uses ONLY the latest active approved bank
    # version per (course_id, lesson_id, skill_id). Older approved versions
    # stay in history but never leak into new assessments.
    pool = question_tools.get_latest_approved_questions(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    banks = repo.latest_approved_banks(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    skills = repo.scoped_skills(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    key = lambda row: (row.course_id, row.lesson_id, row.skill_id)
    if learned_only:
        learned = {key(p) for p in repo.get_skill_performance(
            db, student_id, course_id=course_id, lesson_id=lesson_id) if p.total_attempts > 0}
        banks = [b for b in banks if key(b) in learned]
        skills = [s for s in skills if key(s) in learned]
        allowed_banks = {b.id for b in banks}
        pool = [q for q in pool if q['bank_id'] in allowed_banks]
        if len({b.skill_id for b in banks}) < 2:
            raise SelectionError('Practice at least two skills before a Quick Check.', {})
    covered = {key(b) for b in banks}
    missing = [s for s in skills if key(s) not in covered]
    flagged = repo.get_flagged_question_ids(db)
    bank_ids = {b.id for b in banks}
    flags_in_scope = [q.id for b in banks for q in repo.get_questions(db, b.id) if q.id in flagged]
    meta = {"rationale": [], "weak_skills": [], "failed_retried": [], "per_bank": {},
            "flagged_excluded": len(flags_in_scope), "covered_skills": sorted({b.skill_id for b in banks}),
            "missing_skills": [s.skill_id for s in missing], "n_per_bank": n}
    if missing:
        raise SelectionError('No usable approved bank for skill "' + (missing[0].name or missing[0].skill_id) + '". Generate and approve its questions.', meta)
    if not pool:
        raise SelectionError("No usable approved questions found. Approve or regenerate a bank first.", meta)
    history = repo.get_attempts(db, student_id, limit=10000)
    seen = {a.question_id for a in history}
    failed = set(repo.get_failed_question_ids(db, student_id))
    perf = repo.get_skill_performance(db, student_id, course_id=course_id, lesson_id=lesson_id)
    weak = {(p.course_id, p.lesson_id, p.skill_id) for p in perf if p.total_attempts and p.accuracy < settings.mastery_developing_min}
    meta["weak_skills"] = sorted({k[2] for k in weak & covered})
    grouped = {b.id: [] for b in banks}
    for q in pool:
        grouped[q["bank_id"]].append(q)
    selected, used = [], set()
    # Weak skills are presented first without sacrificing coverage of other banks.
    for bank in sorted(banks, key=lambda b: (key(b) not in weak, b.created_at, b.id)):
        candidates = grouped[bank.id]
        if len(candidates) < n:
            row = next((s for s in skills if key(s) == key(bank)), None)
            name = row.name if row else bank.skill_id
            raise SelectionError(f'Skill "{name}" has only {len(candidates)} usable approved questions; {n} are required. Regenerate or approve more questions.', meta)
        group, difficulties = [], Counter()
        while len(group) < n:
            remaining = [q for q in candidates if q["id"] not in used]
            q = min(remaining, key=lambda q: (0 if q["id"] in failed else 1 if q["id"] not in seen else 2,
                    difficulties[q["difficulty"]], {"easy": 0, "medium": 1, "hard": 2}.get(q["difficulty"], 3), q["id"]))
            used.add(q["id"])
            group.append(q)
            difficulties[q["difficulty"]] += 1
            reason = "retry previously failed" if q["id"] in failed else "unseen question" if q["id"] not in seen else "remaining valid question"
            if key(bank) in weak:
                reason += "; targets weak skill"
            meta["rationale"].append(f"{q['id']}: {reason}; balances difficulty ({q['difficulty']})")
        selected.extend(group)
        meta["per_bank"][bank.id] = len(group)
    meta["failed_retried"] = sorted(failed & used)
    return selected, meta


def evaluate_answer(question: dict, student_answer) -> dict:
    """Structured per-question evaluation."""
    correct_answer = question["correct_answer"]
    if question.get("type") == "multiple_choice":
        try:
            correct = int(student_answer) == int(correct_answer)
        except (TypeError, ValueError):
            correct = str(student_answer).strip() == str(correct_answer).strip()
    else:
        norm = lambda v: str(v or "").strip().lower()
        correct = norm(student_answer) == norm(correct_answer) or norm(correct_answer) in norm(student_answer)
    return {"question_id": question["id"], "correct": correct, "student_answer": student_answer,
            "correct_answer": correct_answer, "skill_id": question.get("skill_id", "general")}


def record_attempt(db: Session, *, student_id: str, question_id: str, assessment_id: str,
                   answer, correct: bool) -> dict:
    att = repo.record_attempt(db, student_id=student_id, question_id=question_id,
                              assessment_id=assessment_id, answer=answer, correct=correct)
    return {"attempt_id": att.id, "correct": att.correct}

def study_context(db, selected):
    # Each question already carries its real bank scope; deduplicate by full identity.
    from sahlha.app.agent.tools.explanation_tools import serialize_lesson
    from sahlha.app.agent.tools.skill_tools import serialize_skill
    pairs = sorted({(q["course_id"], q["lesson_id"]) for q in selected})
    wanted = {(q["course_id"], q["lesson_id"], q["skill_id"]) for q in selected}
    explanations, lessons = [], []
    for course, lesson in pairs:
        rows = repo.list_skills(db, course_id=course, lesson_id=lesson)
        found = {r.skill_id for r in rows}
        explanations.extend(serialize_skill(r) for r in rows if (course, lesson, r.skill_id) in wanted)
        for _, _, skill in sorted(k for k in wanted if k[:2] == (course, lesson) and k[2] not in found):
            explanations.append({"skill_id": skill, "name": skill, "course_id": course, "lesson_id": lesson,
                                 "description": "", "explanation": "", "key_concepts": []})
        row = repo.get_lesson_explanation(db, course_id=course, lesson_id=lesson)
        if row and row.explanation:
            lessons.append(serialize_lesson(row))
    return explanations, lessons[0] if len(pairs) == 1 and lessons else None


create_assessment = repo.create_assessment
get_assessment = repo.get_assessment
get_attempt_for = repo.get_attempt_for
finish_assessment = repo.finish_assessment
