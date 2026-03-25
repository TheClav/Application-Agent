"""
Tool: get_soft_signals
Fetches the single soft_signals row. Used to shape cover letter tone and interest paragraph.
"""

from job_agent.db.connection import get_conn, get_cursor

TOOL_SCHEMA = {
    "name": "get_soft_signals",
    "description": (
        "Fetch the candidate's soft profile signals: preferred problem types, preferred culture, "
        "things to avoid, what they're excited about, and work style. Use this to inform cover letter "
        "tone and to write a genuine interest paragraph."
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
    cur.execute("SELECT * FROM soft_signals LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise RuntimeError("No soft_signals row found. Run seed.py first.")
    result = dict(row)
    result["id"] = str(result["id"])
    return result
