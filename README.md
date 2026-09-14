# Sahlha AI — Learning-Loop MVP

First functional prototype proving the **Sahlha learning loop end-to-end**:
upload → OCR → RAG → **agent splits lesson into skills (one per topic — the agent decides
how many), writes a lesson overview and an explanation per skill** →
**one 10-question bank per skill** → teacher approves each bank →
student studies, then is assessed (**4 questions picked from EACH bank**, or one
skill's 4 when a `skill_id` is given — **skill = explanation + exercise**) →
attempts stored → memory updated → next assessment adapts.

> LLM provider: **Groq** (`GROQ_API_KEY` + `GROQ_MODEL`, default `llama-3.3-70b-versatile`,
> via native `groq` SDK with OpenAI-compatible fallback). Without a key the agent uses a
> **grounded deterministic fallback generator** so the whole loop still works offline.

## 1. Final project structure

```text
sahlha/
└── app/
    ├── main.py                    # FastAPI entrypoint (thin routers only)
    ├── config.py                  # settings (Groq keys, chunking, top-k, n=4)
    ├── api/
    │   ├── routes_documents.py    # POST /documents/upload, POST /documents/{id}/process
    │   ├── routes_agent.py        # POST /agent/generate-question-bank
    │   ├── routes_teacher.py      # GET pending, GET bank, POST approve/reject
    │   └── routes_assessment.py   # POST start/submit, GET student performance
    ├── agent/
    │   ├── agent.py               # SahlhaAgent state-machine runtime (ONE agent)
    │   ├── state.py               # AgentState (typed, serializable) + Phase enum
    │   ├── prompts.py             # LLM prompts: questions + skill extraction + explanations
    │   ├── schemas.py             # GeneratedQuestion / QuestionList / ExtractedSkill / SkillExplanation
    │   ├── llm.py                 # Groq client + grounded fallback generators
    │   └── tools/
    │       ├── rag_tools.py       # retrieve_lesson / retrieve_skill_material / retrieve_relevant_material
    │       ├── question_tools.py  # save_questions / get_question_bank / get_approved_questions
    │       ├── student_tools.py   # history / failed / skill performance / update memory
    │       └── assessment_tools.py# select_questions / evaluate_answer / record_attempt
    ├── rag/
    │   ├── ingestion.py           # bytes → extract → chunk → persist → reindex
    │   ├── ocr.py                 # extract_document_text() interface (text vs scanned)
    │   ├── chunking.py            # overlapping char chunker + cleaner
    │   ├── embeddings.py          # TF-IDF embedding model (swappable)
    │   ├── vectorstore.py         # cosine search abstraction (swappable for FAISS/Chroma)
    │   └── retriever.py           # filtered semantic retrieval
    ├── database/
    │   ├── database.py            # engine/session, init_db (app owns transactions)
    │   ├── models.py              # Document, DocumentChunk, QuestionBank, Question,
    │                              # Student, Assessment, StudentAttempt, StudentSkillPerformance
    │   └── repositories/          # ONLY layer (besides services) touching the ORM
    ├── schemas/api.py             # FastAPI request models
    └── services/services.py       # business logic (routes stay thin)
streamlit_app.py                   # test client: teacher / student / debug tabs
tests/                             # test_rag, test_questions, test_assessment, test_api_loop
data/                              # sqlite db, uploads, vectorizer (gitignored)
```

## 2. Agent architecture

One `SahlhaAgent` (`sahlha/app/agent/agent.py`) — an explicit **state machine** over
`AgentState`, not a free-form while-loop:

```text
SKILL_EXTRACTION → SKILL_EXPLANATION → QUESTION_GENERATION (per skill)
→ (teacher boundary) → WAITING_FOR_TEACHER
→ ASSESSMENT → EVALUATION → ADAPTATION
```

- `extract_skills()`: `retrieve_lesson()` → Groq returns skills JSON (validated via
  `SkillList`) → persisted in `skills` (idempotent unless `force=True`). The agent decides
  the number of skills (one per lesson topic); `max_skills` is only a safety cap.
- `explain_skills()`: per skill, skill-focused retrieval → Groq writes a grounded
  student-facing explanation → stored on the skill row.
- `explain_lesson()`: one grounded overview (title + explanation + key concepts) for the
  whole lesson → stored in `lesson_explanations` (idempotent; runs inside skill extraction too).
- `generate_lesson_banks()`: one `generate_question_bank()` per skill (10 questions each) — skill-focused
  retrieval → Groq generates **structured JSON** → `QuestionList` validation →
  `save_questions()` → phase `WAITING_FOR_TEACHER`. The bank's `skill_id` is enforced
  app-side on every question row.
- `start_assessment()`: approved questions + student history → memory-aware
  `select_questions()` (**exactly 4 from EACH approved bank**, so every skill is covered;
  failed-retry → weak skills → unseen → difficulty balance runs inside each bank)
  → `Assessment` row created. The response also carries
  `lesson_explanation` (whole-lesson overview) plus `skill_explanations` — so the student
  **studies the lesson, then the skills, before the exercise**. Correct answers never leave the server.
- `submit_assessment()`: per-question `evaluate_answer()` → `record_attempt()` →
  `update_student_memory()` → phase `ADAPTATION`.
- Every phase transition and tool call is appended to `state.trace` (shown in the Streamlit debug tab).

## 3. Tool list & responsibilities

| Tool | Responsibility |
|---|---|
| `retrieve_lesson(course, lesson)` | RAG chunks for one lesson (with doc/course/lesson/skill/page/chunk metadata) |
| `retrieve_skill_material(skill)` | RAG chunks for one skill |
| `retrieve_relevant_material(query, filters)` | free-form semantic search with optional filters |
| `save_questions(...)` | **validate** LLM JSON (Pydantic) then persist new `pending_review` version |
| `get_question_bank(bank_id)` | full bank + questions (teacher review) |
| `get_approved_questions(filters)` | only `approved` banks' questions (assessment pool) |
| `get_student_history(student)` | past attempts (capped, no full-history prompt dumps) |
| `get_failed_questions(student)` | question IDs answered incorrectly |
| `get_student_skill_performance(student)` | per-skill accuracy rows |
| `update_student_memory(...)` | upsert skill counters after each attempt |
| `select_questions(...)` | deterministic: failed-retry → weak skills (<0.6) → unseen → difficulty balance; **exactly 4** |
| `evaluate_answer(question, answer)` | structured `{question_id, correct, student_answer, correct_answer, skill_id}` |
| `record_attempt(...)` | one `StudentAttempt` row per answer (never just a score) |

The agent **never** touches the DB/vector store directly — only through these tools.

## 4. Database schema (SQLite)

- `documents(id, filename, course_id, lesson_id, skill_id, status, char_count, chunk_count, created_at)`
- `document_chunks(id, document_id, course_id, lesson_id, skill_id, page, chunk_index, text)`
- `skills(id, course_id, lesson_id, skill_id[slug, unique per lesson], name, description, explanation, key_concepts[JSON], created_at, updated_at)`
- `lesson_explanations(id, course_id, lesson_id[unique], title, explanation, key_concepts[JSON], created_at, updated_at)`
- `question_banks(id, course_id, lesson_id, skill_id, version, status[pending_review|approved|rejected], teacher_feedback, created_at, updated_at)` — versions append-only, never overwritten
- `questions(id, question_bank_id, skill_id, question_type, question_text, options[JSON], correct_answer[JSON], explanation, difficulty, created_at)`
- `students(id, name, created_at)`
- `assessments(id, student_id, question_bank_id, question_ids[JSON], status, score, created_at)`
- `student_attempts(id, student_id, question_id, assessment_id, answer[JSON], correct, timestamp)`
- `student_skill_performance(id, student_id, skill_id, total_attempts, correct_attempts, accuracy, last_updated)` — unique `(student_id, skill_id)`

## 5. RAG architecture

```text
upload bytes → extract_document_text() → clean → overlap-chunk (800/120)
→ persist chunks → refit TF-IDF → cosine search (+ keyword fallback)
```

- `ocr.py` is a provider interface: native text for pdf/docx/txt; scanned PDFs/images go to
  tesseract (`pytesseract`/`pdf2image`) when installed, otherwise recorded as
  `ocr:unavailable` without crashing ingestion. `is_scanned` + `method` are returned.
- Every retrieved chunk carries `document_id, course_id, lesson_id, skill_id, page, chunk_id, text, score`.
- Generation is **grounded**: only retrieved chunks enter the prompt; fallback generator builds
  stems from chunk sentences. Full documents are never pasted into prompts.

## 6. API endpoints

```text
POST /documents/upload
POST /documents/{id}/process
POST /agent/extract-skills            (lesson → agent-decided skills + explanations + lesson overview)
GET  /agent/skills?course_id&lesson_id[&skill_id]
POST /agent/explain-lesson             (whole-lesson overview explanation)
GET  /agent/lesson                     (study bundle: lesson overview + skill explanations)
POST /agent/generate-question-bank    (single skill)
POST /agent/generate-lesson-banks     (one bank per skill)
GET  /teacher/question-banks/pending
GET  /teacher/question-banks/{id}
POST /teacher/question-banks/{id}/approve
POST /teacher/question-banks/{id}/reject        (JSON {feedback} → next version uses it)
POST /assessment/start                 (optional skill_id → that skill's 4-question exercise)
POST /assessment/{id}/submit
GET  /students/{id}/performance
GET  /students/{id}/skill-progress?course_id&lesson_id   (per-skill explanation+exercise status)
GET  /audio/skill?course_id&lesson_id&skill_id[&voice]   (WAV speech of a skill's explanation)
GET  /audio/lesson?course_id&lesson_id[&voice]           (WAV speech of the lesson overview)
GET  /images/skill?course_id&lesson_id&skill_id          (JPEG picture related to the skill)
GET  /health
```

## 7. Run FastAPI

```powershell
pip install -r requirements.txt
copy .env.example .env   # add GROQ_API_KEY to enable the real LLM; optional
python -m uvicorn sahlha.app.main:app --reload --port 8000
```

## 8. Run Streamlit

```powershell
$env:SAHLHA_API = "http://127.0.0.1:8000"
streamlit run streamlit_app.py
```

## 9. Test the complete loop

```powershell
python -m pytest tests/ -q   # 11 tests: RAG, generation, approve, reject→v2, assessment×4,
                             # memory-adapts, HTTP loop, skill extraction+explanations,
                             # one-bank-per-skill, skill banks approve+assess, skill HTTP endpoints
```

Manual loop in Streamlit: **Teacher** tab → upload file → Extract skills (agent decides the
count; review explanations) → Generate 10-question banks (one per skill) → approve each →
**Student** tab → load the lesson's skills → per skill: read its explanation →
start its 4-question exercise → submit → progress bar tracks completed skills →
**Debug** tab shows phases/tool calls).

