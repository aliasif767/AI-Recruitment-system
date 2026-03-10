import os
import re
import json
import hashlib
from typing import Literal, List
from typing_extensions import TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

from models import CandidateReport, SkillMatch, LanguageMatch, ProjectHighlight, EvaluationScore
from tools import GithubAuditTool

load_dotenv()

# ─────────────────────────────────────────────
# Deterministic Result Cache
# Same CV + Same JD = identical result always
# ─────────────────────────────────────────────
_SCORE_CACHE: dict = {}
_CACHE_FILE = ".recruiter_cache.json"

def _load_cache():
    global _SCORE_CACHE
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r") as f:
                _SCORE_CACHE = json.load(f)
            print(f"   💾 Cache loaded: {len(_SCORE_CACHE)} entries")
        except Exception:
            _SCORE_CACHE = {}

def _save_cache():
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(_SCORE_CACHE, f, indent=2)
    except Exception:
        pass

def _cache_key(resume_text: str, job_description: str) -> str:
    combined = resume_text.strip() + "|||" + job_description.strip()
    return hashlib.sha256(combined.encode()).hexdigest()

_load_cache()

# ─────────────────────────────────────────────
# Scoring Rubric — forces mathematical scoring
# ─────────────────────────────────────────────
SCORING_RUBRIC = """
═══ DETERMINISTIC SCORING RUBRIC — FOLLOW EXACTLY ═══

Compute match_score using this FIXED weighted formula.
YOU MUST SHOW YOUR CALCULATION STEP BY STEP.

  CATEGORY              WEIGHT   MAX PTS
  ─────────────────────────────────────
  Technical Skills        35%      35
  Programming Languages   20%      20
  Project Relevance       20%      20
  Years of Experience     15%      15
  Code Quality / GitHub   10%      10
  ─────────────────────────────────────
  TOTAL                  100%     100

TECHNICAL SKILLS (max 35):
  - Identify all must-have skills from the JD (call this N, max 5)
  - For each must-have skill the candidate CLEARLY has: earn (35 / N) points
  - "Clearly has" = direct evidence in resume or GitHub. No assumptions.

PROGRAMMING LANGUAGES (max 20):
  - Identify all required languages from the JD (call this L)
  - For each required language the candidate knows: earn (20 / L) points
  - Evidence: mentioned in resume, or GitHub repos exist in that language

PROJECT RELEVANCE (max 20):
  - 3 or more directly relevant projects = 20 pts
  - 1-2 directly relevant projects      = 10 pts
  - Only tangentially relevant projects = 5 pts
  - No relevant projects                = 0 pts

YEARS OF EXPERIENCE (max 15):
  - Meets or exceeds required years     = 15 pts
  - Within 6 months short               = 10 pts
  - Within 1 year short                 = 7 pts
  - Less than half of required years    = 3 pts
  - No experience found                 = 0 pts

CODE QUALITY / GITHUB (max 10):
  - Active GitHub with relevant repos   = 10 pts
  - GitHub exists, low activity         = 5 pts
  - No GitHub found                     = 0 pts

FINAL RULES:
  match_score = sum of all 5 category scores (integer)
  match_score >= 70  → final_decision = "MATCH"
  match_score 50-69  → final_decision = "MAYBE"
  match_score < 50   → final_decision = "NO_MATCH"

Put your step-by-step calculation inside cultural_fit_notes.
═══════════════════════════════════════════════════════
"""

# ─────────────────────────────────────────────
# State
# ─────────────────────────────────────────────
class RecruiterState(TypedDict):
    job_description: str
    resume_text: str
    github_handle: str
    jd_analysis: str          # structured JD breakdown
    screening_verdict: str    # MATCH / NO_MATCH + extracted handles
    github_audit: str         # raw GitHub data
    skill_analysis: str       # deep skill comparison
    project_analysis: str     # project relevance analysis
    is_technical_match: bool
    final_evaluation: CandidateReport
    cache_hit: bool


# ─────────────────────────────────────────────
# LLM & Tools
# ─────────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    model_kwargs={"seed": 42},
)
github_tool = GithubAuditTool()


# ─────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────

def cache_check(state: RecruiterState):
    """Return cached result immediately if this exact CV+JD was seen before."""
    key = _cache_key(state["resume_text"], state["job_description"])
    if key in _SCORE_CACHE:
        try:
            report = CandidateReport(**_SCORE_CACHE[key])
            # Only use cache if it's a real valid result
            if report.match_score > 0 and report.candidate_name not in ("Unknown", "", "Candidate"):
                print(f"   ✅ Cache hit — {report.candidate_name} score: {report.match_score}%")
                return {"final_evaluation": report, "cache_hit": True}
            else:
                # Stale/failed cache entry — delete it and reprocess
                print(f"   🗑️ Stale cache entry removed — will reprocess")
                del _SCORE_CACHE[key]
                _save_cache()
        except Exception:
            pass
    return {"cache_hit": False}


