"""Audio tools — the ONLY way the agent turns explanations into speech.

Tools resolve the explanation text from the DB, synthesize via the TTS provider,
and cache the WAV on disk keyed by content hash. The LLM never touches audio bytes.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile

from sqlalchemy.orm import Session

from sahlha.app.audio import tts
from sahlha.app.database.repositories import repositories as repo

logger = logging.getLogger(__name__)

_VOICE_RE = re.compile(r"[^A-Za-z0-9 _-]")


def sanitize_voice(voice: str | None) -> str | None:
    """Keep the TTS voice a short, safe token (pure — unit tested).

    The value is interpolated into the cache key and forwarded to the TTS
    provider, so overlong/garbage input must never reach either. Returns
    None when no usable voice was supplied (caller falls back to default).
    """
    if voice is None:
        return None
    cleaned = _VOICE_RE.sub("", voice.strip())[:64].strip()
    return cleaned or None


def _cached_or_synth(text: str, voice: str | None) -> tuple[str, str, bool]:
    from sahlha.app.config import settings

    os.makedirs(settings.audio_dir, exist_ok=True)
    voice_used = sanitize_voice(voice) or settings.groq_tts_voice
    digest = hashlib.sha1(f"{settings.groq_tts_model}|{voice_used}|{settings.openrouter_tts_model}|{settings.openrouter_tts_voice}|{settings.openrouter_tts_format}|{settings.openrouter_tts_sample_rate}|{text}".encode()).hexdigest()[:16]
    path = os.path.join(settings.audio_dir, f"{digest}.wav")
    if valid_audio_file(path):
        return path, voice_used, True
    try:
        wav, voice_used = tts.synthesize(text, voice_used)
    except ValueError:
        raise
    except RuntimeError as exc:
        # Provider detail (model names, terms URLs, HTTP errors) is logged
        # server-side only. Clients get a calm generic 503 so lessons never
        # break and no provider internals leak to student devices.
        logger.warning("TTS synthesis unavailable: %s", type(exc).__name__)
        raise RuntimeError("Audio is unavailable right now.") from exc
    except Exception as exc:  # never leak provider internals/secrets to clients
        logger.warning("TTS synthesis failed: %s", type(exc).__name__)
        raise RuntimeError("Audio is unavailable right now.") from exc
    if not tts.valid_wav(wav):
        raise RuntimeError("Audio is unavailable right now.")
    # Re-check after synthesis: a concurrent request for the same text may
    # have populated the cache while we were calling the provider, in which
    # case we reuse it instead of writing a duplicate file.
    if valid_audio_file(path):
        return path, voice_used, True
    # Atomic write so a concurrent reader never sees a half-written WAV.
    fd, tmp_path = tempfile.mkstemp(dir=settings.audio_dir, suffix=".wav.part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(wav)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return path, voice_used, False


def skill_explanation_to_audio(db: Session, *, course_id: str, lesson_id: str,
                               skill_id: str, voice: str | None = None) -> dict:
    """Speech audio for one skill's agent-written explanation."""
    skill = repo.get_skill(db, course_id=course_id, lesson_id=lesson_id, skill_id=skill_id)
    if skill is None:
        raise ValueError(f"Skill {skill_id} not found in {course_id}/{lesson_id}")
    if not skill.explanation:
        raise ValueError(f"Skill {skill_id} has no explanation yet — run extract-skills first")
    text = f"{skill.name}. {skill.explanation}"
    path, voice_used, cached = _cached_or_synth(text, voice)
    repo.set_media(db, skill, audio_path=path)
    return {"audio_id": os.path.basename(path).replace(".wav", ""), "path": path,
            "skill_id": skill_id, "voice": voice_used, "cached": cached,
            "chars": len(text)}


def lesson_explanation_to_audio(db: Session, *, course_id: str, lesson_id: str,
                                voice: str | None = None) -> dict:
    """Speech audio for the whole-lesson overview explanation."""
    row = repo.get_lesson_explanation(db, course_id=course_id, lesson_id=lesson_id)
    if row is None or not row.explanation:
        raise ValueError(f"Lesson {course_id}/{lesson_id} has no explanation yet — run explain-lesson first")
    text = f"{row.title}. {row.explanation}" if row.title else row.explanation
    path, voice_used, cached = _cached_or_synth(text, voice)
    repo.set_media(db, row, audio_path=path)
    return {"audio_id": os.path.basename(path).replace(".wav", ""), "path": path,
            "lesson_id": lesson_id, "voice": voice_used, "cached": cached,
            "chars": len(text)}


def valid_audio_file(path: str) -> bool:
    import wave
    try:
        with wave.open(path, "rb") as stream:
            return stream.getnframes() > 0 and bool(stream.readframes(1))
    except (OSError, EOFError, wave.Error, AttributeError):
        return False
