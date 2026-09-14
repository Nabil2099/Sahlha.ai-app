"""Image tools — the ONLY way the agent attaches pictures to skills.

The tool builds a query from the skill's context (name + key concepts), fetches a
related image via the provider, caches it on disk, and records it on the skill row.
The LLM never touches image bytes or API keys.
"""
from __future__ import annotations

import hashlib
import os

from sqlalchemy.orm import Session

from sahlha.app.database.repositories import repositories as repo
from sahlha.app.images import pexels


def fetch_skill_image(db: Session, *, course_id: str, lesson_id: str,
                      skill_id: str, force: bool = False) -> dict:
    """Fetch (or return cached) one related image for a skill. Raises on failure."""
    from sahlha.app.config import settings

    skill = repo.get_skill(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if skill is None:
        raise ValueError(f"Skill {skill_id} not found in {course_id}/{lesson_id}")
    if skill.image_path and os.path.exists(skill.image_path) and not force:
        return {"skill_id": skill_id, "path": skill.image_path, "source_url": skill.image_url,
                "alt": skill.image_alt, "cached": True}
    query = pexels.build_image_query({"name": skill.name, "skill_id": skill.skill_id,
                                      "key_concepts": skill.key_concepts or []})
    found = pexels.fetch_related_image(query)
    os.makedirs(settings.image_dir, exist_ok=True)
    digest = hashlib.sha1(found["bytes"]).hexdigest()[:16]
    path = os.path.join(settings.image_dir, f"{skill.skill_id[:60]}_{digest}.jpg".replace("/", "_"))
    with open(path, "wb") as fh:
        fh.write(found["bytes"])
    skill.image_url = found["page_url"]
    skill.image_path = path
    skill.image_alt = found["alt"]
    db.commit()
    return {"skill_id": skill_id, "path": path, "source_url": found["page_url"],
            "alt": found["alt"], "photographer": found["photographer"],
            "query": query, "cached": False}
