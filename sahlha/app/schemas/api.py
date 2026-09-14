from pydantic import BaseModel, Field


class GenerateBankRequest(BaseModel):
    course_id: str = "general"
    lesson_id: str = "lesson_1"
    skill_id: str = "general"
    teacher_feedback: str = ""
    n_questions: int = Field(default=8, ge=4, le=20)


class ExtractSkillsRequest(BaseModel):
    course_id: str = "general"
    lesson_id: str = "lesson_1"
    max_skills: int = Field(default=10, ge=1, le=20)  # upper bound only; agent decides the count
    force: bool = False  # re-extract even if skills already exist


class LessonBanksRequest(BaseModel):
    course_id: str = "general"
    lesson_id: str = "lesson_1"
    teacher_feedback: str = ""
    n_questions: int = Field(default=10, ge=4, le=15)  # per-skill bank size


class StartAssessmentRequest(BaseModel):
    student_id: str = "student_1"
    student_name: str = "Student"
    course_id: str | None = None
    lesson_id: str | None = None
    skill_id: str | None = None


class SubmitAssessmentRequest(BaseModel):
    answers: dict[str, object] = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    feedback: str = ""
