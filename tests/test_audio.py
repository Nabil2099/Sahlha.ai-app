"""Audio: pure helpers offline; endpoints degrade to 503 without a Groq key."""
import io
import os
import wave

import pytest

from sahlha.app.audio import tts
from sahlha.app.config import settings


def _make_wav(frames: bytes, *, nchannels=1, sampwidth=2, framerate=22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(nchannels)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        w.writeframes(frames)
    return buf.getvalue()


def test_split_for_tts_respects_limit():
    text = " ".join(f"This is sentence number {i} about loops and variables." for i in range(20))
    chunks = tts.split_for_tts(text, max_chars=120)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)
    assert " ".join(chunks) == text


def test_stitch_wavs_roundtrip():
    a = _make_wav(b"\x01\x02" * 100)
    b = _make_wav(b"\x03\x04" * 50)
    out = tts.stitch_wavs([a, b])
    with wave.open(io.BytesIO(out), "rb") as w:
        assert w.getnframes() == 150
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 22050)
    assert tts.stitch_wavs([a]) == a


def test_stitch_rejects_mismatched_params():
    with pytest.raises(ValueError):
        tts.stitch_wavs([_make_wav(b"\x00" * 10, framerate=22050),
                         _make_wav(b"\x00" * 10, framerate=44100)])


def test_synthesize_needs_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        tts.synthesize("hello")


def test_audio_endpoints_degrade_without_key(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from tests.conftest import SAMPLE_TEXT

    client.post("/documents/upload", files={"file": ("elif.txt", SAMPLE_TEXT * 2)},
                data={"course_id": "ac", "lesson_id": "al", "skill_id": "askill"})
    skills = client.post("/agent/extract-skills",
                         json={"course_id": "ac", "lesson_id": "al", "max_skills": 1}).json()["skills"]
    assert skills and skills[0]["explanation"]
    r = client.get("/audio/skill", params={"course_id": "ac", "lesson_id": "al",
                                           "skill_id": skills[0]["skill_id"]})
    assert r.status_code == 503, r.text
    rl = client.get("/audio/lesson", params={"course_id": "ac", "lesson_id": "al"})
    assert rl.status_code == 503, rl.text
    missing = client.get("/audio/skill", params={"course_id": "ac", "lesson_id": "al",
                                                 "skill_id": "nope"})
    assert missing.status_code == 404
