"""Grounded explanation persistence followed by independent, non-fatal media."""
from sahlha.app.agent.llm import complete_json, fallback_explanation, fallback_lesson_explanation
from sahlha.app.agent.prompts import build_skill_explanation_prompt, build_lesson_explanation_prompt
from sahlha.app.agent.schemas import SkillExplanation, LessonExplanationModel
from sahlha.app.agent.tools import rag_tools, audio_tools, image_tools, skill_tools
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.agent.tools import content_tools
from sahlha.app.agent.learning_content import LearningContent, structured_fallback


def _ensure_media(db, row, image_call, audio_call, **scope):
    result = {}
    for kind, valid, call in (("image", image_tools.valid_image_file, image_call),
                               ("audio", audio_tools.valid_audio_file, audio_call)):
        if valid(getattr(row, kind + "_path", "")):
            result[kind] = "cached"
            continue
        try:
            media = call(db, **scope)
            result[kind] = "cached" if media.get("cached") else "generated"
        except Exception as exc:
            # The explanation was committed before providers were invoked.
            db.rollback()
            result[kind] = "unavailable"
    return result


def ensure_skill_media(db, *, course_id, lesson_id, skill_id):
    row = repo.get_skill(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if row is None:
        raise ValueError("Skill not found")
    return _ensure_media(db, row, image_tools.fetch_skill_image, audio_tools.skill_explanation_to_audio,
                         course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)


def ensure_lesson_media(db, *, course_id, lesson_id):
    row = repo.get_lesson_explanation(db, course_id=course_id, lesson_id=lesson_id)
    if row is None:
        raise ValueError("Lesson not found")
    return _ensure_media(db, row, image_tools.fetch_lesson_image, audio_tools.lesson_explanation_to_audio,
                         course_id=course_id, lesson_id=lesson_id)


def explain_skill(db, *, course_id, lesson_id, skill_id, force=False):
    row = repo.get_skill(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if row is None:
        raise ValueError("Skill not found")
    skill = skill_tools.serialize_skill(row)
    backend = "existing"
    if force or not row.explanation:
        chunks = content_tools.skill_evidence(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id,
            query=f"{row.name} {row.learning_objective}")
        if not chunks and not row.evidence_chunk_ids:
            # Explicit compatibility path for pre-upgrade skills without evidence links.
            chunks = rag_tools.retrieve_relevant_material(db, f"{row.name} {row.description}",
                top_k=5, course_id=course_id, lesson_id=lesson_id)
        if not chunks:
            raise ValueError("No source evidence is available for this skill.")
        system, user = build_skill_explanation_prompt(course_id=course_id, lesson_id=lesson_id,
                                                       skill=skill, context_chunks=chunks)
        data = {}
        try:
            data, backend = complete_json(system, user)
            text = SkillExplanation(explanation=data.get("explanation")).explanation
        except Exception as exc:
            text, backend = fallback_explanation(skill, chunks), f"fallback({type(exc).__name__})"
        try:
            content = LearningContent.model_validate(data.get('learning_content', {})).model_dump()
        except Exception:
            content = structured_fallback(skill, chunks, text)
        row.learning_content = content
        repo.set_skill_explanation(db, row, text)
    media = ensure_skill_media(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    return {"skill": skill_tools.serialize_skill(row), "backend": backend, "media": media}


def serialize_lesson(row):
    return {"id": row.id, "course_id": row.course_id, "lesson_id": row.lesson_id,
            "title": row.title, "explanation": row.explanation, "key_concepts": row.key_concepts or [],
            "has_image": image_tools.valid_image_file(row.image_path), "image_alt": row.image_alt or "",
            "has_audio": audio_tools.valid_audio_file(row.audio_path)}


def explain_lesson(db, *, course_id, lesson_id, force=False):
    row = repo.get_lesson_explanation(db, course_id=course_id, lesson_id=lesson_id)
    backend = "existing"
    if force or row is None or not row.explanation:
        content_map, _ = content_tools.build_content_map(db, course_id, lesson_id)
        chunks = content_tools.overview_sections(content_map)
        names = [s.name for s in repo.list_skills(db, course_id=course_id, lesson_id=lesson_id)]
        system, user = build_lesson_explanation_prompt(course_id=course_id, lesson_id=lesson_id,
                                                       context_chunks=chunks, skill_names=names)
        try:
            if sum(len(c["text"]) + 100 for c in chunks) > 12000:
                raise ValueError("Use complete extractive overview for long lesson")
            data, backend = complete_json(system, user)
            payload = LessonExplanationModel(**data).model_dump()
        except Exception as exc:
            payload = fallback_lesson_explanation(chunks, course_id, lesson_id, names)
            if chunks:
                payload['title'] = content_map['title']
                payload['explanation'] = '\n\n'.join(c['text'] for c in chunks)
                payload['key_concepts'] = content_map.get('concepts') or names
            backend = f"fallback({type(exc).__name__})"
        row = repo.upsert_lesson_explanation(db, course_id=course_id, lesson_id=lesson_id, **payload)
    media = ensure_lesson_media(db, course_id=course_id, lesson_id=lesson_id)
    return {"lesson": serialize_lesson(row), "backend": backend, "media": media}
