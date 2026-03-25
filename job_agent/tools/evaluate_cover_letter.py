"""
Tool: evaluate_cover_letter
Rubric evaluation of the cover letter draft.
"""

import json
import os
import anthropic

SYSTEM_PROMPT = """\
You are a strict cover letter evaluator. Evaluate with fresh eyes — no attachment to what was written.

Rubric criteria (all must pass):
1. Hook is specific — not a generic opener like "I am excited to apply". Names the role and shows \
genuine understanding of the company/team.
2. Resume is not repeated — no bullet points or phrases from the resume appear verbatim.
3. Fit paragraph names an actual role challenge from the JD and references concrete experience.
4. Gap is handled if gap_brief is non-trivial (honestly and briefly).
5. Interest paragraph is non-generic — references something specific about the company or domain.
6. Under 350 words — count the words carefully.
8. No em dashes (—) anywhere in the text.
7. No fabrication — only references experience/skills that exist. This includes duration claims: \
any phrase implying a specific length of experience (e.g. "2 years at X", "over the past year", \
"years of experience with Y") must be exactly derivable from the resume dates. Invented or \
aggregated tenure is fabrication.

Fabrication is a hard stop. Set fabrication_detected=true if detected.

Always return valid JSON matching the exact schema.
"""

EVAL_SCHEMA = {
    "passed": "boolean",
    "fabrication_detected": "boolean",
    "failures": ["list of strings describing each rubric failure"],
    "revision_instructions": ["list of specific, actionable revision instructions"],
}


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("JUDGE_MODEL", os.environ.get("GENERATION_MODEL", "claude-sonnet-4-6"))

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
Only fail criterion 6 if this number exceeds 350.

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
                messages=[{
                    "role": "user",
                    "content": user_message + "\n\nIMPORTANT: Return ONLY the raw JSON object. No markdown, no explanation, no preamble.",
                }],
            )
            retry_raw = retry_response.content[0].text.strip()
            if not retry_raw:
                raise ValueError("evaluate_cover_letter: model returned empty response on retry")
            result = json.loads(retry_raw)

    return result
