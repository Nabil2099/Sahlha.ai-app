"""End-to-end HTTP loop: upload -> generate -> approve -> start -> submit -> performance."""
from tests.conftest import SAMPLE_TEXT


def test_http_loop(client):
    up = client.post("/documents/upload", files={"file": ("elif.txt", SAMPLE_TEXT * 2)},
                     data={"course_id": "python_101", "lesson_id": "elif_lesson", "skill_id": "python_elif"})
    assert up.status_code == 200, up.text
    assert up.json()["chunk_count"] >= 1

    gen = client.post("/agent/generate-question-bank",
                      json={"course_id": "python_101", "lesson_id": "elif_lesson",
                            "skill_id": "python_elif", "n_questions": 8})
    assert gen.status_code == 200, gen.text
    bank_id = gen.json()["question_bank_id"]

    pend = client.get("/teacher/question-banks/pending")
    assert any(b["id"] == bank_id for b in pend.json())

    ap = client.post(f"/teacher/question-banks/{bank_id}/approve")
    assert ap.json()["status"] == "approved"

    start = client.post("/assessment/start", json={"student_id": "http_s1", "student_name": "HTTP"})
    assert start.status_code == 200, start.text
    assert len(start.json()["questions"]) == 4
    asm_id = start.json()["assessment_id"]

    answers = {q["id"]: 0 for q in start.json()["questions"]}
    sub = client.post(f"/assessment/{asm_id}/submit", json={"answers": answers})
    assert sub.status_code == 200, sub.text
    assert sub.json()["total"] == 4

    perf = client.get("/students/http_s1/performance")
    assert len(perf.json()["attempts"]) == 4
