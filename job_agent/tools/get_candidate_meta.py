"""
Tool: get_candidate_meta
Fetches the single candidate_meta row. Used as the hard-filter gate.
"""

from job_agent.db.connection import get_conn, get_cursor

TOOL_SCHEMA = {
    "name": "get_candidate_meta",
    "description": (
        "Fetch the candidate's hard profile facts: location, target title, salary expectations, "
        "visa status, years of experience, and education. Use this first to check whether to proceed "
        "with a job description before doing any expensive work."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def run(_input: dict) -> dict:
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT * FROM candidate_meta LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise RuntimeError("No candidate_meta row found. Run seed.py first.")
    result = dict(row)
    # Convert UUID and date objects to strings for JSON serialisation
    result["id"] = str(result["id"])
    return result
