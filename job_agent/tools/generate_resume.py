"""
Tool: generate_resume
Generates a tailored resume JSON from the writing_context.
"""

import json
import os
import anthropic

SYSTEM_PROMPT = """\
You are an expert technical resume writer. You write resumes that score high on ATS systems AND \
read well to senior engineering hiring managers.

Rules you must follow:
1. Never fabricate skills, outcomes, or experiences. Only use what is in the provided experience bank.
2. Use exact numbers and ranges from the experience bank — do not round or approximate. \
   If the bank says "81-85% accuracy", write "81-85%", not "85%".
3. Only use terminology that appears in the experience bank. Do not introduce words like \
   "ensemble", "production-grade", or similar unless the bank explicitly uses them.
4. Lead every bullet with the impact or outcome, not the activity.
5. Mirror the vocabulary of the job description where truthful — if the JD says "distributed systems", \
use "distributed systems" if the candidate has that experience.
6. Strip resume-speak ("responsible for", "worked on", "helped with"). Write in plain, confident language.
7. Select the 6-8 strongest experiences for this specific role.
8. The summary should be 2-3 sentences max. Specific, not generic.
9. Never use em dashes (—). Use commas, colons, or restructure the sentence instead.

Always return valid JSON matching the exact schema specified.
"""

RESUME_SCHEMA = {
    "summary": "string",
    "experience": [
        {
            "employer": "string",
            "title": "string",
            "dates": "string (e.g. 'Jan 2023 – Present')",
            "description": "string — 1-2 sentence plain-English summary of what the role was and what the candidate worked on. Sets context before the bullets. Do NOT repeat bullet content here.",
            "bullets": ["string", "..."],
        }
    ],
    "skills": ["string"],
    "education": {"degree": "string", "field": "string", "institution": "string"},
}


def _slim_experiences(experiences: list) -> list:
    """Strip embedding + trim story to 350 chars to reduce input tokens."""
    slimmed = []
    for e in experiences:
        slimmed.append({
            "employer": e.get("employer"),
            "title": e.get("title"),
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
            "story": (e.get("story") or "")[:350],
            "outcome": e.get("outcome"),
            "skills": e.get("skills", []),
            "themes": e.get("themes", []),
            "seniority": e.get("seniority"),
        })
    return slimmed


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("GENERATION_MODEL", "claude-sonnet-4-20250514")

    ctx = input_data["writing_context"]

    user_message = f"""\
Write a tailored resume for this candidate.

<job_brief>
{json.dumps(ctx.get("jd_brief", {}), indent=2)}
</job_brief>

<candidate_meta>
{json.dumps(ctx.get("candidate_meta", {}), indent=2, default=str)}
</candidate_meta>

<experience_bank>
{json.dumps(_slim_experiences(ctx.get("experiences", [])), indent=2)}
</experience_bank>

{f'<application_plan>{json.dumps(ctx["plan"], indent=2)}</application_plan>' if ctx.get("plan") else ""}

{f'<revision_instructions>{chr(10).join(ctx["revision_instructions"])}</revision_instructions>' if ctx.get("revision_instructions") else ""}

Follow the application_plan strategy. Lead with the experiences it identifies, handle gaps \
as directed, and use the resume_angle as the basis for the summary section.
Select the best 6-8 experiences for this role. Write 2-4 bullets per role.
For each experience, write a "description" field: 1-2 sentences that set context (what the company does, \
what the role was focused on). Keep it factual and tight — the bullets carry the impact.

Return a JSON object with exactly this schema:
{json.dumps(RESUME_SCHEMA, indent=2)}

Return ONLY valid JSON. No markdown fences, no explanation.
"""

    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            retry_response = client.messages.create(
                model=model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": user_message + "\n\nIMPORTANT: Return ONLY the raw JSON object. No markdown, no explanation, no preamble.",
                }],
            )
            retry_raw = retry_response.content[0].text.strip()
            if not retry_raw:
                raise ValueError("generate_resume: model returned empty response on retry")
            if retry_raw.startswith("```"):
                retry_raw = retry_raw.split("```")[1]
                if retry_raw.startswith("json"):
                    retry_raw = retry_raw[4:]
                retry_raw = retry_raw.strip()
            if not retry_raw:
                raise ValueError("generate_resume: empty JSON after fence stripping on retry")
            result = json.loads(retry_raw)

    return result
