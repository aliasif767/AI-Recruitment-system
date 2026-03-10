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
# Interview Scheduling Helpers
# ─────────────────────────────────────────────
def generate_interview_slots(n=3):
    """Generate n available interview slots starting from next business day."""
    slots = []
    base = datetime.now() + timedelta(days=2)
    added = 0
    while added < n:
        if base.weekday() < 5: 
            for hour in [10, 14, 16]:
                slots.append(base.replace(hour=hour, minute=0, second=0, microsecond=0))
                added += 1
                if added >= n:
                    break
        base += timedelta(days=1)
    return slots

def build_interview_email(candidate_name: str, candidate_email: str,
                           role: str, slots: list, company_name: str,
                           sender_name: str) -> str:
    slot_lines = "\n".join(
        f"  • Option {i+1}: {s.strftime('%A, %B %d %Y at %I:%M %p')}"
        for i, s in enumerate(slots)
    )
    return f"""Subject: Interview Invitation — {role} at {company_name}

Dear {candidate_name},

Thank you for applying for the {role} position at {company_name}.

After carefully reviewing your profile, we are pleased to invite you for an interview. Your background and skills are a strong match for what we are looking for.

Please reply to this email confirming your preferred time from the options below:

{slot_lines}

The interview will be conducted virtually and is expected to last approximately 45–60 minutes.
Please feel free to reach out if you have any questions or need to suggest an alternative time.

We look forward to speaking with you!

Warm regards,
{sender_name}
{company_name} — Talent Acquisition Team"""

def send_interview_email(to_email: str, subject: str, body: str,
                          smtp_host: str, smtp_port: int,
                          sender_email: str, sender_password: str) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls() # Required for Gmail 587
        
        with server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True, "Email sent successfully!"
    except Exception as e:
        return False, str(e)