def jd_architect(state: RecruiterState):
    """Deeply deconstructs the JD into a structured requirements profile."""
    prompt = (
        "You are a senior technical recruiter. Analyze this Job Description deeply.\n\n"
        "Extract and structure:\n"
        "1. MUST-HAVE SKILLS (list each with why it's critical)\n"
        "2. NICE-TO-HAVE SKILLS\n"
        "3. REQUIRED PROGRAMMING LANGUAGES (specify each)\n"
        "4. REQUIRED FRAMEWORKS/TOOLS\n"
        "5. MINIMUM YEARS OF EXPERIENCE\n"
        "6. PROJECT TYPES they should have built\n"
        "7. IDEAL CANDIDATE PERSONA\n\n"
        f"Job Description:\n{state['job_description']}"
    )
    response = llm.invoke(prompt)
    return {"jd_analysis": response.content}


def resume_screener(state: RecruiterState):
    """Fast initial screen + GitHub handle extraction."""
    prompt = (
        f"Quickly analyze this resume vs the JD requirements.\n\n"
        f"RESUME:\n{state['resume_text']}\n\n"
        f"JD REQUIREMENTS:\n{state['jd_analysis']}\n\n"
        f"Answer:\n"
        f"1. Is this a technical match? (MATCH if meets ≥60% must-haves, else NO_MATCH)\n"
        f"2. Extract GitHub username/URL (write NOT_FOUND if absent)\n"
        f"3. Estimated years of experience\n\n"
        f"Respond EXACTLY in this format:\n"
        f"VERDICT: [MATCH/NO_MATCH]\n"
        f"GITHUB: [handle or NOT_FOUND]\n"
        f"EXPERIENCE: [X years]"
    )
    response = llm.invoke(prompt).content

    is_match = "VERDICT: MATCH" in response.upper()

    github_match = re.search(r"GITHUB:\s*(\S+)", response, re.IGNORECASE)
    github_handle = github_match.group(1) if github_match else "unknown"
    github_handle = re.sub(r"https?://(www\.)?github\.com/", "", github_handle).strip("/")
    if github_handle.lower() in ["not_found", "none", "n/a", "unknown"]:
        github_handle = "unknown"

    return {
        "screening_verdict": response,
        "is_technical_match": is_match,
        "github_handle": github_handle,
    }


def github_auditor(state: RecruiterState):
    """Fetch full GitHub profile + repositories."""
    handle = state.get("github_handle", "unknown")
    if handle.lower() in ["unknown", "not_found", "none", ""]:
        return {"github_audit": "No GitHub handle found in resume."}

    print(f"   🔍 Auditing GitHub: @{handle}")
    try:
        data = github_tool._run(handle)
        return {"github_audit": data}
    except Exception as e:
        return {"github_audit": f"GitHub audit failed: {str(e)}"}


def skill_analyzer(state: RecruiterState):
    """Deep skill-by-skill comparison between JD requirements and candidate."""
    prompt = (
        "You are a precise technical evaluator. Compare the candidate's skills EXACTLY against the JD.\n\n"
        "For EVERY skill and language mentioned in the JD:\n"
        "- Check if the candidate has it (yes/no)\n"
        "- Rate their proficiency 0-10 with specific evidence\n"
        "- Note years of experience with that skill\n"
        "- Identify skill gaps\n\n"
        "Also identify any BONUS skills the candidate has beyond the JD.\n\n"
        f"JD REQUIREMENTS:\n{state['jd_analysis']}\n\n"
        f"RESUME:\n{state['resume_text']}\n\n"
        f"GITHUB DATA:\n{state.get('github_audit', 'Not available')}\n\n"
        "Provide a detailed, evidence-based skill breakdown."
    )
    response = llm.invoke(prompt)
    return {"skill_analysis": response.content}


def project_analyzer(state: RecruiterState):
    """Analyze projects for relevance, quality, and tech alignment."""
    prompt = (
        "You are a senior engineer evaluating project quality and relevance.\n\n"
        "Analyze ALL projects from the candidate's resume and GitHub:\n"
        "- How relevant is each project to this specific job role?\n"
        "- What tech stack did they use?\n"
        "- What was the complexity and impact?\n"
        "- Do the projects PROVE the required skills?\n"
        "- Any impressive or standout work?\n\n"
        f"JD (what kind of projects matter):\n{state['jd_analysis']}\n\n"
        f"RESUME:\n{state['resume_text']}\n\n"
        f"GITHUB REPOS:\n{state.get('github_audit', 'Not available')}\n\n"
        "Rank each project by relevance to the job (0-10)."
    )
    response = llm.invoke(prompt)
    return {"project_analysis": response.content}


