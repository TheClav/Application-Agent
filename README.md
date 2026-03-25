# Application Agent

An AI-powered job application agent that ingests a job description and automatically generates a tailored resume and cover letter — including ATS scoring, fabrication detection, and iterative self-revision loops.

---

## What it does

1. **Hard filter** — Extracts explicit dealbreakers from the JD (minimum years, degrees, certifications, visa requirements, GPA minimums) and checks each against the candidate profile. Skips the role immediately if any blocker is triggered.
2. **ATS pre-score** — Scores the candidate's raw profile against the JD to establish a baseline and identify skill gaps.
3. **Semantic search** — Queries the candidate's experience bank (PostgreSQL + pgvector) using cosine similarity to surface the most relevant experiences for the role.
4. **Context distillation** — Compresses search results into a structured fit analysis: strong matches, weak matches, and hard gaps.
5. **Strategic planning** — An Opus-powered planner produces a concrete application strategy: what to lead with, how to handle gaps, resume angle, and cover letter hook.
6. **Resume generation + evaluation loop** — Generates a tailored resume JSON, evaluates it against an 8-criterion rubric and ATS target, then revises up to N times. Fabrication is caught and corrected via retry injection, not hard stop.
7. **Cover letter generation + evaluation loop** — Same generate → evaluate → revise pattern. Hard cap at 350 words. Duration claims and em dashes are explicitly prohibited.
8. **PDF rendering** — Renders final resume and cover letter to PDF via Jinja2 + WeasyPrint.
9. **Application log** — Persists every run to PostgreSQL: scores, iteration counts, strategy, fabrication flags, and the full output JSON.

---

## Tech stack

| Layer | Technology |
|---|---|
| Web UI | Flask (SSE-style polling for live logs) |
| LLM — generation | Claude Haiku |
| LLM — evaluation / judge | Claude Sonnet |
| LLM — strategic planning | Claude Opus |
| Embeddings | VoyageAI `voyage-large-2` (1536-dim) |
| Vector search | pgvector (cosine similarity) |
| Database | PostgreSQL |
| PDF rendering | Jinja2 + WeasyPrint |

---

## Project structure

```
app.py                        # Flask web server and job runner
job_agent/
  agent/
    orchestrator.py           # 9-step pipeline orchestrator
  tools/
    hard_filter.py            # Dealbreaker extraction and check
    distill_context.py        # Fit analysis distillation
    generate_plan.py          # Opus strategic planner
    generate_resume.py        # Resume generator
    evaluate_resume.py        # Resume rubric evaluator + ATS re-scorer
    generate_cover_letter.py  # Cover letter generator
    evaluate_cover_letter.py  # Cover letter rubric evaluator
    search_profile.py         # pgvector semantic search
    get_candidate_meta.py     # Fetch candidate profile from DB
    get_soft_signals.py       # Fetch candidate soft signals from DB
  db/
    schema.sql                # PostgreSQL schema
    connection.py             # DB connection pool
    embeddings.py             # VoyageAI embedding + pgvector search
    seed.py                   # Seed candidate data
  templates/
    resume.html               # Jinja2 resume template
    cover_letter.html         # Jinja2 cover letter template
  rendering.py                # PDF rendering via WeasyPrint
  logger.py                   # Per-run logger setup
requirements.txt
```

---

## Database schema

**`candidate_meta`** — Name, location, remote preference, target title, salary range, visa status, GPA, education, languages.

**`experience_entries`** — Individual experience records: employer, title, dates, story, outcome, skills, themes, seniority, and a 1536-dim pgvector embedding.

**`soft_signals`** — Preferred problem types, culture, work style, what to avoid, what excites the candidate.

**`application_log`** — Full audit trail per run: JD, ATS scores, resume/CL iterations, fabrication flag, strategy, output JSON, PDF paths.

---

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL with the `pgvector` extension installed
- API keys: Anthropic and VoyageAI

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```env
ANTHROPIC_API_KEY=...
VOYAGE_API_KEY=...
DATABASE_URL=postgresql://user@localhost:5432/job_agent

# Model selection
GENERATION_MODEL=claude-haiku-4-5-20251001
JUDGE_MODEL=claude-sonnet-4-6
PLAN_MODEL=claude-opus-4-6

# Pipeline thresholds
ATS_PASS_THRESHOLD=60
ATS_RESUME_TARGET=80
RESUME_SCORE_GATE=70
MAX_REVISION_LOOPS=5
ATS_MIN_DELTA=2
ATS_CEILING=95
```

### Initialize the database

```bash
psql -d job_agent -f job_agent/db/schema.sql
python job_agent/db/seed.py
```

### Run

```bash
python app.py
```

Open `http://localhost:8080` in your browser. Paste a job description, select output mode (resume / cover letter / both), and submit. Live pipeline logs stream to the UI as the agent runs.

---

## How the revision loops work

Both the resume and cover letter go through a **generate → evaluate → revise** cycle:

- The generator produces a draft.
- The evaluator scores it against a rubric and flags specific failures.
- If it fails, the failures become `revision_instructions` injected into the next generation call.
- This repeats up to `MAX_REVISION_LOOPS` times.
- **Fabrication** (invented skills, duration claims not derivable from resume dates) is caught by the evaluator and corrected via targeted retry instructions — not a hard pipeline stop.

---

## Model strategy

| Task | Model | Why |
|---|---|---|
| Resume / CL generation | Haiku | Fast, cheap, follows structured instructions well |
| ATS scoring, rubric evaluation, fabrication detection | Sonnet | Stronger reasoning for nuanced judgment calls |
| Application strategy planning | Opus | Complex multi-constraint reasoning over fit analysis |

You can swap any model via `.env` without touching code.
