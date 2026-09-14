"""Streamlit test client for the Sahlha MVP loop (NOT production UI)."""
from __future__ import annotations

import os

import requests
import streamlit as st

API = os.getenv("SAHLHA_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="Sahlha MVP — Test Client", layout="wide")
st.title("Sahlha AI — MVP Test Client")

for key in ("last_bank", "assessment", "debug"):
    st.session_state.setdefault(key, None)

tab_teacher, tab_student, tab_debug = st.tabs(["👩‍🏫 Teacher", "🧑‍🎓 Student", "🛠️ Debug"])

# ---------------- Teacher ----------------
with tab_teacher:
    st.header("1. Upload material → RAG ingestion")
    course_id = st.text_input("course_id", "python_101", key="t_course")
    lesson_id = st.text_input("lesson_id", "elif_lesson", key="t_lesson")
    skill_id = st.text_input("skill_id", "python_elif", key="t_skill")
    up = st.file_uploader("Educational file (pdf/txt/docx/image)", type=["pdf", "txt", "md", "docx", "png", "jpg", "jpeg"])
    if st.button("Upload + Process", disabled=up is None):
        files = {"file": (up.name, up.getvalue())}
        r = requests.post(f"{API}/documents/upload",
                          data={"course_id": course_id, "lesson_id": lesson_id, "skill_id": skill_id},
                          files=files, timeout=120)
        st.json(r.json())
        st.session_state.debug = {"upload": r.json()}

    st.header("2. Agent splits lesson into skills (+ explanations)")
    st.caption("The agent decides how many skills (one per topic). The slider is only an upper bound.")
    n_sk = st.slider("max_skills (upper bound, hard cap 6)", 1, 6, 6)
    c1, c2 = st.columns(2)
    if c1.button("Extract skills"):
        r = requests.post(f"{API}/agent/extract-skills",
                          json={"course_id": course_id, "lesson_id": lesson_id,
                                "max_skills": n_sk}, timeout=180)
        data = r.json()
        st.json({k: v for k, v in data.items() if k not in ("trace", "skills")})
        st.session_state.debug = data
    if c2.button("Reload skills"):
        st.session_state.skills = requests.get(
            f"{API}/agent/skills", params={"course_id": course_id, "lesson_id": lesson_id},
            timeout=30).json()
    for s in (st.session_state.debug or {}).get("skills", []) if isinstance(st.session_state.debug, dict) else []:
        with st.expander(f"Skill: {s['name']} (`{s['skill_id']}`)"):
            st.write(s.get("description", ""))
            st.markdown("**Explanation:**")
            st.write(s.get("explanation", "") or "_pending_")
            st.caption(f"concepts: {', '.join(s.get('key_concepts', []))}")
    if st.session_state.get("skills"):
        for s in st.session_state.skills:
            with st.expander(f"Skill: {s['name']} (`{s['skill_id']}`)"):
                st.write(s.get("description", ""))
                st.markdown("**Explanation:**")
                st.write(s.get("explanation", "") or "_pending_")

    st.header("3. Generate one question bank per skill (10 questions each)")
    feedback = st.text_area("Teacher feedback for (re)generation (optional)", "")
    n_q = st.slider("questions per skill bank", 4, 15, 10)
    if st.button("Generate banks for all skills"):
        r = requests.post(f"{API}/agent/generate-lesson-banks",
                          json={"course_id": course_id, "lesson_id": lesson_id,
                                "teacher_feedback": feedback, "n_questions": n_q}, timeout=300)
        data = r.json()
        st.json({"lesson_id": data.get("lesson_id"), "num_skills": data.get("num_skills"),
                 "banks": [{k: v for k, v in b.items() if k != "trace"} for b in data.get("banks", [])]})
        st.session_state.debug = data

    st.header("4. Review pending banks (human-in-the-loop, per skill)")
    if st.button("Refresh pending"):
        st.session_state.pending = requests.get(f"{API}/teacher/question-banks/pending", timeout=30).json()
    for b in st.session_state.get("pending", []) or []:
        with st.expander(f"Bank {b['id']} v{b['version']} — {b['course_id']}/{b['lesson_id']} / `{b['skill_id']}`"):
            detail = requests.get(f"{API}/teacher/question-banks/{b['id']}", timeout=30).json()
            for q in detail.get("questions", []):
                st.markdown(f"**Q ({q['difficulty']}, {q['skill_id']})**: {q['question']}")
                st.write({i: o for i, o in enumerate(q["options"])})
                st.caption(f"correct={q['correct_answer']} | {q['explanation']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve", key=f"ap_{b['id']}"):
                st.json(requests.post(f"{API}/teacher/question-banks/{b['id']}/approve", timeout=30).json())
            rej_fb = st.text_input("Rejection feedback", key=f"rj_{b['id']}")
            if c2.button("❌ Reject", key=f"rjbtn_{b['id']}"):
                st.json(requests.post(f"{API}/teacher/question-banks/{b['id']}/reject",
                                      json={"feedback": rej_fb}, timeout=30).json())

# ---------------- Student ----------------
with tab_student:
    st.header("Learn skill by skill — each skill = explanation + exercise")
    sid = st.text_input("student_id", "student_1")
    sname = st.text_input("student_name", "Demo Student")
    sc, sl = st.columns(2)
    s_course = sc.text_input("course_id", "python_101", key="s_course")
    s_lesson = sl.text_input("lesson_id", "elif_lesson", key="s_lesson")
    if st.button("Load my skills"):
        st.session_state.progress = requests.get(
            f"{API}/students/{sid}/skill-progress",
            params={"course_id": s_course, "lesson_id": s_lesson}, timeout=30).json()
        st.session_state.skill_asm = {}
        st.session_state.studied = {}
    prog = st.session_state.get("progress") or {}
    if prog.get("skills"):
        st.progress(prog["completed"] / max(1, prog["total"]),
                    text=f"{prog['completed']}/{prog['total']} skills completed")
        for sk in prog["skills"]:
            status = "✅" if sk["completed"] else ("📖" if sk["has_explanation"] else "⏳")
            acc = f" — accuracy {sk['accuracy']:.0%}" if sk["accuracy"] is not None else ""
            with st.expander(f"{status} {sk['name']} (`{sk['skill_id']}`){acc}", expanded=False):
                det = requests.get(f"{API}/agent/skills",
                                   params={"course_id": s_course, "lesson_id": s_lesson,
                                           "skill_id": sk["skill_id"]}, timeout=30).json()
                expl = det[0].get("explanation", "") if det else ""
                st.markdown("**📖 Explanation — read this first:**")
                try:
                    ir = requests.get(
                        f"{API}/images/skill",
                        params={"course_id": s_course, "lesson_id": s_lesson,
                                "skill_id": sk["skill_id"]}, timeout=120)
                    if ir.status_code == 200:
                        st.image(ir.content, caption=det[0].get("image_alt", "") if det else "")
                    elif ir.status_code == 503:
                        st.info("🖼️ Skill images need PEXELS_API_KEY in the backend .env.")
                except Exception:
                    pass
                st.write(expl or "_No explanation yet._")
                akey = f"audio_{s_course}_{s_lesson}_{sk['skill_id']}"
                if st.button("🔊 Listen to explanation", key=f"tts_{sk['skill_id']}",
                             disabled=not expl):
                    try:
                        ar = requests.get(
                            f"{API}/audio/skill",
                            params={"course_id": s_course, "lesson_id": s_lesson,
                                    "skill_id": sk["skill_id"]}, timeout=180)
                        if ar.status_code == 503:
                            st.warning("Audio needs GROQ_API_KEY (+ accepted TTS model terms). "
                                       "Add it to the backend .env and restart it.")
                        elif ar.status_code != 200:
                            st.error(ar.text[:300])
                        else:
                            st.session_state[akey] = ar.content
                    except Exception as exc:
                        st.error(f"Audio request failed: {exc}")
                if st.session_state.get(akey):
                    st.audio(st.session_state[akey], format="audio/wav")
                st.caption(f"Exercise bank: {sk['bank_questions']} approved questions | "
                           f"attempted: {sk['attempted']}")
                asm = (st.session_state.get("skill_asm") or {}).get(sk["skill_id"])
                if not sk["exercise_ready"]:
                    st.warning("Teacher hasn't approved this skill's bank yet.")
                elif asm is None:
                    if st.button("Start this skill's exercise (4 questions)",
                                 key=f"start_{sk['skill_id']}"):
                        r = requests.post(
                            f"{API}/assessment/start",
                            json={"student_id": sid, "student_name": sname,
                                  "course_id": s_course, "lesson_id": s_lesson,
                                  "skill_id": sk["skill_id"]}, timeout=60)
                        if r.status_code != 200:
                            st.error(r.text)
                        else:
                            st.session_state.setdefault("skill_asm", {})[sk["skill_id"]] = r.json()
                            st.session_state.setdefault("studied", {})[sk["skill_id"]] = False
                            st.rerun()
                else:
                    st.session_state.setdefault("studied", {})[sk["skill_id"]] = st.checkbox(
                        "I've read the explanation — show my 4 questions",
                        value=st.session_state.get("studied", {}).get(sk["skill_id"], False),
                        key=f"studied_{sk['skill_id']}")
                    if st.session_state["studied"][sk["skill_id"]]:
                        answers: dict[str, int] = {}
                        for q in asm["questions"]:
                            st.markdown(f"**{q['question']}**  `[{q['difficulty']}]`")
                            opts = list(q["options"])
                            choice = st.radio("Your answer:", list(range(len(opts))),
                                              format_func=lambda i, _o=opts: f"{i}. {_o[i]}",
                                              key=f"{asm['assessment_id']}_{q['id']}")
                            answers[q["id"]] = choice
                        if st.button("Submit this skill's answers", key=f"sub_{sk['skill_id']}"):
                            r = requests.post(f"{API}/assessment/{asm['assessment_id']}/submit",
                                              json={"answers": answers}, timeout=60)
                            res = r.json()
                            st.json({k: v for k, v in res.items() if k != "trace"})
                            st.session_state.debug = res
                            st.session_state["skill_asm"].pop(sk["skill_id"], None)
                            st.session_state.progress = requests.get(
                                f"{API}/students/{sid}/skill-progress",
                                params={"course_id": s_course, "lesson_id": s_lesson},
                                timeout=30).json()
    st.header("Stored performance / memory")
    if st.button("Load performance"):
        st.json(requests.get(f"{API}/students/{sid}/performance", timeout=30).json())

# ---------------- Debug ----------------
with tab_debug:
    st.header("Developer / debug panel")
    dbg = st.session_state.debug
    if not dbg:
        st.info("No agent run captured yet. Generate a bank or run an assessment first.")
    else:
        trace = dbg.get("trace", [])
        if trace:
            st.subheader("Agent phases + tool calls")
            for t in trace:
                st.write(f"`{t.get('event')}` — {t.get('detail')}")
        for k in ("retrieved_chunks", "backend", "selection_meta", "skill_performance",
                  "score", "assessment_result"):
            if k in dbg:
                st.subheader(k)
                st.json(dbg[k])
        with st.expander("Full payload"):
            st.json(dbg)