def quality_control_officer(state: RecruiterState):
    """
    Two-pass structured output to avoid Groq 400 tool validation errors.
    Pass 1: basic fields + score (small schema, always works)
    Pass 2: nested lists (skills, languages, projects, eval scores)
    Results merged into one CandidateReport and cached.
    """

    resume    = state["resume_text"]
    jd        = state["jd_analysis"]
    screening = state.get("screening_verdict", "N/A")
    github    = state.get("github_audit", "Not available")
    skills    = state.get("skill_analysis", "N/A")
    projects  = state.get("project_analysis", "N/A")

    context = (
        f"RESUME:\n{resume}\n\n"
        f"JD REQUIREMENTS:\n{jd}\n\n"
        f"SCREENING:\n{screening}\n\n"
        f"GITHUB:\n{github}\n\n"
        f"SKILL ANALYSIS:\n{skills}\n\n"
        f"PROJECT ANALYSIS:\n{projects}"
    )

    # ── PASS 1: Core fields only (flat schema — never fails) ──────────────
    class CoreReport(BaseModel):
        candidate_name: str = "Unknown"
        email: str = ""
        phone_no: str = ""
        university_name: str = ""
        cgpa: str = ""
        github_handle: str = ""
        years_of_experience: str = "Unknown"
        match_score: int = Field(default=0, description="Integer 0-100")
        final_decision: str = "NO_MATCH"
        cultural_fit_notes: str = ""
        strengths: List[str] = Field(default_factory=list)
        red_flags: List[str] = Field(default_factory=list)
        outreach_email_draft: str = ""

        @field_validator("match_score", mode="before")
        @classmethod
        def to_int(cls, v):
            if isinstance(v, str):
                import re as _re
                c = _re.sub(r'[^0-9]', '', v)
                return int(c) if c else 0
            try: return int(v)
            except: return 0

        @field_validator("final_decision", mode="before")
        @classmethod
        def fix_decision(cls, v):
            v = str(v).upper().strip()
            if "NO" in v: return "NO_MATCH"
            if "MAYBE" in v: return "MAYBE"
            if "MATCH" in v: return "MATCH"
            return "NO_MATCH"

    pass1_prompt = (
        "Fill the CoreReport for this candidate. "
        "IMPORTANT: match_score must be a plain integer like 75, NOT a string, NOT null.\n\n"
        + SCORING_RUBRIC
        + "\n\n" + context
    )

    # Retry up to 3 times — Groq occasionally rejects structured output on first try
    core = None
    for _attempt in range(3):
        try:
            core = llm.with_structured_output(CoreReport).invoke(pass1_prompt)
            if core.match_score > 0 and core.candidate_name not in ("Unknown", ""):
                break  # valid result
            print(f"   🔄 Pass 1 attempt {_attempt+1}: got score={core.match_score}, retrying...")
        except Exception as e:
            print(f"   🔄 Pass 1 attempt {_attempt+1} failed: {str(e)[:80]}")
            core = None

    if core is None or core.match_score == 0:
        # Final fallback: plain text extraction (no structured output)
        print("   ⚠️ Structured output failed — using plain text fallback")
        try:
            fallback_prompt = (
                "From the resume below, extract these fields as plain text:\n"
                "NAME: <full name>\n"
                "EMAIL: <email>\n"
                "PHONE: <phone>\n"
                "UNIVERSITY: <university>\n"
                "CGPA: <cgpa>\n"
                "GITHUB: <github handle>\n"
                "EXPERIENCE: <years>\n"
                "SCORE: <integer 0-100 based on rubric>\n"
                "DECISION: <MATCH/MAYBE/NO_MATCH>\n\n"
                + SCORING_RUBRIC + "\n\n" + context
            )
            raw = llm.invoke(fallback_prompt).content
            def _extract(label, text):
                m = __import__("re").search(rf"{label}:\s*(.+)", text, __import__("re").IGNORECASE)
                return m.group(1).strip() if m else ""
            score_raw = _extract("SCORE", raw)
            score_int = int(__import__("re").sub(r"[^0-9]", "", score_raw)) if score_raw else 50
            decision  = _extract("DECISION", raw).upper()
            if "NO" in decision:   decision = "NO_MATCH"
            elif "MAYBE" in decision: decision = "MAYBE"
            elif "MATCH" in decision: decision = "MATCH"
            else: decision = "MAYBE" if score_int >= 50 else "NO_MATCH"
            core = CoreReport(
                candidate_name       = _extract("NAME", raw) or "Candidate",
                email                = _extract("EMAIL", raw),
                phone_no             = _extract("PHONE", raw),
                university_name      = _extract("UNIVERSITY", raw),
                cgpa                 = _extract("CGPA", raw),
                github_handle        = _extract("GITHUB", raw),
                years_of_experience  = _extract("EXPERIENCE", raw) or "Unknown",
                match_score          = score_int,
                final_decision       = decision,
                cultural_fit_notes   = "Extracted via plain text fallback.",
                strengths            = [],
                red_flags            = [],
                outreach_email_draft = ""
            )
            print(f"   ✅ Fallback succeeded: {core.candidate_name} → {core.match_score}%")
        except Exception as fe:
            raise RuntimeError(f"All extraction methods failed: {fe}")

    # ── PASS 2: Lists only (separate call — smaller schema) ──────────────
    class ListsReport(BaseModel):
        skill_matches: List[SkillMatch] = Field(default_factory=list)
        language_matches: List[LanguageMatch] = Field(default_factory=list)
        project_highlights: List[ProjectHighlight] = Field(default_factory=list)
        evaluation_scores: List[EvaluationScore] = Field(default_factory=list)

    pass2_prompt = (
        "Fill the ListsReport for this candidate.\n\n"
        "skill_matches: one entry per JD must-have skill + major extras. "
        "required=true for JD must-haves. candidate_has=true only with direct evidence. "
        "proficiency 0-10.\n\n"
        "language_matches: one entry per required language + languages candidate uses. "
        "jd_requires=true if JD specifies it.\n\n"
        "project_highlights: top 5 projects by relevance, relevance_score 0-10.\n\n"
        "evaluation_scores: exactly these 6 categories scored 0-100: "
        "Technical Skills, Programming Languages, Project Relevance, "
        "Experience Level, Code Quality, Learning & Growth.\n\n"
        + context
    )

    try:
        lists = llm.with_structured_output(ListsReport).invoke(pass2_prompt)
    except Exception as e:
        print(f"   ⚠️ Pass 2 failed: {e}. Using empty lists.")
        lists = ListsReport()

    # ── Merge into final CandidateReport ─────────────────────────────────
    report = CandidateReport(
        candidate_name      = core.candidate_name,
        email               = core.email,
        phone_no            = core.phone_no,
        university_name     = core.university_name,
        cgpa                = core.cgpa,
        github_handle       = core.github_handle,
        years_of_experience = core.years_of_experience,
        match_score         = core.match_score,
        final_decision      = core.final_decision,
        cultural_fit_notes  = core.cultural_fit_notes,
        strengths           = core.strengths,
        red_flags           = core.red_flags,
        outreach_email_draft= core.outreach_email_draft,
        skill_matches       = lists.skill_matches,
        language_matches    = lists.language_matches,
        project_highlights  = lists.project_highlights,
        evaluation_scores   = lists.evaluation_scores,
        github_summary      = github,
    )

    # ── Only cache valid results (never cache failures) ─────────────────
    if report.match_score > 0 and report.candidate_name not in ("Unknown", "", "Candidate"):
        key = _cache_key(state["resume_text"], state["job_description"])
        _SCORE_CACHE[key] = report.model_dump()
        _save_cache()
        print(f"   💾 Cached: {report.candidate_name} → {report.match_score}%")
    else:
        print(f"   ⚠️ Result not cached (score=0 or unknown name) — will retry next run")

    return {"final_evaluation": report, "cache_hit": False}


