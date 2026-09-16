"""LLM client: Groq (OpenAI-compatible API) when a key is configured, else fallback.

The fallback generator is grounded (builds questions from retrieved chunks via
templates) so the full loop works offline. When GROQ_API_KEY is set, real
LLM structured generation is used via Groq's OpenAI-compatible endpoint.
Set GROQ_MODEL to pick the model (default: llama-3.3-70b-versatile).
"""
from __future__ import annotations

import json
import re


def _resolve_provider() -> tuple[str, str, str]:
    from sahlha.app.config import settings
    if settings.groq_api_key.strip():
        return "groq", settings.groq_api_key.strip(), settings.groq_model
    if settings.openrouter_api_key.strip() and settings.openrouter_model:
        return "openrouter", settings.openrouter_api_key.strip(), settings.openrouter_model
    if settings.openai_api_key.strip():
        return "openai", settings.openai_api_key.strip(), settings.openai_model
    return "", "", ""


def llm_available() -> bool:
    return bool(_resolve_provider()[0])


def _provider_completion(provider, api_key, model, system, user):
    from openai import OpenAI
    from sahlha.app.config import settings
    base = {"groq": settings.groq_base_url, "openrouter": settings.openrouter_base_url,
            "openai": settings.openai_base_url}[provider]
    kwargs = {"api_key": api_key, "max_retries": 0, "timeout": settings.provider_timeout_seconds}
    if base:
        kwargs["base_url"] = base
    with OpenAI(**kwargs) as client:
        response = client.chat.completions.create(model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4, response_format={"type": "json_object"})
        return response.choices[0].message.content or "{}"


def _call_llm(system: str, user: str) -> tuple[str, str]:
    from sahlha.app.config import settings
    from sahlha.app.agent.providers import retryable_provider_error, logger
    provider, key, model = _resolve_provider()
    if not provider:
        raise RuntimeError("no-llm-configured")
    try:
        return _provider_completion(provider, key, model, system, user), provider
    except Exception as exc:
        logger.info("Text provider unavailable: provider=%s category=%s", provider, type(exc).__name__)
        if provider != "groq" or not retryable_provider_error(exc) or not settings.openrouter_api_key.strip() or not settings.openrouter_model:
            raise
    # Exactly one cross-provider attempt; SDK retries are disabled.
    return _provider_completion("openrouter", settings.openrouter_api_key.strip(),
                                settings.openrouter_model, system, user), "openrouter"


def _extract_json_array(text: str) -> list:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("questions", "question_bank", "items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
    except Exception:
        pass
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError("LLM did not return parseable JSON")


def fallback_questions(context_chunks: list[dict], skill_id: str, n: int = 8,
                       feedback: str = "") -> list[dict]:
    """Deterministic grounded generator: builds MCQs from chunk sentences."""
    import re as _re

    sentences: list[str] = []
    for c in context_chunks:
        for s in _re.split(r"(?<=[.!?])\s+", c.get("text", "")):
            s = s.strip()
            if len(s.split()) >= 6:
                sentences.append((s, c.get("skill_id") or skill_id))
    if not sentences:
        sentences = [("The lesson introduces key concepts and examples.", skill_id)]

    wants_hard = "hard" in feedback.lower() or "difficult" in feedback.lower() or "practical" in feedback.lower()
    difficulties = (["medium", "hard", "medium", "hard"] if wants_hard else ["easy", "medium", "easy", "medium", "hard", "medium"])
    out: list[dict] = []
    for i in range(n):
        sent, sk = sentences[i % len(sentences)]
        words = sent.split()
        # Blank-out a keyword for the stem
        keyword = max([w.strip(",.;:()\"'") for w in words if len(w) > 4], key=len, default="concept")
        stem = sent.replace(keyword, "_____", 1) if keyword in sent else sent
        question = f"Based on the lesson, complete the statement: {stem}"
        correct = f"{keyword} — as stated in the lesson"
        distractors = [
            "It is unrelated to the lesson topic",
            "The lesson explicitly contradicts this",
            "This is never mentioned in the material",
        ]
        options = [correct] + distractors
        # Deterministic rotation so correct index varies
        rot = i % 4
        options = options[rot:] + options[:rot]
        out.append({
            "skill_id": sk,
            "type": "multiple_choice",
            "question": question,
            "options": options,
            "correct_answer": options.index(correct),
            "explanation": f"Grounded in lesson text: \"{sent[:160]}\"",
            "difficulty": difficulties[i % len(difficulties)],
        })
    return out


def generate_questions_llm(system: str, user: str, context_chunks: list[dict],
                            skill_id: str, n: int, feedback: str = "") -> tuple[list[dict], str]:
    """Returns (questions, backend) where backend is 'groq'/'openai' or 'fallback'."""
    if llm_available():
        try:
            raw, provider = _call_llm(system, user)
            return _extract_json_array(raw), provider
        except Exception as exc:
            # Fail soft to grounded fallback so the loop never breaks
            return fallback_questions(context_chunks, skill_id, n, feedback), f"fallback({type(exc).__name__})"
    return fallback_questions(context_chunks, skill_id, n, feedback), "fallback(no-api-key)"


def complete_json(system: str, user: str) -> tuple[dict | list, str]:
    """Generic structured call. Returns (parsed_json, backend). Falls back raises-free? No:
    raises RuntimeError when no LLM is configured so callers can use grounded fallbacks."""
    if not llm_available():
        raise RuntimeError("no-llm-configured")
    try:
        raw, provider = _call_llm(system, user)
        text = raw.strip()
        try:
            return json.loads(text), provider
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0)), provider
            raise ValueError("LLM did not return parseable JSON")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"llm-error: {type(exc).__name__}") from exc


