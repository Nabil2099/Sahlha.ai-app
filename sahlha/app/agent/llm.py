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


def _provider_completion(provider, api_key, model, system, user, temperature: float = 0.4):
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
            temperature=temperature, response_format={"type": "json_object"})
        return response.choices[0].message.content or "{}"


def temperature_for(task: str) -> float:
    """Task-specific temperatures: deterministic for extraction/verification."""
    from sahlha.app.config import settings
    mapping = {
        "skill_extraction": settings.skill_extraction_temperature,
        "skill_consolidation": settings.skill_consolidation_temperature,
        "semantic_verifier": settings.semantic_verifier_temperature,
        "question_generation": settings.question_generation_temperature,
        "explanation": settings.explanation_temperature,
    }
    return float(mapping.get(task, 0.4))


def _call_llm(system: str, user: str, temperature: float = 0.4) -> tuple[str, str]:
    from sahlha.app.config import settings
    from sahlha.app.agent.providers import retryable_provider_error, logger
    provider, key, model = _resolve_provider()
    if not provider:
        raise RuntimeError("no-llm-configured")
    try:
        return _provider_completion(provider, key, model, system, user, temperature), provider
    except Exception as exc:
        logger.info("Text provider unavailable: provider=%s category=%s", provider, type(exc).__name__)
        if provider != "groq" or not retryable_provider_error(exc) or not settings.openrouter_api_key.strip() or not settings.openrouter_model:
            raise
    # Exactly one cross-provider attempt; SDK retries are disabled.
    return _provider_completion("openrouter", settings.openrouter_api_key.strip(),
                                settings.openrouter_model, system, user, temperature), "openrouter"


def _alternate_provider() -> tuple[str, str, str]:
    """Configured alternate provider for one bounded failover attempt (schema repair)."""
    from sahlha.app.config import settings
    primary, _, _ = _resolve_provider()
    if primary == "groq" and settings.openrouter_api_key.strip() and settings.openrouter_model:
        return "openrouter", settings.openrouter_api_key.strip(), settings.openrouter_model
    return "", "", ""


