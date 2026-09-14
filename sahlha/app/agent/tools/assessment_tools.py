"""Assessment tools: deterministic selection + evaluation + attempt recording.

The LLM reasons over memory; THIS module controls IDs, scoring, persistence.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from sahlha.app.config import settings
from sahlha.app.database.repositories import repositories as repo


def select_questions(db: Session, *, student_id: str, course_id: str | None = None,
                     lesson_id: str | None = None, skill_id: str | None = None,
                     n_per_bank: int | None = None) -> tuple[list[dict], dict]:
    """Select exactly `n_per_bank` questions from EACH approved question bank.

    Banks are per-skill, so the assessment covers every skill with the same
    memory-aware heuristics applied inside each bank:
    1. Questions previously failed by this student (retry, if still approved)
    2. Questions in weak skills (accuracy < 0.6)
    3. Unseen questions
    4. Fill remainder, balancing difficulty, avoiding repetition within assessment.
    """
    from sahlha.app.agent.tools import question_tools, student_tools

    n_per_bank = n_per_bank or settings.assessment_num_questions
    pool = question_tools.get_approved_questions(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if not pool:
        raise ValueError("No approved questions found. Approve a bank first.")
    # Group pool by bank (stable order) — one selection round per bank.
    banks: dict[str, list[dict]] = {}
    for q in pool:
        banks.setdefault(q["bank_id"], []).append(q)

    history = student_tools.get_student_history(db, student_id)
    failed_ids = set(student_tools.get_failed_questions(db, student_id))
    seen_ids = {h["question_id"] for h in history}
    perf = {p["skill_id"]: p["accuracy"] for p in student_tools.get_student_skill_performance(db, student_id)}
    weak_skills = {s for s, acc in perf.items() if acc < 0.6}

    selected: list[dict] = []
    rationale: list[str] = []
    per_bank: dict[str, int] = {}

    def _take(group: list[dict], cands: list[dict], reason: str):
        for q in cands:
            if len(group) >= n_per_bank:
                break
            if q["id"] not in {s["id"] for s in group}:
                group.append(q)
                rationale.append(f"{q['id']} (bank={q['bank_id']}, {q['skill_id']}/{q['difficulty']}): {reason}")

    for bank_id, group_pool in banks.items():
        if len(group_pool) < n_per_bank:
            raise ValueError(
                f"Bank {bank_id} has only {len(group_pool)} approved questions, "
                f"need {n_per_bank} per bank.")
        by_id = {q["id"]: q for q in group_pool}
        group: list[dict] = []
        _take(group, [by_id[i] for i in failed_ids if i in by_id], "retry previously failed")
        _take(group, [q for q in group_pool if q["skill_id"] in weak_skills
                      and q["id"] not in {s["id"] for s in group}], "targets weak skill")
        _take(group, [q for q in group_pool if q["id"] not in seen_ids
                      and q["id"] not in {s["id"] for s in group}], "unseen question")
        have = {q["difficulty"] for q in group}
        for diff in ("easy", "medium", "hard"):
            if len(group) >= n_per_bank:
                break
            if diff not in have:
                _take(group, [q for q in group_pool if q["difficulty"] == diff
                              and q["id"] not in {s["id"] for s in group}],
                      f"balances difficulty ({diff})")
        _take(group, group_pool, "fill remainder")
        selected.extend(group[:n_per_bank])
        per_bank[bank_id] = len(group[:n_per_bank])

    return selected, {"rationale": rationale, "weak_skills": sorted(weak_skills),
                      "failed_retried": sorted(failed_ids & {s["id"] for s in selected}),
                      "per_bank": per_bank, "n_per_bank": n_per_bank}


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
