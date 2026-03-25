"""
Seed script — populate candidate_meta, soft_signals, and experience_entries.
Run with: python -m job_agent.db.seed
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from job_agent.db.connection import get_conn, get_cursor
from job_agent.db.embeddings import embed_and_store

# ---------------------------------------------------------------------------
# Candidate meta
# ---------------------------------------------------------------------------
CANDIDATE = {
    "name": "Calvin DeBellis",
    "location": "Open to relocation anywhere in the US — currently Madison, WI",
    "remote_pref": "hybrid",
    "target_title": "Software Engineer / AI Engineer / Data Scientist",
    "salary_min": 80000,
    "salary_target": 130000,
    "years_experience": 2,
    "visa_status": "citizen",
    "education": {
        "degree": "B.S.",
        "field": "Computer Science & Data Science",
        "institution": "University of Wisconsin–Madison",
    },
    "languages": ["English"],
}

# ---------------------------------------------------------------------------
# Soft signals
# ---------------------------------------------------------------------------
SOFT_SIGNALS = {
    "preferred_problems": (
        "AI agents and LLM infrastructure, data engineering and pipeline work, "
        "developer tooling, computer vision and ML systems, building things from 0 to 1."
    ),
    "preferred_culture": (
        "Small teams with high autonomy. Startup or early-stage environment where I can own "
        "projects end-to-end. Curious, technically sharp people who ship fast and care about quality."
    ),
    "avoid": (
        "Heavy process and bureaucracy. Large orgs where I'd be siloed into a narrow slice of work "
        "with little ownership or visibility into the broader system."
    ),
    "excited_about": (
        "Companies building in the LLM and AI agent space. Data infrastructure that unlocks new "
        "capabilities. Roles where I can apply ML and software engineering together. "
        "International or adventure-friendly culture is a bonus — I've lived in Australia, "
        "Thailand, and Czechia and love new environments."
    ),
    "work_style": (
        "Autonomous and ownership-oriented. I take initiative, ask questions to understand the "
        "full picture, and communicate progress clearly. I prefer deep work with real ownership "
        "over being handed narrow tickets."
    ),
}

# ---------------------------------------------------------------------------
# Experience entries — one atomic accomplishment per row
# ---------------------------------------------------------------------------
EXPERIENCES = [
    {
        "employer": "Ataccama",
        "title": "AI Intern",
        "start_date": "2025-05-01",
        "end_date": "2025-08-31",
        "story": (
            "Researched and applied LLM fine-tuning strategies in Azure AI Foundry to reduce the size "
            "of the AI agent's system prompt. The prompt had grown to over 11k tokens, adding cost and "
            "latency to every inference call. I identified that many prompt instructions could be baked "
            "into model behavior through fine-tuning instead. I owned the research, experimentation, "
            "and data pipeline end-to-end — scripting data extraction from testing environments, "
            "filtering responses, converting to JSONL, and running fine-tuning jobs."
        ),
        "outcome": "Identified path to ~50% reduction in system-prompt token usage (11k → <6k)",
        "skills": ["Python", "LLM fine-tuning", "Azure AI Foundry", "Azure", "JSONL", "data pipelines"],
        "themes": ["AI", "LLMs", "optimization", "ownership"],
        "seniority": "owned",
    },
    {
        "employer": "Ataccama",
        "title": "AI Intern",
        "start_date": "2025-05-01",
        "end_date": "2025-08-31",
        "story": (
            "Expanded and enhanced the internal agent evaluation framework to support comparison across "
            "multiple fine-tuned model variants. The existing framework had limited question diversity, "
            "which made it hard to distinguish real performance differences from noise. I increased the "
            "number of unique evaluation questions by 140% and used prompt mutation to vary phrasing "
            "and difficulty. Cut evaluation variance in half, giving the team a more reliable signal "
            "when iterating on models."
        ),
        "outcome": "Cut evaluation variance in half; 140% increase in unique evaluation questions",
        "skills": ["Python", "LLMs", "evaluation frameworks", "Pandas", "prompt engineering"],
        "themes": ["AI", "evaluation", "infrastructure", "reliability"],
        "seniority": "owned",
    },
    {
        "employer": "Ataccama",
        "title": "AI Intern",
        "start_date": "2025-05-01",
        "end_date": "2025-08-31",
        "story": (
            "Built data visualizations in Python using Pandas, Plotly, and Matplotlib to communicate "
            "model performance findings to the engineering team and broader company. Presented results "
            "at a company all-hands meeting. Also worked with GitLab CI/CD, Docker, and Kubernetes "
            "to support the existing deployment pipeline for fine-tuned models and S3 for artifact storage."
        ),
        "outcome": "Presented findings at company all-hands; supported CI/CD pipeline for model deploys",
        "skills": ["Python", "Pandas", "Plotly", "Matplotlib", "Docker", "Kubernetes", "GitLab CI/CD", "Amazon S3"],
        "themes": ["data visualization", "CI/CD", "communication", "cloud"],
        "seniority": "contributed",
    },
    {
        "employer": "Instructure",
        "title": "Marketing Operations Intern",
        "start_date": "2024-06-01",
        "end_date": "2024-09-30",
        "story": (
            "Independently owned an end-to-end ETL pipeline project to support Media Mix Modeling and "
            "marketing spend analysis. The data was fragmented across multiple databases — Snowflake "
            "for internal data, external partner systems for finance data. I wrote SQL queries in "
            "Snowflake to pull and transform the data, used Python with the Google Sheets API to clean "
            "and aggregate it, and managed stakeholder communication with internal teams and external "
            "partners throughout. Learned the statistical foundations of MMM directly from the data "
            "scientist building the model."
        ),
        "outcome": "Delivered end-to-end ETL pipeline for Media Mix Model as sole project owner",
        "skills": ["Python", "SQL", "Snowflake", "ETL", "Google Sheets API", "data pipelines"],
        "themes": ["data-engineering", "ETL", "ownership", "stakeholder-management"],
        "seniority": "owned",
    },
    {
        "employer": "Instructure",
        "title": "Revenue/Data Operations Intern",
        "start_date": "2023-06-01",
        "end_date": "2023-08-31",
        "story": (
            "Validated and optimized Tableau dashboards for the Revenue Operations team by writing SQL "
            "queries across multiple data sources to verify accuracy. Also worked in Salesforce doing "
            "account deduplication and data cleanup. Shadowed a data engineer maintaining marketing "
            "pipeline dashboards, getting exposure to direct data attribution and multi-source pipeline architecture."
        ),
        "outcome": "Improved dashboard accuracy across multiple data sources; cleaned Salesforce account data",
        "skills": ["SQL", "Tableau", "Salesforce", "data validation", "Snowflake"],
        "themes": ["analytics", "data-engineering", "backend"],
        "seniority": "contributed",
    },
    {
        "employer": "Instructure",
        "title": "Revenue/Data Operations Intern",
        "start_date": "2023-06-01",
        "end_date": "2023-08-31",
        "story": (
            "Built a web scraping project to collect school start dates from public school websites "
            "and use that data to predict seasonal server traffic spikes. Wrote the scrapers in Python, "
            "cleaned and structured the data, and delivered findings to the team to help anticipate "
            "when server load would increase."
        ),
        "outcome": "Delivered server traffic prediction dataset from scraped school calendar data",
        "skills": ["Python", "web scraping", "data collection", "data analysis"],
        "themes": ["data-engineering", "automation", "backend"],
        "seniority": "contributed",
    },
    {
        "employer": "Inspirit AI",
        "title": "Project Intern",
        "start_date": "2021-03-01",
        "end_date": "2021-06-30",
        "story": (
            "Worked on a team building an app to identify cancerous skin lesions from photos using ML. "
            "Owned data augmentation to enlarge training datasets — stretching small training sets by "
            "multiple factors through photo editing. Made specific choices based on accuracy vs. "
            "performance tradeoffs. This was a turning point: watching model performance shift based "
            "purely on data preparation — not the architecture — made it clear how foundational data quality is."
        ),
        "outcome": "Expanded training datasets significantly through targeted data augmentation",
        "skills": ["Python", "data augmentation", "computer vision", "ML", "image preprocessing"],
        "themes": ["ML", "data-engineering", "computer vision"],
        "seniority": "contributed",
    },
    {
        "employer": "Personal Project",
        "title": "TrickSki Calculator — ML Pipeline",
        "start_date": "2024-09-01",
        "end_date": "2025-03-01",
        "story": (
            "Co-built a real-time trick water skiing calculator used by competitive athletes and judges, "
            "enforcing official IWWF 2025 rules. I solely designed and integrated the ML pipeline: "
            "trained skill-tiered GRU models on real Nationals and Regionals competition data, "
            "exported to ONNX, and wired up on-device inference via ONNX Runtime Web — no backend "
            "required. The models achieve a 95% hit rate in the top 5 suggestions. Also contributed "
            "to the React frontend. Deployed as a web app and native iOS/Android app via Capacitor."
        ),
        "outcome": "95% hit rate in top 5 trick suggestions; on-device inference with no backend",
        "skills": ["Python", "PyTorch", "GRU", "ONNX", "ONNX Runtime", "React", "machine learning", "Capacitor"],
        "themes": ["ML", "AI", "product", "mobile", "on-device inference"],
        "seniority": "owned",
    },
    {
        "employer": "Personal Project",
        "title": "TrickSki Orientation CNN",
        "start_date": "2024-09-01",
        "end_date": "2025-01-01",
        "story": (
            "Built Phase 1 of a computer vision pipeline to automatically score competitive trick "
            "water skiing runs. Fine-tuned a pretrained ResNet-18 to classify skier body orientation "
            "(forward, back, left, right) from still frames — the foundation for identifying tricks "
            "as orientation sequences. Built a 240-image dataset from scratch by sourcing and labeling "
            "archived tournament footage. Key breakthroughs: removing rotational data augmentation "
            "(which was destroying orientation signal) and adding a center crop to cut background noise "
            "pushed test accuracy from ~50% to 81-85%."
        ),
        "outcome": "Test accuracy improved from ~50% to 81-85% through targeted preprocessing changes",
        "skills": ["Python", "CNN", "ResNet", "PyTorch", "computer vision", "data preprocessing", "transfer learning"],
        "themes": ["ML", "computer vision", "research", "AI"],
        "seniority": "owned",
    },
    {
        "employer": "UW-Madison Academic Project",
        "title": "MiniSpark Engine (Operating Systems)",
        "start_date": "2024-09-01",
        "end_date": "2024-12-31",
        "story": (
            "Implemented a Spark-style data processing engine in C supporting lazy RDD transformation "
            "pipelines (map, filter, partitionBy, join) across partitioned datasets. Built a custom "
            "POSIX thread pool with a recursive post-order DAG scheduler that resolves all partition "
            "dependencies before submitting work — preventing deadlocks in deep dependency chains. "
            "Added microsecond-resolution task timing via a dedicated monitoring thread. "
            "Diagnosed and resolved concurrency bugs including data races and partition corruption "
            "using GDB and ThreadSanitizer."
        ),
        "outcome": "Full Spark-style engine in C with deadlock-free parallel DAG execution",
        "skills": ["C", "multithreading", "POSIX threads", "operating systems", "systems programming", "concurrency"],
        "themes": ["systems", "distributed-systems", "performance", "reliability"],
        "seniority": "owned",
    },
    {
        "employer": "UW-Madison Academic Project",
        "title": "Spark HDFS Distributed Cluster (Big Data Systems)",
        "start_date": "2024-01-01",
        "end_date": "2024-05-31",
        "story": (
            "Built a fully containerized 6-node distributed cluster with Apache Spark and HDFS using "
            "Docker Compose to analyze ~400k real Wisconsin mortgage applications (HMDA 2021). "
            "Demonstrated all three Spark query interfaces (RDD, DataFrame, Spark SQL), designed a "
            "Hive data warehouse with bucketing for partition-local aggregations, and analyzed "
            "broadcast join vs. shuffle behavior through query plan inspection. Trained a PySpark "
            "MLlib Decision Tree classifier to predict loan approval, achieving 89.55% accuracy."
        ),
        "outcome": "89.55% loan approval prediction accuracy; full 6-node distributed Spark cluster",
        "skills": ["Python", "Spark", "HDFS", "Docker", "PySpark", "SQL", "machine learning", "Hive"],
        "themes": ["distributed-systems", "data-engineering", "ML", "big data"],
        "seniority": "owned",
    },
    {
        "employer": "UW-Madison Coursework",
        "title": "AI & ML Systems (Artificial Neural Networks + Big Data Systems)",
        "start_date": "2022-08-01",
        "end_date": "2025-12-31",
        "story": (
            "Deep coursework in AI and ML across multiple classes. Artificial Neural Networks: "
            "implemented and studied CNNs, RNNs, transformers, backpropagation, and MLPs. "
            "Big Data Systems: hands-on with Docker, PyTorch, gRPC, SQL, HDFS, MapReduce, Spark, "
            "Cassandra, and Kafka. Data Science Modeling: applied statistics in R covering "
            "Monte Carlo simulation, Bayesian inference, linear/logistic regression, random forests, "
            "and cross-validation. Algorithms: greedy, divide and conquer, dynamic programming, "
            "network flow."
        ),
        "outcome": "Double B.S. in CS and Data Science, graduated Dec 2025",
        "skills": [
            "Python", "R", "SQL", "PyTorch", "Spark", "Kafka", "Docker",
            "machine learning", "statistics", "algorithms", "data structures"
        ],
        "themes": ["ML", "AI", "data-engineering", "distributed-systems", "research"],
        "seniority": "contributed",
    },
]


def seed():
    conn = get_conn()
    cur = get_cursor(conn)

    cur.execute("DELETE FROM experience_entries")
    cur.execute("DELETE FROM candidate_meta")
    cur.execute("DELETE FROM soft_signals")
    conn.commit()

    # candidate_meta
    cur.execute(
        """
        INSERT INTO candidate_meta
            (name, location, remote_pref, target_title, salary_min, salary_target,
             years_experience, visa_status, education, languages)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            CANDIDATE["name"],
            CANDIDATE["location"],
            CANDIDATE["remote_pref"],
            CANDIDATE["target_title"],
            CANDIDATE["salary_min"],
            CANDIDATE["salary_target"],
            CANDIDATE["years_experience"],
            CANDIDATE["visa_status"],
            json.dumps(CANDIDATE["education"]),
            CANDIDATE["languages"],
        ),
    )

    # soft_signals
    cur.execute(
        """
        INSERT INTO soft_signals
            (preferred_problems, preferred_culture, avoid, excited_about, work_style)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            SOFT_SIGNALS["preferred_problems"],
            SOFT_SIGNALS["preferred_culture"],
            SOFT_SIGNALS["avoid"],
            SOFT_SIGNALS["excited_about"],
            SOFT_SIGNALS["work_style"],
        ),
    )
    conn.commit()
    print("Inserted candidate_meta and soft_signals.")

    # experience entries + embeddings
    for i, exp in enumerate(EXPERIENCES):
        cur.execute(
            """
            INSERT INTO experience_entries
                (employer, title, start_date, end_date, story, outcome, skills, themes, seniority)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                exp["employer"],
                exp["title"],
                exp["start_date"],
                exp["end_date"],
                exp["story"],
                exp["outcome"],
                exp["skills"],
                exp["themes"],
                exp["seniority"],
            ),
        )
        row = cur.fetchone()
        entry_id = row["id"]
        conn.commit()

        embed_text = exp["story"]
        if exp.get("outcome"):
            embed_text += " " + exp["outcome"]
        embed_and_store(entry_id, embed_text)
        print(f"  [{i+1}/{len(EXPERIENCES)}] {exp['employer']} — {exp['title'][:50]}")

    print("\nSeed complete.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    seed()
