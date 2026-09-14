"""SQLAlchemy engine / session factory. Application owns all transactions."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from sahlha.app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from sahlha.app.database import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Lightweight additive migration for SQLite (create_all won't ALTER existing tables)."""
    from sqlalchemy import inspect, text

    wanted: dict[str, list[tuple[str, str]]] = {
        "skills": [("image_url", "VARCHAR(1024)"), ("image_path", "VARCHAR(1024)"),
                   ("image_alt", "VARCHAR(512)")],
    }
    with engine.connect() as conn:
        for table, cols in wanted.items():
            if not inspect(conn).has_table(table):
                continue
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            conn.commit()
