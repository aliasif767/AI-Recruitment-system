import streamlit as st
import os, json, time, shutil, tempfile
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

load_dotenv()

# ─────────────────────────────────────────────
# Helpers & Business Logic
# ─────────────────────────────────────────────

def generate_interview_slots(n=3):
    slots = []
    base = datetime.now() + timedelta(days=2)
    added = 0
    while added < n:
        if base.weekday() < 5:
            for hour in [10, 14, 16]:
                slots.append(base.replace(hour=hour, minute=0, second=0, microsecond=0))
                added += 1
                if added >= n: break
        base += timedelta(days=1)
    return slots

def build_interview_email(candidate_name, role, slots, company_name):
    slot_lines = "\n".join([f"• {s.strftime('%A, %B %d at %I:%M %p')}" for s in slots])
    return f"Dear {candidate_name},\n\nWe loved your profile for the {role} position. We'd like to invite you for an interview.\n\nAvailable slots:\n{slot_lines}\n\nBest regards,\n{company_name} Team"

def send_interview_email(to_email, subject, body):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    if not sender_email or not sender_password:
        return False, "SMTP credentials missing"
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True, "Success"
    except Exception as e:
        return False, str(e)

# ── Page config ──────────────────────────────
st.set_page_config(page_title="TalentScope AI", page_icon="🎯", layout="wide")

