"""Question generation: retrieve -> structured gen -> validate -> save. + approval transitions."""
from sahlha.app.agent.agent import SahlhaAgent
from sahlha.app.agent.state import AgentState
from sahlha.app.agent.tools import question_tools
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag import ingestion
from tests.conftest import SAMPLE_TEXT


def _seed(db_session):
    ingestion.ingest_upload(db_session, file_bytes=SAMPLE_TEXT.encode(), filename="elif.txt",
                            course_id="python_101", lesson_id="elif_lesson", skill_id="python_elif")


def test_generate_validate_save(db_session):
    _seed(db_session)
    agent = SahlhaAgent(db_session, AgentState())
    out = agent.generate_question_bank(course_id="python_101", lesson_id="elif_lesson",
                                       skill_id="python_elif", n_questions=6)
    assert out["status"] == "pending_review"
    bank = question_tools.get_question_bank(db_session, out["question_bank_id"])
    assert bank and len(bank["questions"]) == 6
    for q in bank["questions"]:
        assert len(q["options"]) == 4 and 0 <= q["correct_answer"] <= 3


def test_approve_flow(db_session):
    _seed(db_session)
    agent = SahlhaAgent(db_session, AgentState())
    out = agent.generate_question_bank(course_id="python_101", lesson_id="elif_lesson",
                                       skill_id="python_elif", n_questions=4)
    bank = repo.get_bank(db_session, out["question_bank_id"])
    repo.set_bank_status(db_session, bank, "approved")
    assert repo.get_bank(db_session, bank.id).status == "approved"


def test_reject_then_regenerate_new_version(db_session):
    _seed(db_session)
    agent = SahlhaAgent(db_session, AgentState())
    v1 = agent.generate_question_bank(course_id="python_101", lesson_id="elif_lesson",
                                      skill_id="python_elif", n_questions=4)
    b1 = repo.get_bank(db_session, v1["question_bank_id"])
    repo.set_bank_status(db_session, b1, "rejected", "Too easy. Add more practical questions.")
    assert b1.version == 1 and b1.status == "rejected"

    agent2 = SahlhaAgent(db_session, AgentState())
    v2 = agent2.generate_question_bank(course_id="python_101", lesson_id="elif_lesson",
                                       skill_id="python_elif", n_questions=4,
                                       teacher_feedback="Too easy. Add more practical questions.")
    assert v2["version"] == 2, "history must not be overwritten; new version expected"
    assert repo.get_bank(db_session, v1["question_bank_id"]).status == "rejected"
