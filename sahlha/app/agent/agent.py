"""Single Sahlha learning agent: explicit state-machine runtime.

Flow per phase:
  SKILL_EXTRACTION: retrieve_lesson -> LLM splits lesson into skills (persisted)
  SKILL_EXPLANATION: per skill, retrieve skill material -> LLM writes grounded explanation
  QUESTION_GENERATION: per skill, retrieve skill material -> LLM/fallback structured gen
      -> validate -> save_questions (one bank per skill) -> WAITING_FOR_TEACHER
  (teacher approves/rejects each bank via API — explicit workflow boundary, never auto-bypassed)
  ASSESSMENT: get_approved_questions + get_student_history -> select_questions (exactly 4)
  EVALUATION: evaluate_answer -> record_attempt -> update_student_memory -> ADAPTATION
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from sahlha.app.agent.llm import (
    complete_json,
    generate_questions_llm,
)
from sahlha.app.agent.prompts import (
    build_question_prompt,
    build_skill_extraction_prompt,
)
from sahlha.app.agent.schemas import SkillList
from sahlha.app.agent.state import AgentState, Phase
from sahlha.app.agent.tools import assessment_tools, question_tools, rag_tools, student_tools, skill_tools, explanation_tools


class SahlhaAgent:
    def __init__(self, db: Session, state: AgentState | None = None):
        self.db = db
        self.state = state or AgentState()

    # ---------- SKILL EXTRACTION + EXPLANATION ----------
    def extract_skills(self, *, course_id: str, lesson_id: str, max_skills: int = 6,
                       force: bool = False, n_skills: int | None = None) -> dict:
        """Split a lesson into skills (one per topic; the AGENT decides how many).

        Idempotent unless force=True. `max_skills` is only an upper-bound safety cap.
        `n_skills` is a deprecated alias kept for backwards compatibility.
        """
        if n_skills is not None:
            max_skills = n_skills
        st = self.state
        st.course_id, st.lesson_id = course_id, lesson_id
        st.current_phase = Phase.SKILL_EXTRACTION
        st.log("phase", st.current_phase)
        from sahlha.app.agent.tools import content_tools
        from sahlha.app.agent.pedagogy import DISCOVERY_VERSION
        content_map, chunks = content_tools.build_content_map(self.db, course_id, lesson_id)
        if not force and content_map.get('skills_version') == DISCOVERY_VERSION:
            existing = skill_tools.list_skills(self.db, course_id=course_id, lesson_id=lesson_id)
            if existing and all(s.evidence_chunk_ids and s.learning_objective for s in existing):
                skills = [self._skill_to_dict(s) for s in existing]
                st.skills = skills
                st.log("skills:existing", {"count": len(skills)})
                return {"skills": skills, "backend": "existing", "trace": st.trace}

        if not chunks:
            content_tools.retire_superseded_skills(self.db, course_id, lesson_id, set())
            raise ValueError("No instructional lesson content is available for skill discovery. Titles, indexes and publication details cannot support skills.")
        st.log("tool:full_lesson_map", {"num_chunks": len(chunks), "sections": len(content_map['sections'])})
        raw, backends = [], []
        # Every ordered chunk is mapped. Each request is bounded; there is no
        # global prefix truncation or relevance top-k during topic discovery.
        for chunk in chunks:
            system, user = build_skill_extraction_prompt(course_id=course_id, lesson_id=lesson_id,
                context_chunks=[chunk], max_skills=max_skills)
            try:
                data, backend = complete_json(system, user)
                validated = SkillList(skills=data["skills"] if isinstance(data, dict) else data).skills
                mapped = [item.model_dump() for item in validated]
            except Exception as exc:
                mapped = content_tools.fallback_topics([chunk])
                backend = f"fallback({type(exc).__name__})"
            # Validate each section before combining. A malformed model response
            # must not suppress useful fallback topics in the rest of the lesson.
            mapped, _ = content_tools.validate_skills(mapped, [chunk], max(1, max_skills))
            if not mapped:
                mapped = content_tools.fallback_topics([chunk])
            raw.extend(mapped)
            backends.append(backend)
        raw, warnings = content_tools.validate_skills(raw, chunks, max(1, max_skills))
        if not raw:
            raw, extra = content_tools.validate_skills(content_tools.fallback_topics(chunks), chunks, max(1, max_skills))
            warnings.extend(extra)
        if not raw:
            raise ValueError("No evidence-supported teachable topics could be extracted. Review extraction quality.")
        content_tools.save_mapped_topics(self.db, course_id, lesson_id, content_map, raw, warnings)
        backend = ','.join(dict.fromkeys(backends))
        st.log("llm:extract_skills", {"backend": backend, "count": len(raw), "warnings": warnings})

        skills = []
        for s in raw[: max(1, max_skills)]:
            row = skill_tools.register_skill(self.db, course_id=course_id, lesson_id=lesson_id, skill=s)
            skills.append(self._skill_to_dict(row))
        content_tools.retire_superseded_skills(self.db, course_id, lesson_id, {s["skill_id"] for s in skills})
        st.skills = skills
        return {"skills": skills, "backend": backend, "trace": st.trace}

    def explain_skills(self, *, course_id: str, lesson_id: str, force: bool = False) -> dict:
        self.state.current_phase = Phase.SKILL_EXPLANATION
        self.state.log("phase", self.state.current_phase)
        out = []
        for row in skill_tools.list_skills(self.db, course_id=course_id, lesson_id=lesson_id):
            result = explanation_tools.explain_skill(self.db, course_id=course_id,
                lesson_id=lesson_id, skill_id=row.skill_id, force=force)
            self.state.log("llm:explain_skill", {"skill_id": row.skill_id, "backend": result["backend"]})
            self.state.log("media:skill", result["media"])
            out.append(result["skill"])
        self.state.skills = out
        return {"skills": out, "trace": self.state.trace}

    def explain_lesson(self, *, course_id: str, lesson_id: str, force: bool = False) -> dict:
        self.state.current_phase = Phase.LESSON_EXPLANATION
        self.state.log("phase", self.state.current_phase)
        result = explanation_tools.explain_lesson(self.db, course_id=course_id, lesson_id=lesson_id, force=force)
        self.state.log("llm:explain_lesson", {"backend": result["backend"]})
        self.state.log("media:lesson", result["media"])
        return {**result, "trace": self.state.trace}

    _lesson_to_dict = staticmethod(explanation_tools.serialize_lesson)

    def generate_lesson_banks(self, *, course_id: str, lesson_id: str,
                              teacher_feedback: str = "", n_questions: int = 6) -> dict:
        """One question bank per skill of the lesson (skills extracted/explained first if missing)."""
        st = self.state
        if not skill_tools.list_skills(self.db, course_id=course_id, lesson_id=lesson_id):
            self.extract_skills(course_id=course_id, lesson_id=lesson_id)
            self.explain_skills(course_id=course_id, lesson_id=lesson_id)
        banks = []
        for row in skill_tools.list_skills(self.db, course_id=course_id, lesson_id=lesson_id):
            banks.append(self.generate_question_bank(
                course_id=course_id, lesson_id=lesson_id, skill_id=row.skill_id,
                teacher_feedback=teacher_feedback, n_questions=n_questions))
        return {"lesson_id": lesson_id, "num_skills": len(banks), "banks": banks, "trace": st.trace}

    _skill_to_dict = staticmethod(skill_tools.serialize_skill)

    # ---------- QUESTION GENERATION (per skill) ----------
    def generate_question_bank(self, *, course_id: str, lesson_id: str, skill_id: str,
                               teacher_feedback: str = "", n_questions: int = 8,
                               student_id: str = "", teacher_id: str = "teacher_1") -> dict:
        st = self.state
        st.course_id, st.lesson_id, st.skill_id = course_id, lesson_id, skill_id
        st.student_id, st.teacher_id = student_id, teacher_id
        st.current_phase = Phase.QUESTION_GENERATION
        st.log("phase", Phase.QUESTION_GENERATION)

        from sahlha.app.agent.tools import content_tools
        skill_row = skill_tools.get_skill(self.db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
        objective = skill_row.learning_objective if skill_row else f'Explain {skill_id.replace("_", " ")}.'
        misconceptions = skill_row.misconceptions if skill_row else []
        chunks = content_tools.skill_evidence(self.db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id,
            query=f"{skill_row.name if skill_row else skill_id} {objective}")
        for chunk in chunks:
            chunk['learning_objective'] = objective
        if not chunks:
            raise ValueError("No source evidence is available within this skill scope.")
        st.retrieved_context = chunks
        st.log("tool:retrieve_skill_material", {"skill_id": skill_id, "num_chunks": len(chunks),
                                                "chunk_ids": [c.get("chunk_id") for c in chunks]})

        reasons = question_tools.flag_reasons(self.db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
        if reasons:
            teacher_feedback += "\nPrevious teacher feedback to avoid:\n" + "\n".join("- " + reason for reason in reasons)
        st.log("teacher:flag_context", {"count": len(reasons)})
        system, user = build_question_prompt(course_id=course_id, lesson_id=lesson_id,
                                             skill_id=skill_id, context_chunks=chunks,
                                             feedback=teacher_feedback, n=n_questions)
        user += f"\nLearning objective: {objective}\nKnown misconceptions: {misconceptions}"
        questions, backend = generate_questions_llm(system, user, chunks, skill_id, n_questions, teacher_feedback)
        st.log("llm:generate_questions", {"backend": backend, "num_questions": len(questions)})
        from sahlha.app.agent.tools.critique_tools import critique_and_top_up
        questions, critique = critique_and_top_up(questions, chunks, skill_id, n_questions, teacher_feedback)
        st.log("questions:critique", critique)

        saved = question_tools.save_questions(self.db, course_id=course_id, lesson_id=lesson_id,
                                              skill_id=skill_id, questions=questions,
                                              teacher_feedback=teacher_feedback)
        st.log("tool:save_questions", saved)
        st.current_phase = Phase.WAITING_FOR_TEACHER
        st.log("phase", Phase.WAITING_FOR_TEACHER)
        return {**saved, "backend": backend, "trace": st.trace,
                "retrieved_chunks": len(chunks)}

    # ---------- ASSESSMENT ----------
    def start_assessment(self, *, student_id: str, course_id: str | None = None,
                         lesson_id: str | None = None, skill_id: str | None = None, learned_only: bool = False) -> dict:
        st = self.state
        st.student_id = student_id
        st.current_phase = Phase.ASSESSMENT
        st.log("phase", Phase.ASSESSMENT)
        student_tools.ensure_student(self.db, student_id)

        approved = question_tools.get_approved_questions(self.db, course_id=course_id,
                                                         lesson_id=lesson_id, skill_id=skill_id)
        st.log("tool:get_approved_questions", {"count": len(approved)})
        history = student_tools.get_student_history(self.db, student_id)
        perf = student_tools.get_student_skill_performance(self.db, student_id, course_id=course_id, lesson_id=lesson_id)
        st.student_memory = {"history_count": len(history), "performance": perf,
                             "failed": student_tools.get_failed_questions(self.db, student_id)}
        st.log("tool:get_student_history", st.student_memory)

        selected, meta = assessment_tools.select_questions(self.db, student_id=student_id,
                                                           course_id=course_id, lesson_id=lesson_id,
                                                           skill_id=skill_id, learned_only=learned_only)
        st.log("tool:select_questions", meta)
        st.current_question_ids = [q["id"] for q in selected]
        bank_id = selected[0]["bank_id"] if selected else ""
        assessment = assessment_tools.create_assessment(self.db, student_id=student_id,
                                            question_bank_id=bank_id,
                                            question_ids=st.current_question_ids, course_id=course_id or "",
                                            lesson_id=lesson_id or "", selection_meta=meta)
        explanations, lesson_explanation = assessment_tools.study_context(self.db, selected)
        st.log("tool:study_context", {"skills": len(explanations), "lesson_overview": lesson_explanation is not None})
        # Student-facing payload must NOT include correct answers
        public = [{k: q[k] for k in ("id", "bank_id", "skill_id", "type", "question", "options", "difficulty")
                   if k in q} for q in selected]
        return {"assessment_id": assessment.id, "student_id": student_id,
                "questions": public, "lesson_explanation": lesson_explanation,
                "skill_explanations": explanations,
                "selection_meta": meta, "trace": st.trace}

    # ---------- EVALUATION ----------
    def submit_assessment(self, *, assessment_id: str, answers: dict[str, object]) -> dict:
        st = self.state
        st.current_phase = Phase.EVALUATION
        st.log("phase", Phase.EVALUATION)
        assessment = assessment_tools.get_assessment(self.db, assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")
        st.current_answers = answers
        results: list[dict] = []
        for qid in assessment.question_ids:
            q = question_tools.get_question(self.db, qid)
            if not q:
                continue
            existing = assessment_tools.get_attempt_for(self.db, assessment_id, qid)
            if existing is not None:
                # Already checked inline (attempt locked at check time): reuse it.
                results.append({"question_id": qid, "correct": existing.correct,
                                "student_answer": existing.answer,
                                "correct_answer": q.correct_answer,
                                "skill_id": q.skill_id})
                continue
            qdict = {"id": q.id, "skill_id": q.skill_id, "type": q.question_type,
                     "correct_answer": q.correct_answer}
            res = assessment_tools.evaluate_answer(qdict, answers.get(qid))
            assessment_tools.record_attempt(self.db, student_id=assessment.student_id,
                                            question_id=qid, assessment_id=assessment_id,
                                            answer=answers.get(qid), correct=res["correct"])
            student_tools.update_memory_for_question(self.db, student_id=assessment.student_id,
                                                     question=q, correct=res["correct"])
            st.log("tool:record_attempt", {"question_id": qid, "correct": res["correct"]})
            results.append(res)
        correct = sum(1 for r in results if r["correct"])
        assessment_tools.finish_assessment(self.db, assessment, correct / len(results) if results else 0.0)
        st.assessment_result = {"assessment_id": assessment_id, "score": assessment.score,
                                "correct": correct, "total": len(results), "results": results}
        st.current_phase = Phase.ADAPTATION
        st.log("phase", Phase.ADAPTATION)
        perf = student_tools.get_student_skill_performance(self.db, assessment.student_id,
            course_id=assessment.course_id or None, lesson_id=assessment.lesson_id or None)
        return {**st.assessment_result, "skill_performance": perf, "trace": st.trace}
