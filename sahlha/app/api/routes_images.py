"""Image endpoints: one related picture per skill (Pexels, cached on disk)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from sahlha.app.database.database import get_db
from sahlha.app.services import services as svc

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/skill")
def skill_image(course_id: str = "general", lesson_id: str = "lesson_1",
                skill_id: str = "", force: bool = False,
                db: Session = Depends(get_db)):
    """JPEG image related to the skill (fetched via Pexels on first call, then cached).

    404 when the skill is unknown or Pexels has nothing; 503 when PEXELS_API_KEY is missing.
    """
    try:
        result = svc.skill_image(db, course_id=course_id, lesson_id=lesson_id,
                                 skill_id=skill_id, force=force)
        return FileResponse(result["path"], media_type="image/jpeg",
                            filename=f"{skill_id}.jpg")
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
