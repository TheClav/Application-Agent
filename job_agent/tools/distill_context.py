"""
Tool: distill_context
Haiku-powered context distillation.
Maps JD requirements against the candidate's experience bank with explicit match/gap classification.
Produces a tight context package for the Opus planner.
"""

import json
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """\
You are a precise job fit analyst. Your job is to map a candidate's experience against \
job requirements with surgical accuracy.

Classification rules:
- strong_match: candidate has clear, direct evidence for this requirement
- weak_match: candidate has adjacent or partial evidence — be specific about what exactly is missing
- hard_miss: candidate has no relevant evidence — be honest, do not stretch

Do not editorialize. Report what is there and what is not.
Always return valid JSON.
"""

OUTPUT_SCHEMA = {
    "strong_matches": [
        {
            "requirement": "string — the JD requirement",
            "evidence": "string — specific experience entry that covers this",
        }
    ],
    "weak_matches": [
        {
            "requirement": "string — the JD requirement",
            "evidence": "string — what partial coverage exists",
            "gap": "string — what exactly is missing",
        }
    ],
    "hard_misses": [
        {
            "requirement": "string — the JD requirement",
            "reason": "string — why the candidate has no coverage",
        }
    ],
    "candidate_strengths": ["list of 3-5 standout strengths relative to this specific role"],
    "culture_signals": ["list of company/team culture signals extracted from the JD"],
}


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("GENERATION_MODEL", "claude-haiku-4-5-20251001")

    jd_brief = input_data["jd_brief"]
    candidate_meta = input_data["candidate_meta"]
    experiences = input_data["experiences"]
    soft_signals = input_data.get("soft_signals", {})

    user_message = f"""\
Map this candidate's experience against the job requirements.

<job_brief>
{json.dumps(jd_brief, indent=2)}
</job_brief>

<candidate_meta>
{json.dumps(candidate_meta, indent=2, default=str)}
</candidate_meta>

<experience_bank>
{json.dumps(experiences, indent=2, default=str)}
</experience_bank>

<soft_signals>
{json.dumps(soft_signals, indent=2, default=str)}
</soft_signals>

For each required skill in the JD, classify as strong_match, weak_match, or hard_miss.
Be specific — cite actual experience entries as evidence.

Return a JSON object with exactly this schema:
{json.dumps(OUTPUT_SCHEMA, indent=2)}

Return ONLY valid JSON. No markdown fences, no explanation.
"""

    response = client.messages.create(
        model=model,
        max_tokens=3000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # If the response was cut off, retry fresh with a higher limit — don't prefill with truncated JSON
    if response.stop_reason == "max_tokens":
        response = client.messages.create(
            model=model,
            max_tokens=8096,
            temperature=0,
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
            # Only use prefill retry when we got a complete but malformed response
            retry_response = client.messages.create(
                model=model,
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": "That response was not valid JSON. Return ONLY the JSON object, nothing else.",
                    },
                ],
            )
            result = json.loads(retry_response.content[0].text.strip())

    return result
