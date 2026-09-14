"""Audio endpoints: explanation text -> Groq TTS speech (WAV file responses)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from sahlha.app.database.database import get_db
from sahlha.app.services import services as svc

router = APIRouter(prefix="/audio", tags=["audio"])


def _to_file(result: dict) -> FileResponse:
    return FileResponse(result["path"], media_type="audio/wav",
                        filename=f"{result.get('skill_id') or result.get('lesson_id')}.wav")


@router.get("/skill")
def skill_audio(course_id: str = "general", lesson_id: str = "lesson_1",
                skill_id: str = "", voice: str | None = None,
                db: Session = Depends(get_db)):
    """WAV audio of one skill's explanation. 503 when Groq TTS is not configured."""
    try:
        return _to_file(svc.skill_audio(db, course_id=course_id, lesson_id=lesson_id,
                                        skill_id=skill_id, voice=voice))
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@router.get("/lesson")
def lesson_audio(course_id: str = "general", lesson_id: str = "lesson_1",
                 voice: str | None = None, db: Session = Depends(get_db)):
    """WAV audio of the whole-lesson overview explanation."""
    try:
        return _to_file(svc.lesson_audio(db, course_id=course_id, lesson_id=lesson_id,
                                         voice=voice))
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
