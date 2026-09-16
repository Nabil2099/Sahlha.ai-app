"""Prompts owned by the LLM side (reasoning/generation). App logic stays in tools/services."""


def evidence_context(chunks, budget=16000):
    """Pack complete ranked chunks; never cut code or a table mid-character."""
    parts, size = [], 0
    for i, chunk in enumerate(chunks):
        part = f"[chunk {chunk.get('chunk_id', i)} | section={chunk.get('section_id', '')} | page={chunk.get('page', '')}] {chunk.get('text', '')}"
        if size + len(part) + 2 <= budget:
            parts.append(part)
            size += len(part) + 2
    return '\n\n'.join(parts) or '(no context retrieved)'

QUESTION_SYSTEM = """You are the Sahlha learning agent. Generate a question bank GROUNDED ONLY in the retrieved lesson material below.
Rules:
- Every question must be answerable from the provided context. Do not invent unrelated facts.
- Include evidence_chunk_ids, learning_objective, tested_concept and verification.source_quote.
- Cite exact supplied chunk IDs and an exact supporting sentence. Match the skill objective.
- Distractors must be plausible misconceptions and demonstrably wrong for the stem.
- No generic distractors such as unrelated/not mentioned. Ensure exactly one defensible answer.
- Mix difficulties: easy, medium, hard.
- Prefer multiple_choice with exactly 4 options. correct_answer is the 0-based index of the correct option.
- Cover different key concepts from the context.
- If teacher feedback is provided, follow it.
Return ONLY valid JSON: a list of question objects with keys:
skill_id, type ("multiple_choice"), question, options (4 strings), correct_answer (int), explanation, difficulty.
"""

QUESTION_USER_TEMPLATE = """Course: {course_id}\nLesson: {lesson_id}\nSkill: {skill_id}\nTeacher feedback (may be empty): {feedback}\n\n--- RETRIEVED LESSON CONTEXT ---\n{context}\n--- END CONTEXT ---\n\nGenerate {n} questions as a JSON array."""


def build_question_prompt(*, course_id: str, lesson_id: str, skill_id: str,
                          context_chunks: list[dict], feedback: str = "", n: int = 8) -> tuple[str, str]:
    context = evidence_context(context_chunks)
    user = QUESTION_USER_TEMPLATE.format(course_id=course_id, lesson_id=lesson_id,
                                         skill_id=skill_id, feedback=feedback or "(none)",
                                         context=context, n=n)
    return QUESTION_SYSTEM, user


SKILL_EXTRACTION_SYSTEM = """You are the Sahlha learning agent. Split the lesson material below into skills, where each skill is ONE TOPIC of the lesson.
Rules:
- YOU decide how many skills there are — one per distinct topic in the material. Do not aim for a fixed number; use as many as the topics require (up to the maximum below).
- Each skill must be grounded in the provided context. Do not invent topics outside it.
- Each skill must be independently learnable and testable.
- Include learning_objective, prerequisites, misconceptions, difficulty, source_section_ids, evidence_chunk_ids.
- evidence_chunk_ids MUST cite the supplied chunk identifiers. Never invent evidence.
- Reject isolated labels like True, False, Looping, Example, Output. Use teachable topics supported by the source.
- Merge overlapping topics and order prerequisites before applications.
- skill_id: short snake_case slug unique within the lesson.
- key_concepts: 3-6 short phrases taken from the material.
Return ONLY valid JSON: {"skills": [{"skill_id": ..., "name": ..., "description": ..., "key_concepts": [...]}]}.
"""

SKILL_EXTRACTION_USER_TEMPLATE = """Course: {course_id}\nLesson: {lesson_id}\nMaximum skills (upper bound only — you decide the actual number from the topics): {max_skills}\n\n--- LESSON CONTEXT ---\n{context}\n--- END CONTEXT ---"""

