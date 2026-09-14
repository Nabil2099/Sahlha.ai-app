"""RAG: upload -> process -> retrieve relevant lesson."""
from sahlha.app.rag import ingestion, retriever
from tests.conftest import SAMPLE_TEXT


def test_rag_ingest_and_retrieve(db_session):
    info = ingestion.ingest_upload(db_session, file_bytes=SAMPLE_TEXT.encode(),
                                   filename="elif.txt", course_id="python_101",
                                   lesson_id="elif_lesson", skill_id="python_elif")
    assert info["chunk_count"] >= 1
    assert info["char_count"] > 100
    assert info["method"] == "txt"

    chunks = retriever.retrieve_lesson(db_session, "python_101", "elif_lesson", top_k=3)
    assert chunks, "retriever returned nothing"
    assert all(set(("document_id", "course_id", "lesson_id", "skill_id", "page", "chunk_id", "text")) <= set(c)
               for c in chunks)
    assert "elif" in " ".join(c["text"] for c in chunks).lower()
