"""Skill registration and serialization; ORM access belongs to repositories."""
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.agent.tools.audio_tools import valid_audio_file
from sahlha.app.agent.tools.image_tools import valid_image_file


def register_skill(db, *, course_id, lesson_id, skill):
    return repo.upsert_skill(db, course_id=course_id, lesson_id=lesson_id,
        skill_id=skill["skill_id"], name=skill.get("name", skill["skill_id"]),
        description=skill.get("description", ""), key_concepts=skill.get("key_concepts", []), educational_metadata=skill)


def serialize_skill(row):
    return {**{k: getattr(row, k) for k in ("learning_objective", "prerequisites", "misconceptions", "difficulty", "source_section_ids", "evidence_chunk_ids", "learning_content")}, "id": row.id, "course_id": row.course_id, "lesson_id": row.lesson_id,
            "skill_id": row.skill_id, "name": row.name, "description": row.description,
            "explanation": row.explanation, "key_concepts": row.key_concepts or [],
            "has_image": valid_image_file(row.image_path), "image_alt": row.image_alt or "",
            "has_audio": valid_audio_file(row.audio_path)}


def list_skills(db, *, course_id, lesson_id):
    return repo.list_skills(db, course_id=course_id, lesson_id=lesson_id)

get_skill = repo.get_skill
