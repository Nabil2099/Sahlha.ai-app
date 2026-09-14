"""Skills: lesson -> agent-extracted skills -> explanations -> one bank per skill."""
from sahlha.app.database.repositories import repositories as repo
from sahlha.app.rag import ingestion
from sahlha.app.services import services as svc
from tests.conftest import SAMPLE_TEXT

LONG_TEXT = " ".join([
    "Python conditional statements control program flow with decisions.",
    "The if statement runs a block only when its condition is true.",
    "The elif keyword means else if and tests another condition when the first is false.",
    "Multiple elif branches are checked in order from top to bottom.",
    "Only the first branch whose condition is true will execute.",
    "The else block runs when no if or elif condition matched anything.",
    "Indentation defines which statements belong to each branch block.",
    "Comparison operators like double equals and greater than build conditions.",
])


def _seed(db_session):
    ingestion.ingest_upload(db_session, file_bytes=LONG_TEXT.encode(), filename="cond.txt",
                            course_id="python_101", lesson_id="cond_lesson", skill_id="python_cond")


def test_extract_skills_with_explanations(db_session):
    _seed(db_session)
    out = svc.extract_skills(db_session, course_id="python_101", lesson_id="cond_lesson", n_skills=3)
    skills = out["skills"]
    assert len(skills) >= 2, "lesson must be split into multiple skills"
    assert len({s["skill_id"] for s in skills}) == len(skills), "skill slugs must be unique"
    for s in skills:
        assert s["name"] and s["description"], "each skill needs name + description"
        assert s["explanation"] and len(s["explanation"]) > 40, "each skill needs an agent explanation"
    # Idempotent: second call returns existing rows, no duplicates
    out2 = svc.extract_skills(db_session, course_id="python_101", lesson_id="cond_lesson", n_skills=3)
    assert len(out2["skills"]) == len(skills)


def test_lesson_banks_one_per_skill(db_session):
    _seed(db_session)
    svc.extract_skills(db_session, course_id="python_101", lesson_id="cond_lesson", n_skills=3)
    res = svc.generate_lesson_banks(db_session, course_id="python_101", lesson_id="cond_lesson",
                                    n_questions=4)
    skills = svc.list_skills(db_session, course_id="python_101", lesson_id="cond_lesson")
    assert res["num_skills"] == len(skills) >= 2
    for bank in res["banks"]:
        assert bank["status"] == "pending_review"
    bank_skill_ids = {b["question_bank_id"] for b in res["banks"]}
    assert len(bank_skill_ids) == len(skills), "exactly one bank per skill"
    # every bank's questions carry their own skill
    for b in res["banks"]:
        detail = svc.bank_detail(db_session, b["question_bank_id"])
        assert detail["questions"], "bank must not be empty"
        assert {q["skill_id"] for q in detail["questions"]} == {detail["skill_id"]}


def test_skill_banks_approve_and_assess(db_session):
    _seed(db_session)
    svc.extract_skills(db_session, course_id="python_101", lesson_id="cond_lesson", n_skills=2)
    res = svc.generate_lesson_banks(db_session, course_id="python_101", lesson_id="cond_lesson",
                                    n_questions=4)
    for b in res["banks"]:
        svc.approve_bank(db_session, b["question_bank_id"])
    started = svc.start_assessment(db_session, student_id="skill_s1", student_name="Skill")
    # 4 questions from EACH skill bank
    assert len(started["questions"]) == 4 * res["num_skills"] == 8
    assert all(v == 4 for v in started["selection_meta"]["per_bank"].values())
    # Study-before-exercise: every covered skill ships its explanation, no answers leaked
    covered = {q["skill_id"] for q in started["questions"]}
    explained = {e["skill_id"] for e in started["skill_explanations"]}
    assert covered <= explained, "each assessed skill must have a study explanation"
    assert all(e["explanation"] for e in started["skill_explanations"])
    assert all("correct_answer" not in e for e in started["skill_explanations"])
    result = svc.submit_assessment(db_session, assessment_id=started["assessment_id"],
                                   answers={q["id"]: 0 for q in started["questions"]})
    assert result["total"] == 8
    assert len(repo.get_attempts(db_session, "skill_s1")) == 8


def test_http_skill_endpoints(client):
    client.post("/documents/upload", files={"file": ("cond.txt", LONG_TEXT)},
                data={"course_id": "c1", "lesson_id": "l1", "skill_id": "s"})
    ex = client.post("/agent/extract-skills", json={"course_id": "c1", "lesson_id": "l1", "max_skills": 2})
    assert ex.status_code == 200, ex.text
    assert len(ex.json()["skills"]) >= 1
    assert all(s["explanation"] for s in ex.json()["skills"])
    Fresh = client.get("/agent/skills", params={"course_id": "c1", "lesson_id": "l1"})
    assert len(Fresh.json()) == len(ex.json()["skills"])
    one = client.get("/agent/skills", params={"course_id": "c1", "lesson_id": "l1",
                                              "skill_id": ex.json()["skills"][0]["skill_id"]})
    assert len(one.json()) == 1 and one.json()[0]["explanation"], "single-skill study lookup"
    gen = client.post("/agent/generate-lesson-banks", json={"course_id": "c1", "lesson_id": "l1",
                                                             "n_questions": 4})
    assert gen.status_code == 200, gen.text
    assert gen.json()["num_skills"] >= 1
    for b in gen.json()["banks"]:
        client.post(f"/teacher/question-banks/{b['question_bank_id']}/approve")
    start = client.post("/assessment/start", json={"student_id": "study_s1"})
    assert start.status_code == 200, start.text
    assert start.json()["skill_explanations"], "assessment must include study material"
    assert all(s["explanation"] for s in start.json()["skill_explanations"])
    # 4 questions from EACH of the 2 approved banks
    assert len(start.json()["questions"]) == 8
    by_bank: dict[str, int] = {}
    for q in start.json()["questions"]:
        by_bank[q["bank_id"]] = by_bank.get(q["bank_id"], 0) + 1
    assert sorted(by_bank.values()) == [4, 4]


