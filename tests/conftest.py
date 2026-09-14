"""Shared pytest fixtures: isolated SQLite DB per test module run."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("OPENAI_API_KEY", "")

from sahlha.app.database.database import Base, get_db  # noqa: E402


@pytest.fixture()
def db_session():
    from sahlha.app.database import models  # noqa: F401  (register)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(tmp.name)
        except PermissionError:
            pass  # Windows: SQLite handle may linger; temp file is harmless


@pytest.fixture()
def client(db_session):
    from sahlha.app.main import app

    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


SAMPLE_TEXT = (
    "Python elif lesson. The elif keyword means else-if. It lets a program test multiple "
    "conditions in order. If the first if condition is false, Python checks the elif condition. "
    "Only the first true branch executes. An optional else runs when nothing matches. "
    "Example: if score >= 90 grade A elif score >= 80 grade B else grade C."
)