SKILL_EXPLANATION_SYSTEM = """You are the Sahlha learning agent. Write a clear student-facing EXPLANATION of ONE skill, grounded ONLY in the retrieved material below.
Rules:
- Explain the concept in your own teaching words, but every fact must come from the context.
- Structure: short intro, how it works, a concrete example from the material, common mistake to avoid.
- Include a backward-compatible explanation string and a learning_content object.
- learning_content fields: core_idea, steps (strings), example, common_mistake, check_understanding,
  visual_type, visual_spec, playground, audio_script.
- visual_type must be none or an appropriate subject-specific type: code_trace, loop_flow,
  condition_flow, variable_state, number_line, equation_steps, coordinate_graph,
  labeled_diagram, process_sequence, timeline, map_points, sentence_builder, word_highlight.
- visual_spec ONLY has title, items (label, detail, value, x, y), source_text (display only).
- playground ONLY has interaction (none/step/select/order/highlight), prompt, choices (strings).
- No scripts, executable code, URLs, HTML, or arbitrary expressions. Use none if no useful visual exists.
- Keep all facts, examples and visual values grounded in the supplied evidence.
Return ONLY valid JSON: {"explanation": "...", "learning_content": {...}}.
"""

SKILL_EXPLANATION_USER_TEMPLATE = """Course: {course_id}\nLesson: {lesson_id}\nSkill: {name} ({skill_id})\nDescription: {description}\nKey concepts: {concepts}\n\n--- SKILL MATERIAL ---\n{context}\n--- END MATERIAL ---"""


def build_skill_extraction_prompt(*, course_id: str, lesson_id: str,
                                  context_chunks: list[dict], max_skills: int = 6) -> tuple[str, str]:
    context = "\n\n".join(f"[chunk {c.get('chunk_id', i)}] {c.get('text', '')}"
                          for i, c in enumerate(context_chunks)) or "(no context retrieved)"
    return SKILL_EXTRACTION_SYSTEM, SKILL_EXTRACTION_USER_TEMPLATE.format(
        course_id=course_id, lesson_id=lesson_id, max_skills=max_skills, context=context)


def build_skill_explanation_prompt(*, course_id: str, lesson_id: str, skill: dict,
                                   context_chunks: list[dict]) -> tuple[str, str]:
    context = evidence_context(context_chunks)
    return SKILL_EXPLANATION_SYSTEM, SKILL_EXPLANATION_USER_TEMPLATE.format(
        course_id=course_id, lesson_id=lesson_id, name=skill.get("name", skill.get("skill_id")),
        skill_id=skill.get("skill_id"), description=skill.get("description", ""),
        concepts=", ".join(skill.get("key_concepts", [])), context=context)


LESSON_EXPLANATION_SYSTEM = """You are the Sahlha learning agent. Write a student-facing OVERVIEW of a whole LESSON, grounded ONLY in the retrieved material below.
Rules:
- Every fact must come from the context. Do not invent topics.
- Structure: what this lesson is about (2-3 sentences), the main ideas in order, how the listed skills connect, what the student will be able to do afterwards.
- Then list 4-8 key_concepts taken from the material.
- Title: short lesson title derived from the material.
Return ONLY valid JSON: {"title": "...", "explanation": "...", "key_concepts": [...]}.
"""

LESSON_EXPLANATION_USER_TEMPLATE = """Course: {course_id}\nLesson: {lesson_id}\nSkills in this lesson: {skills}\n\n--- LESSON MATERIAL ---\n{context}\n--- END MATERIAL ---"""


def build_lesson_explanation_prompt(*, course_id: str, lesson_id: str,
                                    context_chunks: list[dict],
                                    skill_names: list[str] | None = None) -> tuple[str, str]:
    context = "\n\n".join(f"[chunk {c.get('chunk_id', i)}] {c.get('text', '')}"
                          for i, c in enumerate(context_chunks)) or "(no context retrieved)"
    return LESSON_EXPLANATION_SYSTEM, LESSON_EXPLANATION_USER_TEMPLATE.format(
        course_id=course_id, lesson_id=lesson_id,
        skills=", ".join(skill_names or []) or "(skills not extracted yet)",
        context=context[:12000])
