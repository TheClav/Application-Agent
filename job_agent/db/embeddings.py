"""
Embeddings pipeline — write and search experience entry vectors.
Uses VoyageAI (voyage-large-2) by default, falls back to OpenAI if VOYAGE_API_KEY is not set.
"""

import os
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "voyage-large-2")
EMBEDDING_DIM = 1536  # voyage-large-2 outputs 1536-dim vectors


def _get_embedding(text: str) -> list[float]:
    if EMBEDDING_MODEL.startswith("voyage"):
        import time
        import voyageai
        client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
        for attempt in range(6):
            try:
                result = client.embed([text], model=EMBEDDING_MODEL)
                return result.embeddings[0]
            except voyageai.error.RateLimitError:
                wait = 22 * (attempt + 1)
                print(f"      [voyage] rate limited — waiting {wait}s...")
                time.sleep(wait)
        raise RuntimeError("Voyage rate limit: exhausted retries")
    else:
        # OpenAI fallback
        from openai import OpenAI
        client = OpenAI()
        result = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return result.data[0].embedding


def embed_and_store(entry_id: str, story_text: str) -> None:
    """Embed story_text and write the vector back to experience_entries."""
    from job_agent.db.connection import get_conn, get_cursor

    vector = _get_embedding(story_text)
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute(
        "UPDATE experience_entries SET embedding = %s WHERE id = %s",
        (vector, entry_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def search(query_text: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
    """
    Semantic search over experience_entries.
    Returns top_k entries ranked by cosine similarity.
    Optional filters: seniority (str), recency_years (int).
    """
    from job_agent.db.connection import get_conn, get_cursor

    query_vector = _get_embedding(query_text)
    conn = get_conn()
    cur = get_cursor(conn)

    where_clauses = ["embedding IS NOT NULL"]
    filter_params: list = []

    if filters:
        if "seniority" in filters:
            where_clauses.append("seniority = %s")
            filter_params.append(filters["seniority"])
        if "recency_years" in filters:
            where_clauses.append(
                "(end_date IS NULL OR end_date >= now() - (%s || ' years')::interval)"
            )
            filter_params.append(str(filters["recency_years"]))

    where_sql = " AND ".join(where_clauses)

    cur.execute(
        f"""
        SELECT
            id, employer, title, start_date, end_date,
            story, outcome, skills, themes, seniority,
            1 - (embedding <=> %s::vector) AS similarity
        FROM experience_entries
        WHERE {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        [query_vector] + filter_params + [query_vector, top_k],
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
