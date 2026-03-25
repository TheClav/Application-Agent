"""
Tool: search_profile
Semantic search over experience_entries using pgvector.
Called multiple times per run with different query strategies.
"""

from job_agent.db.embeddings import search


def run(input_data: dict) -> list[dict]:
    query = input_data["query"]
    top_k = input_data.get("top_k", 5)
    filters = input_data.get("filters")

    results = search(query, top_k=top_k, filters=filters)

    # Serialise dates and UUIDs
    serialised = []
    for r in results:
        r = dict(r)
        r["id"] = str(r["id"])
        if r.get("start_date"):
            r["start_date"] = str(r["start_date"])
        if r.get("end_date"):
            r["end_date"] = str(r["end_date"])
        serialised.append(r)
    return serialised
