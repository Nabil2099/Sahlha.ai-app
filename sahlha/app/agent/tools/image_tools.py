"""Image tools — the ONLY way the agent attaches pictures to skills.

The tool builds a query from the skill's context (name + key concepts), fetches a
related image via the provider, caches it on disk, and records it on the skill row.
The LLM never touches image bytes or API keys.
"""
from __future__ import annotations

import hashlib
import logging
import os

from sqlalchemy.orm import Session

from sahlha.app.database.repositories import repositories as repo
from sahlha.app.images import pexels

logger = logging.getLogger(__name__)


def fetch_skill_image(db: Session, *, course_id: str, lesson_id: str,
                      skill_id: str, force: bool = False) -> dict:
    """Fetch (or return cached) one related image for a skill. Raises on failure."""
    from sahlha.app.config import settings

    skill = repo.get_skill(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if skill is None:
        raise ValueError(f"Skill {skill_id} not found in {course_id}/{lesson_id}")
    return _fetch_for_row(db, skill, force=force)


def _fetch_for_row(db, skill, force=False):
    from sahlha.app.config import settings
    skill_id = getattr(skill, "skill_id", skill.lesson_id)
    if valid_image_file(skill.image_path) and not force:
        return {"skill_id": skill_id, "path": skill.image_path, "source_url": skill.image_url,
                "alt": skill.image_alt, "cached": True}
    query = pexels.build_image_query({"name": getattr(skill, "name", getattr(skill, "title", "")), "skill_id": skill_id,
                                      "description": getattr(skill, "description", ""),
                                      "key_concepts": skill.key_concepts or []})
    try:
        found = pexels.fetch_related_image(query)
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        # Network/provider failures must degrade to a calm 503, never a 500.
        logger.warning("Image fetch failed: %s", type(exc).__name__)
        raise RuntimeError("No picture is available right now.") from exc
    os.makedirs(settings.image_dir, exist_ok=True)
    digest = hashlib.sha1(found["bytes"]).hexdigest()[:16]
    path = os.path.join(settings.image_dir, f"{digest}.jpg".replace("/", "_"))
    # Atomic write so a concurrent reader never sees a half-written JPEG.
    import tempfile

    fd, tmp_path = tempfile.mkstemp(dir=settings.image_dir, suffix=".jpg.part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(found["bytes"])
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    repo.set_media(db, skill, image_url=found["page_url"], image_path=path, image_alt=found["alt"])
    return {"skill_id": skill_id, "path": path, "source_url": found["page_url"],
            "alt": found["alt"], "photographer": found["photographer"],
            "query": query, "cached": False}


def valid_image_file(path):
    try:
        return bool(path and os.path.isfile(path) and os.path.getsize(path) >= 1024)
    except OSError:
        return False


def fetch_lesson_image(db, *, course_id, lesson_id, force=False):
    row = repo.get_lesson_explanation(db, course_id=course_id, lesson_id=lesson_id)
    if row is None:
        raise ValueError("Lesson explanation not found")
    return _fetch_for_row(db, row, force)