def test_lesson_explanation_flow(db_session):
    _seed(db_session)
    out = svc.extract_skills(db_session, course_id="python_101", lesson_id="cond_lesson", n_skills=2)
    assert out["lesson"]["explanation"] and len(out["lesson"]["explanation"]) > 60
    assert out["lesson"]["title"], "lesson overview needs a title"
    # Idempotent
    again = svc.explain_lesson(db_session, course_id="python_101", lesson_id="cond_lesson")
    assert again["lesson"]["id"] == out["lesson"]["id"]
    assert again["backend"] == "existing"
    # Study bundle
    bundle = svc.get_lesson(db_session, course_id="python_101", lesson_id="cond_lesson")
    assert bundle["lesson"]["explanation"]
    assert len(bundle["skills"]) >= 2
    # Attached to the assessment, ahead of the exercise
    res = svc.generate_lesson_banks(db_session, course_id="python_101", lesson_id="cond_lesson",
                                    n_questions=4)
    for b in res["banks"]:
        svc.approve_bank(db_session, b["question_bank_id"])
    started = svc.start_assessment(db_session, student_id="les_s1", student_name="Les")
    assert started["lesson_explanation"], "assessment must carry the lesson overview"
    assert started["lesson_explanation"]["explanation"]
    assert "correct_answer" not in str(started["lesson_explanation"])


def test_http_lesson_endpoints(client):
    client.post("/documents/upload", files={"file": ("cond.txt", LONG_TEXT)},
                data={"course_id": "c2", "lesson_id": "l2", "skill_id": "s"})
    ex = client.post("/agent/explain-lesson", params={"course_id": "c2", "lesson_id": "l2"})
    assert ex.status_code == 200, ex.text
    assert ex.json()["lesson"]["explanation"]
    bundle = client.get("/agent/lesson", params={"course_id": "c2", "lesson_id": "l2"})
    assert bundle.json()["lesson"]["explanation"]


def test_skill_is_explanation_plus_exercise(db_session):
    """One skill = study its explanation, then do its own 4-question exercise."""
    _seed(db_session)
    out = svc.extract_skills(db_session, course_id="python_101", lesson_id="cond_lesson", n_skills=2)
    res = svc.generate_lesson_banks(db_session, course_id="python_101", lesson_id="cond_lesson",
                                    n_questions=4)
    for b in res["banks"]:
        svc.approve_bank(db_session, b["question_bank_id"])
    target = out["skills"][0]["skill_id"]
    started = svc.start_assessment(db_session, student_id="unit_s1", student_name="Unit",
                                   course_id="python_101", lesson_id="cond_lesson", skill_id=target)
    assert len(started["questions"]) == 4
    assert {q["skill_id"] for q in started["questions"]} == {target}
    assert len(started["skill_explanations"]) == 1
    assert started["skill_explanations"][0]["explanation"], "exercise comes with its explanation"
    svc.submit_assessment(db_session, assessment_id=started["assessment_id"],
                          answers={q["id"]: 0 for q in started["questions"]})
    prog = svc.skill_progress(db_session, student_id="unit_s1",
                              course_id="python_101", lesson_id="cond_lesson")
    assert prog["total"] == 2 and prog["completed"] == 1
    done = next(s for s in prog["skills"] if s["skill_id"] == target)
    todo = next(s for s in prog["skills"] if s["skill_id"] != target)
    assert done["completed"] and done["attempted"] == 4 and done["exercise_ready"]
    assert not todo["completed"] and todo["attempted"] == 0


def test_http_skill_progress(client):
    client.post("/documents/upload", files={"file": ("cond.txt", LONG_TEXT)},
                data={"course_id": "c3", "lesson_id": "l3", "skill_id": "s"})
    client.post("/agent/extract-skills", json={"course_id": "c3", "lesson_id": "l3", "max_skills": 2})
    gen = client.post("/agent/generate-lesson-banks", json={"course_id": "c3", "lesson_id": "l3",
                                                             "n_questions": 4})
    for b in gen.json()["banks"]:
        client.post(f"/teacher/question-banks/{b['question_bank_id']}/approve")
    skills = client.get("/agent/skills", params={"course_id": "c3", "lesson_id": "l3"}).json()
    one = client.post("/assessment/start", json={"student_id": "prog_s1", "course_id": "c3",
                                                 "lesson_id": "l3",
                                                 "skill_id": skills[0]["skill_id"]})
    assert one.status_code == 200, one.text
    assert len(one.json()["questions"]) == 4
    client.post(f"/assessment/{one.json()['assessment_id']}/submit",
                json={"answers": {q["id"]: 0 for q in one.json()["questions"]}})
    prog = client.get("/students/prog_s1/skill-progress",
                      params={"course_id": "c3", "lesson_id": "l3"})
    assert prog.status_code == 200, prog.text
    assert prog.json()["completed"] == 1 and prog.json()["total"] == 2