## 10b. Audio explanations (Groq TTS)

New tool pair `skill_explanation_to_audio` / `lesson_explanation_to_audio`
(`sahlha/app/agent/tools/audio_tools.py`) turns stored explanations into speech via
Groq's Orpheus English TTS (`canopylabs/orpheus-v1-english`, `sahlha/app/audio/tts.py`):
long text is split sentence-aware, each chunk synthesized, and the WAVs stitched.
Files are cached in `data/audio/` by content hash. The student UI has a 🔊 **Listen**
button per skill. Requires `GROQ_API_KEY` **and** accepting the model terms in the Groq
console — without them the endpoints return `503` (there is no offline TTS fallback).

## 10c. Skill images (Pexels)

Tool `fetch_skill_image` (`sahlha/app/agent/tools/image_tools.py`) builds a query from the
skill's context (name + key concepts) and fetches one landscape picture via the Pexels API
(`sahlha/app/images/pexels.py`), cached in `data/images/` and recorded on the skill row
(`image_url`/`image_path`/`image_alt`; added to existing DBs by a startup migration).
The student UI shows the picture above each explanation. Set `PEXELS_API_KEY` in `.env`
(free at https://www.pexels.com/api/) — without it `GET /images/skill` returns `503`.

## 10. Known limitations & next steps

- Embeddings are TF-IDF (offline-friendly) — swap `embeddings.py`/`vectorstore.py` for
  sentence-transformers + FAISS/Chroma when ready; interfaces are isolated.
- OCR for scanned PDFs needs `tesseract` binary + `pdf2image`; otherwise text is best-effort.
- No auth (single teacher/student IDs), no pagination, SQLite only — all intentional for the MVP.
- Next: real auth, richer question types (short answer grading via LLM), spaced-repetition
  scheduling on top of `StudentSkillPerformance`, and analytics over `student_attempts`.
