"""FastAPI entrypoint. Thin routes; logic lives in services/agent/tools."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from sahlha.app.api import routes_agent, routes_assessment, routes_audio, routes_documents, routes_images, routes_teacher
from sahlha.app.database.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sahlha AI Learning Agent (MVP)", lifespan=lifespan)
app.include_router(routes_documents.router)
app.include_router(routes_agent.router)
app.include_router(routes_teacher.router)
app.include_router(routes_assessment.router)
app.include_router(routes_audio.router)
app.include_router(routes_images.router)


@app.get("/")
def root():
    return {"service": "sahlha-mvp", "status": "ok"}


@app.get("/health")
def health():
    return {"ok": True}
