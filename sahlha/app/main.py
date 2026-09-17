"""FastAPI entrypoint. Thin routes; logic lives in services/agent/tools."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sahlha.app.api import (routes_agent, routes_assessment, routes_audio, routes_auth,
                            routes_classrooms, routes_documents, routes_images,
                            routes_materials, routes_parent, routes_student, routes_teacher,
                            routes_teacher_platform)
from sahlha.app.config import settings
from sahlha.app.database.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.embedding_warmup:
        from threading import Thread
        from sahlha.app.rag.embeddings import get_embeddings
        Thread(target=get_embeddings, name="embedding-warmup", daemon=True).start()
    yield


app = FastAPI(title="Sahlha AI Learning Platform", lifespan=lifespan)

# Mobile development: emulator / physical device / Flutter web. Credentials are
# bearer tokens (Flutter secure storage), not cookies — origins stay explicit.
_origins = ["http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:8080", "http://127.0.0.1:8080",
            "http://localhost:5000", "http://127.0.0.1:5000"]
if settings.cors_extra_origins.strip():
    _origins += [o.strip() for o in settings.cors_extra_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Platform APIs (authenticated, RBAC-enforced).
app.include_router(routes_auth.router)
app.include_router(routes_classrooms.router)
app.include_router(routes_materials.router)
app.include_router(routes_student.router)
app.include_router(routes_teacher_platform.router)
app.include_router(routes_parent.router)
# Legacy AI-loop APIs (kept working; Streamlit dev tool + existing tests use them).
if settings.legacy_dev_api_enabled:
    app.include_router(routes_documents.router)
    app.include_router(routes_agent.router)
    app.include_router(routes_teacher.router)
    app.include_router(routes_assessment.router)
    app.include_router(routes_audio.router)
    app.include_router(routes_images.router)



@app.get("/")
def root():
    return {"service": "sahlha", "status": "ok"}


@app.get("/health")
def health():
    """Liveness + non-secret availability flags.

    Reports only booleans (TTS/image configured) so operators can verify
    `.env` keys are loaded without ever logging or exposing secret values.
    """
    from sahlha.app.audio import tts as tts_mod
    from sahlha.app.images import pexels as pexels_mod
    from sahlha.app.agent.llm import llm_available
    from sahlha.app.config import settings as _settings

    try:
        from sahlha.app.rag import embeddings as _emb
        _dense_available = bool(_emb.get_embeddings().dense)
    except Exception:
        _dense_available = False
    try:
        from sentence_transformers import CrossEncoder as _CE  # noqa: F401
        _reranker_available = True
    except Exception:
        _reranker_available = False
    from sahlha.app.rag.ocr import discover_tesseract
    return {"ok": True, "tts_configured": tts_mod.tts_available(),
            "images_configured": pexels_mod.pexels_available(),
            "llm_configured": llm_available(),
            "dense_embeddings_enabled": bool(_settings.dense_embeddings_enabled),
            "dense_embeddings_available": _dense_available,
            "reranker_enabled": bool(_settings.reranker_enabled),
            "reranker_available": bool(_reranker_available),
            "ocr_available": bool(discover_tesseract())}
