"""SQLAlchemy engine / session factory. Application owns all transactions."""
from pathlib import Path

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

    # SQLite creates the database file, but not its parent directories.
    if engine.dialect.name == "sqlite":
        database = engine.url.database
        if database and database != ":memory:" and not engine.url.query.get("uri"):
            Path(database).parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Lightweight additive migration for SQLite (create_all won't ALTER existing tables).

    Additive only: new tables are created by create_all; here we add columns to
    tables that already exist from an older version. The legacy performance
    uniqueness constraint uses a transactional copy with the original table retained.
    """
    from sqlalchemy import inspect, text

    if engine.dialect.name != "sqlite":
        return
    wanted: dict[str, list[tuple[str, str]]] = {
        "skills": [("image_url", "VARCHAR(1024)"), ("image_path", "VARCHAR(1024)"),
                   ("image_alt", "VARCHAR(512)"), ("audio_path", "VARCHAR(1024) DEFAULT ''")],
        "lesson_explanations": [("audio_path", "VARCHAR(1024) DEFAULT ''"),
                                ("image_url", "VARCHAR(1024) DEFAULT ''"),
                                ("image_path", "VARCHAR(1024) DEFAULT ''"), ("image_alt", "VARCHAR(512) DEFAULT ''")],
        "assessments": [("course_id", "VARCHAR(128) DEFAULT ''"), ("lesson_id", "VARCHAR(128) DEFAULT ''"),
                        ("selection_meta", "JSON DEFAULT '{}' ")],
        "questions": [("retired", "BOOLEAN NOT NULL DEFAULT 0")],
        "question_banks": [("teacher_id", "VARCHAR(32)"), ("classroom_id", "VARCHAR(32)"),
                           ("material_id", "VARCHAR(32)")],
        "student_skill_performance": [("course_id", "VARCHAR(128)"), ("lesson_id", "VARCHAR(128)"),
                                      ("skill_row_id", "VARCHAR(32)")],
    }
    additions = {
        "documents": {"blocks": "JSON DEFAULT '[]'", "extraction_quality": "JSON DEFAULT '{}'"},
        "document_chunks": {"section": "TEXT DEFAULT ''", "section_id": "TEXT DEFAULT ''", "type": "TEXT DEFAULT 'paragraph'", "block_metadata": "JSON DEFAULT '{}'"},
        "skills": {"extraction_active": "BOOLEAN NOT NULL DEFAULT 1", "learning_objective": "TEXT DEFAULT ''", "prerequisites": "JSON DEFAULT '[]'", "misconceptions": "JSON DEFAULT '[]'", "difficulty": "TEXT DEFAULT ''", "source_section_ids": "JSON DEFAULT '[]'", "evidence_chunk_ids": "JSON DEFAULT '[]'", "learning_content": "JSON DEFAULT '{}'"},
        "questions": {"evidence_chunk_ids": "JSON DEFAULT '[]'", "learning_objective": "TEXT DEFAULT ''", "tested_concept": "TEXT DEFAULT ''", "verification": "JSON DEFAULT '{}'"},
        "learning_materials": {"quality_signals": "JSON DEFAULT '{}'"},
    }
    for table, columns in additions.items():
        wanted.setdefault(table, []).extend(columns.items())
    with engine.connect() as conn:
        for table, cols in wanted.items():
            if not inspect(conn).has_table(table):
                continue
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            conn.commit()

    _migrate_performance_constraint()
    _backfill_assessment_scopes()


def _migrate_performance_constraint():
    """SQLite cannot drop a UNIQUE constraint: copy transactionally, retaining rows.

    Only the old (student, skill) constraint is replaced. No learner data is reset.
    """
    from sqlalchemy import inspect, text
    from sahlha.app.database.models import StudentSkillPerformance
    from sqlalchemy.schema import CreateTable
    with engine.begin() as conn:
        constraints = inspect(conn).get_unique_constraints("student_skill_performance")
        legacy = any(set(c["column_names"]) == {"student_id", "skill_id"} for c in constraints)
        conn.execute(text("UPDATE student_skill_performance SET course_id = COALESCE(course_id, ''), lesson_id = COALESCE(lesson_id, '')"))
        if not legacy:
            return
        # Reproduce the mapped schema with a temporary name. All existing mapped fields survive.
        ddl = str(CreateTable(StudentSkillPerformance.__table__).compile(conn))
        ddl = ddl.replace("CREATE TABLE student_skill_performance", "CREATE TABLE student_skill_performance_scoped", 1)
        conn.execute(text(ddl))
        columns = ", ".join(c.name for c in StudentSkillPerformance.__table__.columns)
        conn.execute(text(f"INSERT INTO student_skill_performance_scoped ({columns}) SELECT {columns} FROM student_skill_performance"))
        conn.execute(text("ALTER TABLE student_skill_performance RENAME TO student_skill_performance_legacy_backup"))
        conn.execute(text("ALTER TABLE student_skill_performance_scoped RENAME TO student_skill_performance"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scoped_performance_student_id ON student_skill_performance(student_id)"))


def _backfill_assessment_scopes():
    """Adopt scope only when every selected question agrees; never sample one bank."""
    import json
    from sqlalchemy import text
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, question_ids FROM assessments WHERE COALESCE(course_id, '') = ''")).all()
        for aid, question_ids in rows:
            ids = json.loads(question_ids) if isinstance(question_ids, str) else question_ids
            if not ids:
                continue
            from sqlalchemy import select
            from sahlha.app.database.models import Question, QuestionBank
            pairs = conn.execute(select(Question.id, QuestionBank.course_id, QuestionBank.lesson_id)
                .join(QuestionBank, Question.question_bank_id == QuestionBank.id).where(Question.id.in_(ids))).all()
            if len(pairs) != len(set(ids)):
                continue
            courses, lessons = {r[1] for r in pairs}, {r[2] for r in pairs}
            conn.execute(text("UPDATE assessments SET course_id=:course, lesson_id=:lesson WHERE id=:id"),
                         {"id": aid, "course": next(iter(courses)) if len(courses) == 1 else "",
                          "lesson": next(iter(lessons)) if len(courses) == len(lessons) == 1 else ""})