# ── Elite UI CSS ─────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

    /* ── Reset & Base ── */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background: #07080d;
        color: #c8d0e0;
    }

    /* ── Hide Streamlit branding ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1300px; }

    /* ── Animated Grid Background ── */
    .grid-bg {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background-image:
            linear-gradient(rgba(99, 102, 241, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99, 102, 241, 0.04) 1px, transparent 1px);
        background-size: 48px 48px;
        pointer-events: none; z-index: 0;
    }

    /* ── Hero Section ── */
    .hero-wrap {
        position: relative; overflow: hidden;
        background: linear-gradient(135deg, #0d0f1a 0%, #111526 50%, #0d1020 100%);
        border: 1px solid rgba(99,102,241,0.18);
        border-radius: 20px;
        padding: 3rem 2.5rem 2.5rem;
        margin-bottom: 2rem;
        text-align: center;
    }
    .hero-wrap::before {
        content: '';
        position: absolute; top: -80px; left: 50%; transform: translateX(-50%);
        width: 600px; height: 300px;
        background: radial-gradient(ellipse at center, rgba(99,102,241,0.15) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-eyebrow {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(99,102,241,0.12);
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 999px;
        padding: 5px 16px;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #a5b4fc;
        margin-bottom: 1.2rem;
    }
    .hero-dot { width: 6px; height: 6px; background: #6366f1; border-radius: 50%; display: inline-block; animation: pulse-dot 2s infinite; }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.7); }
    }
    .hero-title {
        font-family: 'Syne', sans-serif;
        font-size: 3rem;
        font-weight: 800;
        color: #f0f4ff;
        line-height: 1.1;
        letter-spacing: -0.02em;
        margin: 0 0 0.75rem;
    }
    .hero-title em { font-style: normal; color: #818cf8; }
    .hero-sub {
        font-size: 1rem;
        color: #6b7a9e;
        max-width: 500px;
        margin: 0 auto 1.5rem;
        font-weight: 300;
        line-height: 1.7;
    }
    .hero-stats {
        display: flex; justify-content: center; gap: 2.5rem;
        margin-top: 1.5rem; padding-top: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.06);
    }
    .hero-stat-val {
        font-family: 'Syne', sans-serif;
        font-size: 1.6rem; font-weight: 700; color: #e2e8f8;
    }
    .hero-stat-lbl { font-size: 0.75rem; color: #4a5370; margin-top: 2px; letter-spacing: 0.05em; }

    /* ── Tab Styling ── */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 12px;
        padding: 5px;
        gap: 4px;
        margin-bottom: 1.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: #5a6380 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        padding: 10px 22px !important;
        transition: all 0.2s ease !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(99,102,241,0.18) !important;
        color: #a5b4fc !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ── Inputs ── */
    .stTextArea textarea, .stTextInput input {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        color: #d0d9f0 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.9rem !important;
        padding: 14px !important;
        transition: border-color 0.2s ease !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: rgba(99,102,241,0.5) !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.08) !important;
    }
    .stTextArea label, .stTextInput label, .stFileUploader label {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: #5a6380 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
    }

    /* ── File Uploader ── */
    [data-testid="stFileUploader"] > div {
        background: rgba(99,102,241,0.04) !important;
        border: 2px dashed rgba(99,102,241,0.2) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stFileUploader"] > div:hover {
        border-color: rgba(99,102,241,0.45) !important;
        background: rgba(99,102,241,0.07) !important;
    }

    /* ── Primary Button ── */
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5, #6366f1) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: 'Syne', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.04em !important;
        padding: 14px 28px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 24px rgba(99,102,241,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 32px rgba(99,102,241,0.45) !important;
        background: linear-gradient(135deg, #5a51f0, #7173f5) !important;
    }
    .stButton > button:active { transform: translateY(0) !important; }

    /* ── Metric Cards ── */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 1.25rem 1.5rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.75rem !important;
        color: #4a5370 !important;
        letter-spacing: 0.07em !important;
        text-transform: uppercase !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Syne', sans-serif !important;
        font-size: 2rem !important;
        color: #e2e8f8 !important;
        font-weight: 700 !important;
    }

    /* ── Progress Bar ── */
    .stProgress > div > div {
        background: linear-gradient(90deg, #4f46e5, #818cf8) !important;
        border-radius: 999px !important;
    }
    .stProgress > div {
        background: rgba(255,255,255,0.07) !important;
        border-radius: 999px !important;
    }

    /* ── Section Labels ── */
    .section-label {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.72rem;
        font-weight: 500;
        color: #4a5370;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
        margin-top: 1.5rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-label::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(255,255,255,0.06);
    }

    /* ── Candidate Cards ── */
    .cand-card {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 1.1rem 1.4rem;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 1.2rem;
        transition: border-color 0.2s ease, background 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .cand-card:hover {
        border-color: rgba(99,102,241,0.3);
        background: rgba(99,102,241,0.04);
    }
    .cand-card::before {
        content: '';
        position: absolute; left: 0; top: 0; bottom: 0;
        width: 3px;
        border-radius: 0 3px 3px 0;
    }
    .cand-card.match::before { background: #10b981; }
    .cand-card.maybe::before { background: #f59e0b; }
    .cand-card.no::before { background: #e11d48; }

    .score-ring {
        width: 56px; height: 56px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-family: 'Syne', sans-serif;
        font-size: 1rem; font-weight: 700;
        flex-shrink: 0;
    }
    .score-ring.match { background: rgba(16,185,129,0.12); color: #10b981; border: 1.5px solid rgba(16,185,129,0.3); }
    .score-ring.maybe { background: rgba(245,158,11,0.12); color: #f59e0b; border: 1.5px solid rgba(245,158,11,0.3); }
    .score-ring.no    { background: rgba(225,29,72,0.12);  color: #e11d48; border: 1.5px solid rgba(225,29,72,0.3); }

    .cand-name {
        font-family: 'Syne', sans-serif;
        font-size: 1rem; font-weight: 600; color: #e2e8f8;
    }
    .cand-meta { font-size: 0.8rem; color: #4a5370; margin-top: 3px; }

    .status-pill {
        padding: 5px 14px; border-radius: 999px;
        font-size: 0.7rem; font-weight: 600;
        letter-spacing: 0.08em; text-transform: uppercase;
    }
    .pill-match  { background: rgba(16,185,129,0.1); color: #10b981; border: 1px solid rgba(16,185,129,0.2); }
    .pill-maybe  { background: rgba(245,158,11,0.1); color: #f59e0b; border: 1px solid rgba(245,158,11,0.2); }
    .pill-no     { background: rgba(225,29,72,0.1);  color: #e11d48; border: 1px solid rgba(225,29,72,0.2); }

    .invite-pill {
        padding: 4px 10px; border-radius: 999px;
        font-size: 0.68rem; font-weight: 500;
        background: rgba(99,102,241,0.1); color: #818cf8;
        border: 1px solid rgba(99,102,241,0.2);
        margin-left: 6px;
    }

    /* ── Expander Styling ── */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 10px !important;
        color: #6b7a9e !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.05em !important;
        padding: 10px 16px !important;
    }
    .streamlit-expanderHeader:hover { border-color: rgba(99,102,241,0.3) !important; color: #a5b4fc !important; }
    .streamlit-expanderContent {
        background: rgba(255,255,255,0.015) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        padding: 1.5rem !important;
    }

    /* ── AI Summary Box ── */
    .ai-summary {
        background: linear-gradient(135deg, rgba(99,102,241,0.06) 0%, rgba(129,140,248,0.04) 100%);
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        position: relative;
    }
    .ai-label {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.68rem; font-weight: 600;
        letter-spacing: 0.12em; text-transform: uppercase;
        color: #818cf8;
        margin-bottom: 0.6rem;
        display: flex; align-items: center; gap: 6px;
    }
    .ai-label-dot { width: 5px; height: 5px; background: #818cf8; border-radius: 50%; animation: pulse-dot 2s infinite; }
    .ai-summary-text { font-size: 0.9rem; color: #aab4cc; line-height: 1.7; }

    /* ── Tag Chips ── */
    .tag-group { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .tag {
        padding: 4px 11px; border-radius: 6px;
        font-size: 0.72rem; font-weight: 500;
    }
    .tag-strength { background: rgba(16,185,129,0.08); color: #34d399; border: 1px solid rgba(16,185,129,0.15); }
    .tag-risk     { background: rgba(225,29,72,0.07);  color: #fb7185; border: 1px solid rgba(225,29,72,0.15); }

    /* ── Project Cards ── */
    .proj-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 8px;
        transition: border-color 0.2s;
    }
    .proj-card:hover { border-color: rgba(99,102,241,0.25); }
    .proj-title { font-family: 'Syne', sans-serif; font-weight: 600; font-size: 0.9rem; color: #d8e0f0; }
    .proj-score { font-size: 0.75rem; color: #6366f1; font-weight: 600; }
    .proj-desc  { font-size: 0.82rem; color: #5a6380; margin-top: 5px; line-height: 1.6; }

    /* ── Dashboard Header ── */
    .dash-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .dash-title {
        font-family: 'Syne', sans-serif;
        font-size: 1.3rem; font-weight: 700; color: #e2e8f8;
    }
    .dash-sub { font-size: 0.8rem; color: #4a5370; margin-top: 2px; }

    /* ── Empty State ── */
    .empty-state {
        text-align: center; padding: 4rem 2rem;
        border: 1px dashed rgba(255,255,255,0.08);
        border-radius: 16px;
        background: rgba(255,255,255,0.015);
    }
    .empty-icon { font-size: 2.5rem; margin-bottom: 1rem; opacity: 0.4; }
    .empty-text { color: #4a5370; font-size: 0.9rem; }

    /* ── DataFrame ── */
    .dataframe { background: rgba(255,255,255,0.02) !important; border-radius: 10px !important; }

    /* ── Download Button ── */
    .stDownloadButton > button {
        background: rgba(99,102,241,0.1) !important;
        color: #a5b4fc !important;
        border: 1px solid rgba(99,102,241,0.25) !important;
        border-radius: 10px !important;
        font-family: 'Syne', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton > button:hover {
        background: rgba(99,102,241,0.18) !important;
        border-color: rgba(99,102,241,0.45) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.3); border-radius: 999px; }
</style>
""", unsafe_allow_html=True)

# ── Session State ────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []

# ── Visual Helpers ────────────────────────────
def make_skill_bar(report):
    skills = report.get("skill_matches", [])
    if not skills:
        return None
    names = [s["skill_name"] for s in skills[:8]]
    profs = [s.get("proficiency", 0) * 10 for s in skills[:8]]
    
    colors = []
    for p in profs:
        if p >= 75:   colors.append("#10b981")
        elif p >= 50: colors.append("#6366f1")
        else:         colors.append("#f59e0b")
    
    fig = go.Figure(go.Bar(
        x=profs, y=names, orientation='h',
        marker=dict(color=colors, line=dict(width=0)),
        hovertemplate='%{y}: <b>%{x}%</b><extra></extra>'
    ))
    fig.update_layout(
        height=240,
        margin=dict(l=0, r=10, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#5a6380", size=11),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", range=[0,100], showline=False, ticksuffix="%"),
        yaxis=dict(showgrid=False),
        bargap=0.35,
    )
    return fig

def make_radar_chart(report):
    cats = ["Technical", "Communication", "Leadership", "Problem Solving", "Culture Fit"]
    scores = report.get("dimension_scores", [70, 65, 55, 80, 75])
    if len(scores) < 5:
        scores = [70, 65, 55, 80, 75]
    fig = go.Figure(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=cats + [cats[0]],
        fill='toself',
        fillcolor='rgba(99,102,241,0.12)',
        line=dict(color='#6366f1', width=2),
        hovertemplate='%{theta}: <b>%{r}</b><extra></extra>'
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(visible=True, range=[0,100], showticklabels=False, gridcolor='rgba(255,255,255,0.07)', linecolor='rgba(255,255,255,0.07)'),
            angularaxis=dict(tickfont=dict(size=10, color='#5a6380'), linecolor='rgba(255,255,255,0.07)', gridcolor='rgba(255,255,255,0.07)')
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=20, b=20),
        height=200,
        showlegend=False,
    )
    return fig

def score_class(score):
    if score >= 75: return "match"
    if score >= 50: return "maybe"
    return "no"

def status_pill_class(status):
    if status == "MATCH": return "pill-match"
    if status == "MAYBE": return "pill-maybe"
    return "pill-no"

# ── Tabs ─────────────────────────────────────
tab_run, tab_dash, tab_export = st.tabs(["  🚀  Batch Processing  ", "  📊  Intelligence Dashboard  ", "  📋  Export Data  "])

# ══════════════════════════════════════════════
# TAB 1 — BATCH PROCESSING
# ══════════════════════════════════════════════
with tab_run:
    st.markdown("""
    <div class="hero-wrap">
        <div class="hero-eyebrow"><span class="hero-dot"></span> AI-Powered Hiring Intelligence</div>
        <div class="hero-title">Screen Smarter.<br><em>Hire Faster.</em></div>
        <div class="hero-sub">Upload any number of resumes and get deep AI-powered analysis, match scores, and automatic interview scheduling — in seconds.</div>
        <div class="hero-stats">
            <div><div class="hero-stat-val">98%</div><div class="hero-stat-lbl">Accuracy</div></div>
            <div><div class="hero-stat-val">&lt;30s</div><div class="hero-stat-lbl">Per Resume</div></div>
            <div><div class="hero-stat-val">Auto</div><div class="hero-stat-lbl">Scheduling</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown('<div class="section-label">📋 Job Description</div>', unsafe_allow_html=True)
        jd_input = st.text_area(
            "Job Description",
            placeholder="Paste the full job requirements, responsibilities, and qualifications here...",
            height=220,
            key="main_jd_input",
            label_visibility="collapsed"
        )

    with col_right:
        st.markdown('<div class="section-label">📁 Resume Files</div>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Upload Resumes",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="resume_uploader",
            label_visibility="collapsed"
        )
        if uploaded_files:
            st.markdown(f"""
            <div style="margin-top:10px; padding: 10px 14px; background: rgba(16,185,129,0.07);
                border: 1px solid rgba(16,185,129,0.2); border-radius: 8px;
                font-size: 0.82rem; color: #34d399; display: flex; align-items: center; gap: 8px;">
                ✓ &nbsp;<strong>{len(uploaded_files)}</strong> file{"s" if len(uploaded_files)>1 else ""} ready to process
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)

    if st.button("⚡  Run AI Screening", use_container_width=True):
        if not jd_input or not uploaded_files:
            st.warning("⚠️  Please provide both a Job Description and at least one Resume.")
        else:
            temp_dir = tempfile.mkdtemp()
            results_list = []

            prog_container = st.container()
            with prog_container:
                progress_bar = st.progress(0)
                status_text = st.empty()

            for index, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                status_text.markdown(
                    f"<div style='font-size:0.85rem; color:#6366f1; padding: 8px 0;'>"
                    f"⟳ &nbsp;Analyzing <code style='background:rgba(99,102,241,0.1); padding:2px 8px; border-radius:4px;'>{filename}</code>"
                    f"&nbsp; — {index+1} of {len(uploaded_files)}</div>",
                    unsafe_allow_html=True
                )

                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                try:
                    from utils import extract_text_from_file
                    from recruiter_graph import app as rec_app

                    text = extract_text_from_file(file_path)
                    response = rec_app.invoke({"job_description": jd_input, "resume_text": text, "github_handle": ""})
                    report = response["final_evaluation"]

                    invite_status = "Skipped"
                    if report.final_decision == "MATCH" and report.email:
                        slots = generate_interview_slots()
                        email_body = build_interview_email(report.candidate_name, "Software Engineer", slots, "TalentScope AI")
                        success, msg = send_interview_email(report.email, "Interview Invitation", email_body)
                        invite_status = "Sent ✓" if success else f"Failed: {msg}"

                    results_list.append({
                        "Name": report.candidate_name,
                        "Status": report.final_decision,
                        "Match %": report.match_score,
                        "Email": report.email,
                        "Exp": report.years_of_experience,
                        "GitHub": report.github_handle,
                        "Invite": invite_status,
                        "Full Report": report.model_dump()
                    })

                except Exception as e:
                    st.error(f"⚠️  Error processing `{filename}`: {e}")

                progress_bar.progress((index + 1) / len(uploaded_files))

            st.session_state.results = results_list
            shutil.rmtree(temp_dir)
            status_text.empty()
            progress_bar.empty()

            matched = sum(1 for x in results_list if x["Status"] == "MATCH")
            st.markdown(f"""
            <div style="padding: 16px 20px; background: rgba(16,185,129,0.07);
                border: 1px solid rgba(16,185,129,0.2); border-radius: 12px; margin-top: 12px;
                display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.4rem;">✅</span>
                <div>
                    <div style="font-family:'Syne',sans-serif; font-weight:600; color:#34d399;">
                        Processed {len(results_list)} resumes
                    </div>
                    <div style="font-size:0.8rem; color:#4a5370; margin-top:2px;">
                        {matched} strong match{"es" if matched != 1 else ""} found · Switch to the Dashboard tab to review
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# TAB 2 — INTELLIGENCE DASHBOARD
# ══════════════════════════════════════════════
with tab_dash:
    if not st.session_state.results:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">🎯</div>
            <div style="font-family:'Syne',sans-serif; font-size:1.1rem; color:#3a4060; font-weight:600; margin-bottom:8px;">No Data Yet</div>
            <div class="empty-text">Run batch processing first to see the intelligence dashboard.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        res = st.session_state.results
        matched   = sum(1 for x in res if x["Status"] == "MATCH")
        maybe     = sum(1 for x in res if x["Status"] == "MAYBE")
        avg_score = int(sum(x["Match %"] for x in res) / len(res))
        invited   = sum(1 for x in res if x.get("Invite") == "Sent ✓")

        st.markdown("""
        <div class="dash-header">
            <div>
                <div class="dash-title">Candidate Intelligence</div>
                <div class="dash-sub">Ranked by AI match score · Click any candidate to expand full report</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Screened", len(res))
        m2.metric("Strong Matches", matched)
        m3.metric("Avg Match Score", f"{avg_score}%")
        m4.metric("Invites Sent", invited)

        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)

        # Funnel overview
        col_donut, col_list = st.columns([1, 2], gap="large")

        with col_donut:
            st.markdown('<div class="section-label">📊 Pipeline Breakdown</div>', unsafe_allow_html=True)
            no_match = len(res) - matched - maybe
            fig_pie = go.Figure(go.Pie(
                labels=["Match", "Maybe", "No Match"],
                values=[matched, maybe, no_match],
                hole=0.65,
                marker=dict(colors=["#10b981","#f59e0b","#e11d48"], line=dict(width=0)),
                textinfo='none',
                hovertemplate='%{label}: <b>%{value}</b><extra></extra>'
            ))
            fig_pie.add_annotation(
                text=f"<b>{len(res)}</b><br><span style='font-size:10px'>Total</span>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=18, color="#e2e8f8", family="Syne")
            )
            fig_pie.update_layout(
                height=200,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
                legend=dict(
                    font=dict(size=11, color="#5a6380", family="DM Sans"),
                    bgcolor="rgba(0,0,0,0)",
                    orientation="v",
                    x=0.85, y=0.5
                )
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="pie_chart")

        with col_list:
            st.markdown('<div class="section-label">🏆 Top Candidates</div>', unsafe_allow_html=True)
            top3 = sorted(res, key=lambda x: x["Match %"], reverse=True)[:3]
            for i, c in enumerate(top3):
                medal = ["🥇","🥈","🥉"][i]
                sc = score_class(c['Match %'])
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:12px; padding: 10px 0;
                    border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1.2rem;">{medal}</span>
                    <div class="score-ring {sc}">{c['Match %']}%</div>
                    <div style="flex:1;">
                        <div class="cand-name">{c['Name']}</div>
                        <div class="cand-meta">{c['Exp']} experience · {c['Email']}</div>
                    </div>
                    <span class="status-pill {status_pill_class(c['Status'])}">{c['Status']}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">📋 All Candidates</div>', unsafe_allow_html=True)

        for idx, cand in enumerate(sorted(res, key=lambda x: x["Match %"], reverse=True)):
            sc       = score_class(cand["Match %"])
            sp       = status_pill_class(cand["Status"])
            name     = cand.get("Name") or "Unknown"
            email    = cand.get("Email") or "—"
            exp      = cand.get("Exp") or "—"
            score    = cand.get("Match %", 0)
            status   = cand.get("Status", "—")
            github   = cand.get("GitHub") or ""
            invited  = cand.get("Invite") == "Sent ✓"

            import html as _html
            invite_badge = '<span class="invite-pill">&#9993; Invited</span>' if invited else ""
            gh_clean = github if github and github not in ("NOT_FOUND", "", None) else ""
            github_badge = (f'<span style="font-size:0.7rem;color:#4a5370;">&#8981; {_html.escape(gh_clean)}</span>') if gh_clean else ""

            card_html = (
                f'<div class="cand-card {sc}">' +
                f'<div class="score-ring {sc}">{score}%</div>' +
                f'<div style="flex:1;min-width:0;overflow:hidden;">' +
                f'<div class="cand-name">{_html.escape(name)}</div>' +
                f'<div class="cand-meta">{_html.escape(email)} &nbsp;&middot;&nbsp; {_html.escape(str(exp))} exp {invite_badge}</div>' +
                '</div>' +
                '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px;flex-shrink:0;">' +
                f'<span class="status-pill {sp}">{status}</span>' +
                github_badge +
                '</div></div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

            with st.expander(f"⟶  View Full Intelligence Report — {name}", expanded=False):
                report = cand["Full Report"]

                # ── AI Summary ──────────────────────────────────────────
                import html as _html, re as _re

                raw_summary = (report.get("github_summary") or "").strip()

                # Detect raw GitHub repo dump (contains "REPO: ... LANG: ... STARS:")
                if raw_summary and _re.search(r'REPO\s*:', raw_summary):
                    repo_entries = _re.split(r'(?=REPO\s*:)', raw_summary)
                    repo_cards_html = ""
                    for entry in repo_entries:
                        entry = entry.strip()
                        if not entry:
                            continue
                        def _get(pattern, text, default=""):
                            m = _re.search(pattern, text)
                            return m.group(1).strip() if m else default
                        repo  = _html.escape(_get(r'REPO\s*:\s*([^|]+)', entry))
                        lang  = _get(r'LANG\s*:\s*([^|]+)', entry)
                        stars = _get(r'STARS\s*:\s*([^|]+)', entry, "0")
                        desc  = _html.escape(_get(r'DESC\s*:\s*(.+?)(?=REPO|$)', entry, "No description")[:120])
                        lang  = _html.escape(lang) if lang and lang.lower() not in ("unknown", "") else ""
                        lang_badge = (f'<span style="background:rgba(99,102,241,0.15);color:#818cf8;padding:1px 8px;border-radius:4px;font-size:0.68rem;">{lang}</span>') if lang else ""
                        repo_cards_html += (
                            f'<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                            f'<span style="color:#4a5370;font-size:0.85rem;margin-top:1px;">⌥</span>'
                            f'<div style="flex:1;min-width:0;">'
                            f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">'
                            f'<span style="font-weight:600;font-size:0.85rem;color:#d0d9f0;">{repo}</span>'
                            f'{lang_badge}'
                            f'<span style="font-size:0.7rem;color:#4a5370;">&#9733; {stars}</span>'
                            f'</div>'
                            f'<div style="font-size:0.78rem;color:#5a6380;margin-top:3px;line-height:1.5;">{desc}</div>'
                            f'</div></div>'
                        )
                    summary_text = (
                        '<div style="margin-bottom:0.5rem;font-size:0.75rem;color:#4a5370;letter-spacing:0.08em;text-transform:uppercase;">GitHub Repositories</div>'
                        + repo_cards_html
                    )
                elif raw_summary:
                    summary_text = _html.escape(raw_summary)
                else:
                    summary_text = "No AI summary was generated for this candidate."

                # Decide tone based on status
                if status == "MATCH":
                    summary_icon = "✦"
                    summary_accent = "#10b981"
                    summary_bg = "rgba(16,185,129,0.05)"
                    summary_border = "rgba(16,185,129,0.2)"
                    verdict_label = "Strong Hire"
                    verdict_color = "#10b981"
                elif status == "MAYBE":
                    summary_icon = "◈"
                    summary_accent = "#f59e0b"
                    summary_bg = "rgba(245,158,11,0.05)"
                    summary_border = "rgba(245,158,11,0.2)"
                    verdict_label = "Consider Further"
                    verdict_color = "#f59e0b"
                else:
                    summary_icon = "✕"
                    summary_accent = "#e11d48"
                    summary_bg = "rgba(225,29,72,0.05)"
                    summary_border = "rgba(225,29,72,0.15)"
                    verdict_label = "Not Recommended"
                    verdict_color = "#e11d48"

                # NOTE: No HTML comments inside the string — Streamlit's markdown parser breaks on <!-- -->
                summary_html = (
                    f'<div style="background:{summary_bg}; border:1px solid {summary_border};'
                    f'border-radius:14px; padding:1.4rem 1.6rem; margin-bottom:1.5rem;">'

                    f'<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.9rem;">'
                    f'<span style="font-size:0.7rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase;'
                    f'color:{summary_accent}; font-family:DM Sans,sans-serif;">'
                    f'<span style="width:5px;height:5px;background:{summary_accent};border-radius:50%;'
                    f'display:inline-block;margin-right:5px;"></span>'
                    f'AI Executive Summary</span>'
                    f'<span style="padding:3px 12px; border-radius:999px; font-size:0.68rem; font-weight:700;'
                    f'letter-spacing:0.07em; text-transform:uppercase; color:{verdict_color};'
                    f'background:{summary_accent}22; border:1px solid {summary_accent}44;">'
                    f'{summary_icon} {verdict_label}</span>'
                    f'</div>'

                    f'<div style="font-size:0.9rem; color:#b0bcd4; line-height:1.8; font-family:DM Sans,sans-serif;'
                    f'font-weight:300; letter-spacing:0.01em;">{summary_text}</div>'

                    f'<div style="margin-top:1.1rem; padding-top:1rem; border-top:1px solid rgba(255,255,255,0.06);">'
                    f'<div style="display:flex; justify-content:space-between; margin-bottom:5px;">'
                    f'<span style="font-size:0.72rem; color:#4a5370; letter-spacing:0.06em; text-transform:uppercase;">Overall Match</span>'
                    f'<span style="font-size:0.75rem; font-weight:700; color:{summary_accent}; font-family:Syne,sans-serif;">{score}%</span>'
                    f'</div>'
                    f'<div style="height:5px; background:rgba(255,255,255,0.06); border-radius:999px; overflow:hidden;">'
                    f'<div style="height:100%; width:{score}%; background:linear-gradient(90deg,{summary_accent}99,{summary_accent}); border-radius:999px;"></div>'
                    f'</div></div>'
                    f'</div>'
                )
                st.markdown(summary_html, unsafe_allow_html=True)

                # Charts row
                ch1, ch2 = st.columns(2, gap="medium")
                with ch1:
                    st.markdown('<div style="font-size:0.75rem; color:#4a5370; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">Skill Proficiency</div>', unsafe_allow_html=True)
                    fig_bar = make_skill_bar(report)
                    if fig_bar:
                        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{idx}")
                with ch2:
                    st.markdown('<div style="font-size:0.75rem; color:#4a5370; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">Competency Radar</div>', unsafe_allow_html=True)
                    st.plotly_chart(make_radar_chart(report), use_container_width=True, key=f"radar_{idx}")

                # Strengths & Risks
                col_s, col_r = st.columns(2, gap="medium")
                with col_s:
                    st.markdown('<div style="font-size:0.75rem; color:#4a5370; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">✅ Strengths</div>', unsafe_allow_html=True)
                    strengths = report.get("strengths", [])
                    if strengths:
                        tags = "".join([f'<span class="tag tag-strength">{s}</span>' for s in strengths])
                        st.markdown(f'<div class="tag-group">{tags}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="color:#3a4060; font-size:0.85rem;">No data</div>', unsafe_allow_html=True)

                with col_r:
                    st.markdown('<div style="font-size:0.75rem; color:#4a5370; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">⚠️ Risk Flags</div>', unsafe_allow_html=True)
                    risks = report.get("red_flags", [])
                    if risks:
                        tags = "".join([f'<span class="tag tag-risk">{r}</span>' for r in risks])
                        st.markdown(f'<div class="tag-group">{tags}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="color:#3a4060; font-size:0.85rem;">No flags</div>', unsafe_allow_html=True)

                st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)

                # Projects
                projects = report.get("project_highlights", [])
                if projects:
                    st.markdown('<div style="font-size:0.75rem; color:#4a5370; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:10px;">🚀 Project Highlights</div>', unsafe_allow_html=True)
                    for p in projects:
                        st.markdown(f"""
                        <div class="proj-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span class="proj-title">{p['project_name']}</span>
                                <span class="proj-score">Relevance: {p['relevance_score']}%</span>
                            </div>
                            <div class="proj-desc">{p['description']}</div>
                        </div>
                        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# TAB 3 — EXPORT
# ══════════════════════════════════════════════
with tab_export:
    if not st.session_state.results:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">📋</div>
            <div style="font-family:'Syne',sans-serif; font-size:1.1rem; color:#3a4060; font-weight:600; margin-bottom:8px;">Nothing to Export</div>
            <div class="empty-text">Process some resumes first to generate export data.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        res = st.session_state.results
        st.markdown("""
        <div style="margin-bottom: 1.5rem;">
            <div style="font-family:'Syne',sans-serif; font-size:1.2rem; font-weight:700; color:#e2e8f8;">Export Report</div>
            <div style="font-size:0.8rem; color:#4a5370; margin-top:4px;">All candidate data ready for download</div>
        </div>
        """, unsafe_allow_html=True)

        df = pd.DataFrame(res).drop(columns=["Full Report"])

        st.dataframe(
            df.style.background_gradient(subset=["Match %"], cmap="Blues"),
            use_container_width=True,
            height=400
        )

        col_dl1, col_dl2, _ = st.columns([1, 1, 2])
        with col_dl1:
            st.download_button(
                "📥  Download CSV",
                df.to_csv(index=False),
                "talentscope_results.csv",
                mime="text/csv",
                key="download_csv",
                use_container_width=True
            )
        with col_dl2:
            st.download_button(
                "📥  Download JSON",
                json.dumps([{k: v for k, v in r.items() if k != "Full Report"} for r in res], indent=2),
                "talentscope_results.json",
                mime="application/json",
                key="download_json",
                use_container_width=True
            )