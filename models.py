import re
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class SkillMatch(BaseModel):
    skill_name: str = ""
    required: bool = False
    candidate_has: bool = False
    proficiency: int = 0
    evidence: str = ""
    years: str = "Unknown"


class LanguageMatch(BaseModel):
    language: str = ""
    jd_requires: bool = False
    candidate_has: bool = False
    proficiency: int = 0
    evidence: str = ""


class ProjectHighlight(BaseModel):
    project_name: str = ""
    relevance_score: int = 0
    tech_stack: List[str] = Field(default_factory=list)
    description: str = ""
    source: str = "Resume"
    impact: str = ""


class EvaluationScore(BaseModel):
    category: str = ""
    score: int = 0
    notes: str = ""


class CandidateReport(BaseModel):
    candidate_name: str = "Unknown"
    email: str = ""
    phone_no: str = ""
    university_name: str = ""
    cgpa: str = ""
    github_handle: str = ""
    years_of_experience: str = "Unknown"

    match_score: int = Field(default=0, description="Integer 0-100 only. No quotes.")

    skill_matches: List[SkillMatch] = Field(default_factory=list)
    language_matches: List[LanguageMatch] = Field(default_factory=list)
    project_highlights: List[ProjectHighlight] = Field(default_factory=list)
    evaluation_scores: List[EvaluationScore] = Field(default_factory=list)

    strengths: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    cultural_fit_notes: str = ""
    github_summary: str = ""
    final_decision: str = "NO_MATCH"
    outreach_email_draft: str = ""

    @field_validator("match_score", mode="before")
    @classmethod
    def ensure_int(cls, v):
        if isinstance(v, str):
            cleaned = re.sub(r'[^0-9]', '', v)
            return int(cleaned) if cleaned else 0
        try:
            return int(v)
        except Exception:
            return 0

    @field_validator("final_decision", mode="before")
    @classmethod
    def normalize_decision(cls, v):
        v = str(v).upper().strip()
        if "NO_MATCH" in v or "NO MATCH" in v or "NOMATCH" in v:
            return "NO_MATCH"
        elif "MAYBE" in v:
            return "MAYBE"
        elif "MATCH" in v:
            return "MATCH"
        return "NO_MATCH"

    @field_validator("proficiency", mode="before", check_fields=False)
    @classmethod
    def clamp_proficiency(cls, v):
        try:
            return max(0, min(10, int(v)))
        except Exception:
            return 0