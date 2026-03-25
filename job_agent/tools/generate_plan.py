"""
Tool: generate_plan
Opus-powered strategic application plan.
Takes the distilled context and produces a concrete strategy for resume + cover letter.
"""

import json
import os
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """\
You are a senior career strategist with deep experience in technical hiring. \
You create application strategies that are honest, specific, and maximally effective.

Your plan must be grounded in reality — do not suggest exaggerating or fabricating experience.
The best strategy surfaces the strongest honest fit and handles gaps with confidence, not defensiveness.

Never open resume_angle or cover_letter_hook with a duration headline \
(e.g. "X years of experience", "over the past year"). The candidate's story is defined by \
what they built and owned — lead with specific employers and outcomes, not a tenure summary.

Always return valid JSON.
"""

PLAN_SCHEMA = {
    "strategy_summary": "string — 1 sentence: the core positioning angle",
    "lead_with": ["list of 2-3 experience names (employer + role) to feature most prominently"],
    "deprioritize": ["list of experience names to minimize or omit"],
    "gap_handling": [
        {
            "gap": "string — the gap",
            "approach": "string — one of: address_directly | redirect_to_strength | acknowledge_briefly | omit",
            "framing": "string — one sentence on how to handle it",
        }
    ],
    "resume_angle": "string — 1-2 sentence narrative for the resume summary",
    "cover_letter_hook": "string — 1-2 sentence opening hook",
    "cover_letter_fit": "string — 1-2 sentences on the fit angle to develop in the body",
    "key_themes": ["list of 3-4 themes to weave through both documents"],
    "tone": "string — recommended tone (e.g. confident, direct, technical)",
}


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("PLAN_MODEL", "claude-opus-4-6")

    distilled = input_data["distilled_context"]
    jd_brief = input_data["jd_brief"]
    candidate_meta = input_data["candidate_meta"]

    user_message = f"""\
Create a strategic application plan for this candidate.

<job_brief>
{json.dumps(jd_brief, indent=2)}
</job_brief>

<candidate_meta>
{json.dumps(candidate_meta, indent=2, default=str)}
</candidate_meta>

<fit_analysis>
{json.dumps(distilled, indent=2)}
</fit_analysis>

Based on this fit analysis, create a concrete strategy that:
1. Maximises the strong matches
2. Handles weak matches honestly but confidently
3. Does not paper over hard misses — acknowledges them where needed
4. Produces a coherent narrative across resume and cover letter

Return a JSON object with exactly this schema:
{json.dumps(PLAN_SCHEMA, indent=2)}

Return ONLY valid JSON. No markdown fences, no explanation.
"""

    for attempt in range(5):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            break
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 4:
                wait = 15 * (attempt + 1)
                print(f"      [Opus] overloaded — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise

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
                max_tokens=1500,
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
            retry_raw = retry_response.content[0].text.strip()
            if retry_raw.startswith("```"):
                retry_raw = retry_raw.split("```")[1]
                if retry_raw.startswith("json"):
                    retry_raw = retry_raw[4:]
                retry_raw = retry_raw.strip()
            result = json.loads(retry_raw)

    return result
