"""
Tool: evaluate_cover_letter
Rubric evaluation of the cover letter draft.
"""

import json
import os
import anthropic

SYSTEM_PROMPT = """\
You are a cover letter fabrication checker. Your only job is to detect invented facts.

Check for fabrication:
- A skill, technology, or company is referenced that does not appear in the experience bank.
- A specific duration is stated (e.g. "2 years at X", "over the past year") that is not exactly \
derivable from the resume dates.
- A quantified outcome is claimed that does not appear in the experience bank.

Do NOT flag: rephrasing, paraphrasing, tone, structure, word choice, or style.
When in doubt: do NOT flag. Only flag clear, unambiguous invention.

Always return valid JSON matching the exact schema.
"""

def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    if start != -1:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    raise json.JSONDecodeError("no JSON object found", text, 0)


EVAL_SCHEMA = {
    "passed": "boolean",
    "fabrication_detected": "boolean",
    "failures": ["list of strings describing each rubric failure"],
    "revision_instructions": ["list of specific, actionable revision instructions"],
}


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CL_JUDGE_MODEL", os.environ.get("JUDGE_MODEL", "claude-haiku-4-5-20251001"))

    cover_letter = input_data["cover_letter"]
    ctx = input_data["writing_context"]
    actual_word_count = len(cover_letter.split())

    slim_experiences = [
        {"employer": e.get("employer"), "title": e.get("title"),
         "skills": e.get("skills", []), "outcome": e.get("outcome"),
         "story": (e.get("story") or "")[:200]}
        for e in ctx.get("experiences", [])
    ]

    user_message = f"""\
Evaluate this cover letter draft.

Note: the actual word count (counted programmatically) is {actual_word_count} words.
Only flag word count if this number exceeds 350.

For fabrication checks, use the experience bank below as your source of truth.
Only flag fabrication if a claim has NO basis in any experience entry.
Do NOT flag something as fabrication just because you cannot personally verify it — \
if it appears in the experience bank, it is legitimate.

<experience_bank>
{json.dumps(slim_experiences, indent=2)}
</experience_bank>

<job_brief>
{json.dumps(ctx.get("jd_brief", {}), indent=2)}
</job_brief>

<cover_letter_draft>
{cover_letter}
</cover_letter_draft>

Apply all rubric criteria. Set passed=true only if ALL criteria pass.

Return a JSON object with exactly this schema:
{json.dumps(EVAL_SCHEMA, indent=2)}

Return ONLY valid JSON. No markdown fences, no explanation.
"""

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    try:
        result = _parse_json(raw)
    except json.JSONDecodeError:
        retry_response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": user_message + "\n\nIMPORTANT: Return ONLY the raw JSON object. No markdown, no explanation, no preamble.",
            }],
        )
        retry_raw = retry_response.content[0].text.strip()
        if not retry_raw:
            raise ValueError("evaluate_cover_letter: model returned empty response on retry")
        result = _parse_json(retry_raw)

    return result