# ─────────────────────────────────────────────
# Routing
# ─────────────────────────────────────────────

def route_after_cache(state: RecruiterState) -> Literal["analyze_jd", "done"]:
    """Skip the entire pipeline if we already have a cached result."""
    return "done" if state.get("cache_hit") else "analyze_jd"

def route_after_screen(state: RecruiterState) -> Literal["deep_dive", "quick_report"]:
    return "deep_dive" if state["is_technical_match"] else "quick_report"


# ─────────────────────────────────────────────
# Graph
# ─────────────────────────────────────────────

workflow = StateGraph(RecruiterState)

workflow.add_node("check_cache", cache_check)
workflow.add_node("analyze_jd", jd_architect)
workflow.add_node("screen_resume", resume_screener)
workflow.add_node("audit_github", github_auditor)
workflow.add_node("analyze_skills", skill_analyzer)
workflow.add_node("analyze_projects", project_analyzer)
workflow.add_node("finalize_report", quality_control_officer)

workflow.add_edge(START, "check_cache")

workflow.add_conditional_edges(
    "check_cache",
    route_after_cache,
    {"analyze_jd": "analyze_jd", "done": END}
)
workflow.add_edge("analyze_jd", "screen_resume")

workflow.add_conditional_edges(
    "screen_resume",
    route_after_screen,
    {
        "deep_dive": "audit_github",
        "quick_report": "finalize_report",
    }
)

# Deep dive path: GitHub → Skills → Projects → Report
workflow.add_edge("audit_github", "analyze_skills")
workflow.add_edge("analyze_skills", "analyze_projects")
workflow.add_edge("analyze_projects", "finalize_report")
workflow.add_edge("finalize_report", END)

app = workflow.compile()