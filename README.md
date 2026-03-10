# 🎯 TalentScope AI: Intelligent Recruitment Pipeline

AI Recruitment system is a sophisticated, agentic recruitment tool designed to bridge the gap between thousands of resumes and the perfect technical hire. By combining LLM-powered resume screening with real-world GitHub data auditing, it provides a 360-degree view of a candidate's technical prowess.



##  Key Features

* **Multi-Agent Workflow:** Built with **LangGraph**, the system uses specialized agents for Job Description architecture, Resume Screening, and GitHub Auditing.
* **GitHub Technical Audit:** Automatically extracts GitHub handles from resumes and fetches real-time data on repositories, languages, and contribution quality.
* **Automated Outreach:** Instantly generates and sends personalized interview invitations via SMTP (Gmail supported) for high-scoring matches.
* **Dynamic Dashboard:** High-fidelity Streamlit UI featuring:
    * Match Score Distributions (Plotly).
    * Skill Radar Charts.
    * Side-by-Side Candidate Comparison.
    * CSV Export for ATS integration.
* **Deterministic Caching:** Saves API costs by caching results—identical Resume + JD combinations won't be re-processed.

##  Tech Stack

- **Framework:** [LangGraph](https://github.com/langchain-ai/langgraph) / [LangChain](https://github.com/langchain-ai/langchain)
- **LLM:** [Groq](https://groq.com/) (Llama-3 models)
- **UI:** [Streamlit](https://streamlit.io/)
- **Data Viz:** [Plotly](https://plotly.com/)
- **Parser:** PyPDF2, python-docx
- **API:** PyGithub (GitHub REST API)

## 📋 Prerequisites

- Python 3.9+
- A Groq API Key
- A GitHub Personal Access Token (for extended API rate limits)
- An App Password (if using Gmail SMTP)

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aliasif767/AI-Recruitment-system.git
   cd AI Recruitor