def _parse_json_object(text: str):
    raw = (text or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError("LLM did not return parseable JSON")


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
    """Source-completion MCQs with real lesson terms and explicit evidence.

    Each item has a mechanically checkable answer: filling the blank reproduces
    a cited sentence. No fabricated facts or arbitrary difficulty inflation.
    """
    stop = {'the', 'and', 'with', 'from', 'this', 'that', 'when', 'then', 'only',
            'into', 'which', 'what', 'have', 'does', 'will', 'until', 'another'}
    out, seen = [], set()
    for chunk in context_chunks:
        sentences = [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n', chunk.get('text', '')) if len(x.split()) >= 5]
        vocabulary = list(dict.fromkeys(re.findall(r'\b[A-Za-z][A-Za-z_-]{2,}\b', chunk.get('text', ''))))
        vocabulary = [w for w in vocabulary if w.lower() not in stop]
        for sentence in sentences:
            words = sorted(set(re.findall(r'\b[A-Za-z][A-Za-z_-]{2,}\b', sentence)), key=lambda w: (-len(w), w))
            for answer in words:
                if answer.lower() in stop:
                    continue
                alternatives = [w for w in vocabulary if w.lower() != answer.lower()
                                and not re.search(r'\b'+re.escape(w)+r'\b', sentence, re.I)]
                if len(alternatives) < 3:
                    alternatives += [w for w in vocabulary if w.lower() != answer.lower() and w not in alternatives]
                alternatives = list(dict.fromkeys(w.lower() for w in alternatives))[:3]
                if len(alternatives) < 3:
                    continue
                stem = re.sub(r'\b'+re.escape(answer)+r'\b', '_____', sentence, count=1)
                question = 'Complete the source statement with the exact lesson term: ' + stem
                if question in seen:
                    continue
                seen.add(question)
                options = [answer] + alternatives
                rotation = len(out) % 4
                options = options[rotation:] + options[:rotation]
                out.append({'skill_id': skill_id, 'type': 'multiple_choice', 'question': question,
                    'options': options, 'correct_answer': options.index(answer),
                    'explanation': sentence, 'difficulty': 'easy',
                    'evidence_chunk_ids': [chunk['chunk_id']] if chunk.get('chunk_id') else [],
                    'learning_objective': chunk.get('learning_objective', f'Explain {skill_id.replace("_", " ")}.'),
                    'tested_concept': answer, 'verification': {'method': 'source_completion', 'source_quote': sentence}})
                if len(out) >= n:
                    return out
    return out


def generate_questions_llm(system: str, user: str, context_chunks: list[dict],
                            skill_id: str, n: int, feedback: str = "") -> tuple[list[dict], str]:
    """Returns (questions, backend) where backend is 'groq'/'openai' or 'fallback(...)'.

    Bounded resilience: 1 normal attempt + 1 schema-repair attempt +
    optionally 1 alternate-provider attempt, then deterministic fallback.
    """
    if llm_available():
        try:
            raw, provider = _call_llm(system, user, temperature_for("question_generation"))
            try:
                return _extract_json_array(raw), provider
            except Exception as parse_exc:
                repaired, repaired_provider = _repair_json_array(
                    system, user, raw, str(parse_exc),
                    temperature_for("question_generation"))
                return repaired, repaired_provider
        except Exception as exc:
            # Fail soft to grounded fallback so the loop never breaks
            return fallback_questions(context_chunks, skill_id, n, feedback), f"fallback({type(exc).__name__})"
    return fallback_questions(context_chunks, skill_id, n, feedback), "fallback(no-api-key)"


def _repair_json_array(system: str, user: str, malformed: str, error: str,
                       temperature: float) -> tuple[list, str]:
    """One bounded repair attempt (+ optionally one alternate-provider attempt)."""
    from sahlha.app.agent.providers import logger
    bounded = (malformed or "")[:4000]
    repair_system = (system + "\nYour previous response was not valid for the required schema. "
                     "Fix it and return ONLY valid JSON matching the contract.")
    repair_user = (f"Validation error: {error[:500]}\n"
                   f"Required schema: {{\"questions\": [{{...}}]}}\n"
                   f"Previous response (truncated):\n{bounded}\n"
                   f"Original request:\n{user[:4000]}")
    try:
        raw, provider = _call_llm(repair_system, repair_user, temperature)
        return _extract_json_array(raw), provider + "+repair"
    except Exception as exc:
        logger.info("Structured repair failed: category=%s", type(exc).__name__)
        alt_provider, alt_key, alt_model = _alternate_provider()
        if alt_provider:
            try:
                raw = _provider_completion(alt_provider, alt_key, alt_model,
                                           repair_system, repair_user, temperature)
                return _extract_json_array(raw), alt_provider + "+repair"
            except Exception as exc2:
                logger.info("Alternate-provider repair failed: category=%s", type(exc2).__name__)
                raise exc2 from exc
        raise


def complete_json(system: str, user: str, temperature: float | None = None,
                  task: str = "general") -> tuple[dict | list, str]:
    """Generic structured call with bounded repair (1 normal + 1 repair + 1 alternate).

    Raises RuntimeError when no LLM is configured so callers can use grounded
    fallbacks. Raises RuntimeError(llm-error:...) after bounded attempts fail.
    """
    if not llm_available():
        raise RuntimeError("no-llm-configured")
    temp = temperature if temperature is not None else (temperature_for(task) if task != "general" else 0.4)
    try:
        raw, provider = _call_llm(system, user, temp)
        try:
            return _parse_json_object(raw), provider
        except Exception as parse_exc:
            bounded = (raw or "")[:4000]
            repair_system = (system + "\nYour previous response was not valid JSON for the required schema. "
                             "Fix it and return ONLY valid JSON.")
            repair_user = (f"Validation error: {str(parse_exc)[:500]}\n"
                           f"Previous response (truncated):\n{bounded}\n"
                           f"Original request:\n{user[:4000]}")
            try:
                raw2, provider2 = _call_llm(repair_system, repair_user, temp)
                return _parse_json_object(raw2), provider2 + "+repair"
            except Exception as exc:
                from sahlha.app.agent.providers import logger as _logger
                _logger.info("Structured repair failed: category=%s", type(exc).__name__)
                alt_provider, alt_key, alt_model = _alternate_provider()
                if alt_provider:
                    try:
                        raw3 = _provider_completion(alt_provider, alt_key, alt_model,
                                                    repair_system, repair_user, temp)
                        return _parse_json_object(raw3), alt_provider + "+repair"
                    except Exception as exc2:
                        _logger.info("Alternate-provider repair failed: category=%s", type(exc2).__name__)
                        raise exc2 from exc
                raise
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
    """Compatibility entry point using the evidence-backed topic mapper."""
    from sahlha.app.agent.tools.content_tools import fallback_topics, validate_skills
    return validate_skills(fallback_topics(context_chunks), context_chunks, max_skills)[0]


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