# ── Page config ──────────────────────────────
st.set_page_config(
    page_title="TalentScope AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Professional SaaS UI CSS ─────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: #0f111a; color: #cbd5e1; }
.hero { background: linear-gradient(180deg, #161b22 0%, #0f111a 100%); border: 1px solid #1e293b; border-radius: 12px; padding: 2rem; margin-bottom: 2rem; }
.hero-title { font-size: 2.25rem; font-weight: 700; color: #f8fafc; }
.hero-title span { color: #3b82f6; }
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
.kpi-tile { background: #161b22; border: 1px solid #1e293b; border-radius: 10px; padding: 1.25rem; text-align: center; }
.kpi-num { font-size: 2rem; font-weight: 700; color: #f8fafc; }
.cand-card { background: #161b22; border: 1px solid #1e293b; border-radius: 10px; padding: 1.25rem; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 1.5rem; transition: 0.2s; }
.cand-card:hover { border-color: #3b82f6; }
.pill { padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.pill-green { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.pill-amber { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.pill-red { background: rgba(225, 29, 72, 0.1); color: #e11d48; }
.code-box { background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px; padding: 1rem; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #94a3b8; white-space: pre-wrap; height: 150px; overflow-y: auto; }
</style>
""", unsafe_allow_html=True)

# ── Session State ────────────────────────────
if "results" not in st.session_state: st.session_state.results = []
if "selected" not in st.session_state: st.session_state.selected = None

COLORS = {"MATCH": "#10b981", "MAYBE": "#f59e0b", "NO_MATCH": "#e11d48", "ERROR": "#64748b"}
PLOTLY_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"))

# ── Chart Helpers ─────────────────────────────
def make_overview_scatter(results):
    if not results: return None
    names = [r.get("Name", "?")[:12] for r in results]
    scores = [int(r.get("Match %", 0)) for r in results]
    c = [COLORS.get(str(r.get("Status")).upper(), COLORS["ERROR"]) for r in results]
    fig = go.Figure(go.Bar(x=names, y=scores, marker=dict(color=c, line=dict(width=0)), text=scores, textposition='outside'))
    fig.update_layout(**PLOTLY_LAYOUT, height=300, yaxis=dict(range=[0, 115]))
    return fig

def make_skill_bar(report):
    skills = report.get("skill_matches", [])
    if not skills: return None
    names = [s["skill_name"] for s in skills[:10]]
    profs = [s.get("proficiency", 0) * 10 for s in skills[:10]]
    fig = go.Figure(go.Bar(x=profs, y=names, orientation='h', marker=dict(color="#3b82f6")))
    fig.update_layout(**PLOTLY_LAYOUT, height=300)
    return fig

def make_radar(report):
    scores = report.get("evaluation_scores", [])
    if not scores: return None
    cats = [s["category"] for s in scores]
    vals = [s["score"] for s in scores]
    fig = go.Figure(go.Scatterpolar(r=vals + [vals[0]], theta=cats + [cats[0]], fill='toself', line=dict(color="#3b82f6")))
    fig.update_layout(**PLOTLY_LAYOUT, polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=320)
    return fig

# ── Sidebar ──────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:#f8fafc;'>🎯 TalentScope</h2>", unsafe_allow_html=True)
    st.info("AI Recruitment Intelligence")
    

# ── Tabs ─────────────────────────────────────
tab_run, tab_dash, tab_compare, tab_export = st.tabs(["🚀 Run Pipeline", "📊 Analytics", "⚖️ Compare", "📋 Export"])

with tab_run:
    st.markdown('<div class="hero"><div class="hero-title">Find the <span>Right Engineer</span> Faster.</div></div>', unsafe_allow_html=True)
    col_jd, col_up = st.columns(2)
    with col_jd:
        st.markdown("**📝 Job Description**")
        job_description = st.text_area("jd_input", placeholder="Paste requirements...", height=240, label_visibility="collapsed")
    with col_up:
        st.markdown("**📎 Upload Resumes**")
        uploaded = st.file_uploader("files", type=["pdf","docx","txt"], accept_multiple_files=True, label_visibility="collapsed")

    if st.button("▶ Start Screening Pipeline", use_container_width=True) and uploaded and job_description:
        tmp = tempfile.mkdtemp()
        logs, results = [], []
        prog = st.progress(0)
        status_ph = st.empty()
        log_ph = st.empty()
        
        for i, uf in enumerate(uploaded, 1):
            path = os.path.join(tmp, uf.name)
            with open(path, "wb") as f: f.write(uf.getbuffer())
            
            logs.append(f"▶ Analyzing {uf.name}...")
            log_ph.markdown(f'<div class="code-box">{"".join(logs[-5:])}</div>', unsafe_allow_html=True)
            
            try:
                from utils import extract_text_from_file
                from recruiter_graph import app as rec_app
                
                text = extract_text_from_file(path)
                # Pass empty github_handle to trigger text-based search in your graph
                response = rec_app.invoke({"job_description": job_description, "resume_text": text, "github_handle": ""})
                
                # Report data
                r = response["final_evaluation"]
                
                _invite_status = "not_sent"
                # --- CORRECTED EMAIL LOGIC ---
                if r.final_decision == "MATCH" and r.email:
                    _sender = os.getenv("EMAIL_USER")
                    _pass = os.getenv("EMAIL_PASSWORD")
                    if _sender and _pass:
                        slots = generate_interview_slots()
                        email_body = build_interview_email(r.candidate_name, r.email, "Software Engineer", slots, "TalentScope AI", "Recruitment Team")
                        
                        success, err_msg = send_interview_email(
                            r.email, f"Interview Invitation - {r.candidate_name}", email_body,
                            os.getenv("SMTP_SERVER", "smtp.gmail.com"),
                            int(os.getenv("SMTP_PORT", 587)),
                            _sender, _pass
                        )
                        if success:
                            _invite_status = "sent"
                            logs.append(f"  └─ 📨 Email SENT to {r.email}")
                        else:
                            _invite_status = f"failed: {err_msg}"
                            logs.append(f"  └─ ❌ Email FAILED: {err_msg}")

                results.append({
                    "Name": r.candidate_name, "Status": r.final_decision, "Match %": r.match_score,
                    "Email": r.email, "Phone": r.phone_no, "University": r.university_name,
                    "GitHub": r.github_handle, "Years Experience": r.years_of_experience,
                    "Invite Status": _invite_status, "Full Report": r.model_dump()
                })
                logs.append(f"  ✅ {r.candidate_name}: {r.match_score}%")
            except Exception as e:
                logs.append(f"  ❌ Error processing {uf.name}: {str(e)}")
            
            prog.progress(i / len(uploaded))
            log_ph.markdown(f'<div class="code-box">{"".join(logs[-5:])}</div>', unsafe_allow_html=True)
        
        st.session_state.results = results
        shutil.rmtree(tmp)
        st.success("Pipeline Complete!")

with tab_dash:
    if st.session_state.results:
        res = st.session_state.results
        
        # KPI Row
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Screened", len(res))
        k2.metric("Strong Matches", sum(1 for x in res if x['Status'] == 'MATCH'))
        k3.metric("Avg Match %", f"{int(sum(x['Match %'] for x in res)/len(res))}%")
        k4.metric("Emails Sent", sum(1 for x in res if x['Invite Status'] == 'sent'))

        st.plotly_chart(make_overview_scatter(res), use_container_width=True)
        
        for cand in sorted(res, key=lambda x: x['Match %'], reverse=True):
            status = cand['Status']
            p_class = "pill-green" if status=="MATCH" else "pill-amber" if status=="MAYBE" else "pill-red"
            
            st.markdown(f"""
            <div class="cand-card">
                <div style="font-weight:700; font-size:1.5rem; color:#3b82f6; width:60px;">{cand['Match %']}%</div>
                <div style="flex:1;">
                    <div style="font-weight:600; color:#f8fafc;">{cand['Name']}</div>
                    <div style="font-size:0.85rem; color:#64748b;">{cand['Email']} | Exp: {cand['Years Experience']} | Invite: {cand['Invite Status']}</div>
                </div>
                <div class="pill {p_class}">{status}</div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("View Full Analysis"):
                report = cand["Full Report"]
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(make_skill_bar(report), use_container_width=True)
                with c2:
                    st.plotly_chart(make_radar(report), use_container_width=True)
                st.write("**Strengths:**", ", ".join(report.get("strengths", [])))
                st.write("**Red Flags:**", ", ".join(report.get("red_flags", [])))
    else:
        st.info("Run the pipeline to see results.")

with tab_compare:
    if st.session_state.results:
        names = [r["Name"] for r in st.session_state.results]
        selected_names = st.multiselect("Select candidates to compare", names)
        if selected_names:
            comparison_data = [r for r in st.session_state.results if r["Name"] in selected_names]
            st.table(pd.DataFrame(comparison_data).drop(columns=["Full Report"]))
    else:
        st.info("Run pipeline first.")

with tab_export:
    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results).drop(columns=["Full Report"])
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Download Results CSV", df.to_csv(index=False), "recruitment_results.csv", "text/csv")
    else:
        st.info("No data to export.")