def _sentences(chunks: list[dict]) -> list[str]:
    import re as _re

    out: list[str] = []
    for c in chunks:
        for s in _re.split(r"(?<=[.!?])\s+", c.get("text", "")):
            s = s.strip()
            if len(s.split()) >= 6:
                out.append(s)
    return out


def _top_terms(sentences: list[str], k: int = 6) -> list[str]:
    from collections import Counter

    stop = {"this", "that", "with", "from", "have", "will", "when", "what", "does", "uses",
            "using", "into", "such", "than", "then", "them", "they", "their", "about",
            "after", "also", "program", "example", "lesson"}
    words: list[str] = []
    for s in sentences:
        for w in re.sub(r"[^a-zA-Z ]", "", s).lower().split():
            if len(w) > 4 and w not in stop:
                words.append(w)
    return [w for w, _ in Counter(words).most_common(k)]


def fallback_skills(context_chunks: list[dict], lesson_id: str, max_skills: int = 6) -> list[dict]:
    """Deterministic grounded splitter: one skill per ~2 sentences (agent-side topic count)."""
    sentences = _sentences(context_chunks)
    if not sentences:
        return [{"skill_id": f"{lesson_id}_basics", "name": "Lesson basics",
                 "description": "Core concepts of the lesson.", "key_concepts": []}]
    k = max(1, min(max_skills, (len(sentences) + 1) // 2))
    size = max(1, (len(sentences) + k - 1) // k)
    out: list[dict] = []
    for i in range(k):
        part = sentences[i * size:(i + 1) * size]
        if not part:
            break
        terms = _top_terms(part)
        slug = re.sub(r"[^a-z0-9]+", "_", (terms[0] if terms else f"part{i + 1}").lower()).strip("_")
        out.append({
            "skill_id": f"{lesson_id}__{slug}"[:120],
            "name": f"{terms[0].capitalize() if terms else f'Part {i + 1}'} ({lesson_id})",
            "description": part[0][:220],
            "key_concepts": terms[:5],
        })
    return out


def fallback_explanation(skill: dict, context_chunks: list[dict]) -> str:
    """Grounded explanation composed from the skill's retrieved sentences."""
    sentences = _sentences(context_chunks) or _sentences([{"text": skill.get("description", "")}])
    if not sentences:
        return (f"{skill.get('name', skill.get('skill_id'))}: key lesson concept. "
                "Review the uploaded material for details and examples.")
    intro = sentences[0]
    example = next((s for s in sentences[1:] if any(k in s.lower() for k in ("example", "e.g.", "for instance", ":", "if ", "when "))), None)
    extra = [s for s in sentences[1:4] if s != example]
    parts = [f"{skill.get('name', skill.get('skill_id'))}: {intro}"]
    if extra:
        parts.append("Key points: " + " ".join(extra))
    if example:
        parts.append(f"Example from the material: {example}")
    parts.append("Common mistake to avoid: confusing this with neighboring concepts — re-check the exact wording in the lesson.")
    return "\n\n".join(parts)


def fallback_lesson_explanation(context_chunks: list[dict], course_id: str, lesson_id: str,
                                skill_names: list[str] | None = None) -> dict:
    """Grounded lesson overview composed from lesson sentences."""
    sentences = _sentences(context_chunks)
    if not sentences:
        return {"title": lesson_id.replace("_", " ").title(),
                "explanation": (f"This lesson ({lesson_id}) introduces its key concepts step by step. "
                                "Study each skill below, then attempt the exercise."),
                "key_concepts": skill_names or []}
    terms = _top_terms(sentences, k=8)
    title = f"{terms[0].capitalize()} {terms[1] if len(terms) > 1 else 'basics'}" if terms else lesson_id
    about = " ".join(sentences[:2])
    ideas = " ".join(sentences[2:5])
    parts = [f"In this lesson: {about}"]
    if ideas:
        parts.append(f"Main ideas: {ideas}")
    if skill_names:
        parts.append("You will work through these skills in order: " + ", ".join(skill_names) + ".")
    parts.append("After studying each skill explanation below, you will be ready for the exercise.")
    return {"title": title, "explanation": "\n\n".join(parts), "key_concepts": terms[:8]}
