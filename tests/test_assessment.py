"""Assessment: approved bank -> select 4 -> submit -> evaluate -> persist. Memory reuse."""
from sahlha.app.agent.agent import SahlhaAgent
from sahlha.app.agent.state import AgentState
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag import ingestion
from sahlha.app.services import services as svc
from tests.conftest import SAMPLE_TEXT


def _approved_bank(db_session):
    ingestion.ingest_upload(db_session, file_bytes=(SAMPLE_TEXT * 3).encode(), filename="elif.txt",
                            course_id="python_101", lesson_id="elif_lesson", skill_id="python_elif")
    out = SahlhaAgent(db_session, AgentState()).generate_question_bank(
        course_id="python_101", lesson_id="elif_lesson", skill_id="python_elif", n_questions=8)
    repo.set_bank_status(db_session, repo.get_bank(db_session, out["question_bank_id"]), "approved")
    return out


def test_full_assessment_loop(db_session):
    _approved_bank(db_session)
    started = svc.start_assessment(db_session, student_id="s1", student_name="S1")
    assert len(started["questions"]) == 4, "MVP selects exactly 4 questions"
    assert all("correct_answer" not in q for q in started["questions"]), "never leak answers"

    qids = [q["id"] for q in started["questions"]]
    answers = {qid: 0 for qid in qids}  # answer index 0 for all
    result = svc.submit_assessment(db_session, assessment_id=started["assessment_id"], answers=answers)
    assert result["total"] == 4
    assert len(result["results"]) == 4
    assert all(set(("question_id", "correct", "student_answer", "correct_answer", "skill_id")) <= set(r)
               for r in result["results"])

    attempts = repo.get_attempts(db_session, "s1")
    assert len(attempts) == 4, "every attempt must be stored individually"

    perf = svc.student_performance(db_session, "s1")
    assert perf["skill_performance"], "memory must be updated"
    assert len(perf["attempts"]) == 4


def test_memory_influences_next_assessment(db_session):
    _approved_bank(db_session)
    # Fail everything first time
    started = svc.start_assessment(db_session, student_id="s2", student_name="S2")
    svc.submit_assessment(db_session, assessment_id=started["assessment_id"],
                          answers={q["id"]: "definitely wrong answer xyz" for q in started["questions"]})
    failed = set(repo.get_failed_question_ids(db_session, "s2"))
    assert failed, "expected failures to be recorded"

    # Second assessment should prefer retrying failed questions
    started2 = svc.start_assessment(db_session, student_id="s2", student_name="S2")
    ids2 = {q["id"] for q in started2["questions"]}
    assert failed & ids2, "next assessment should retry at least one failed question"
    assert started2["selection_meta"]["failed_retried"], "selection rationale must record retries"
