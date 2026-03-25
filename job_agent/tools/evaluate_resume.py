"""
Tool: evaluate_resume
Dual evaluation: rubric check + ATS re-score.
Both must pass to exit the resume revision loop.
"""

import json
import os
import anthropic

SYSTEM_PROMPT = """\
You are a strict resume evaluator. You evaluate resumes with fresh eyes — you have no attachment \
to what was written. Your goal is to find failures and give precise revision instructions.

Rubric criteria (all must pass):
1. Required skills from the JD are covered OR the gap is honestly acknowledged — a skill gap that
   is explicitly addressed is a PASS for this criterion, not a failure
2. Outcomes and measurable results are surfaced in bullets
3. The gap_brief from the ATS analysis is addressed (acknowledged OR covered by adjacent experience)
4. The resume contains the most important JD keywords where the candidate genuinely has that experience.
   Do NOT fail this criterion for keywords the candidate simply does not have — that is a gap, not a
   rubric failure.
5. No fabricated skills or experiences
6. Bullets lead with impact, not activity
7. Tone matches the role seniority
8. Fabrication check: no skill or achievement appears that wasn't in the experience bank

Important: criteria 1, 3, and 4 are about honest coverage — a candidate who acknowledges gaps
clearly and surfaces adjacent strength PASSES these criteria. Do not fail a resume for lacking a
skill the candidate genuinely does not have.

Fabrication definition (be precise — do NOT over-flag):
- Fabricated = a skill, technology, or quantified outcome appears in the resume that has NO basis
  in any experience entry. E.g. "5 years Kubernetes" when no entry mentions Kubernetes at all.
- NOT fabricated = rephrasing, paraphrasing, synthesising across entries, or using JD vocabulary
  to describe real experience. Resume bullets will use different words than the raw story entries —
  that is expected and correct.
- When in doubt, do NOT set fabrication_detected. Only set it for clear, unambiguous invention.

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
    "rubric_failures": ["list of strings describing each failure"],
    "ats_score": "integer 0-100 — your re-score of the resume vs the JD",
    "ats_delta": "integer — ats_score minus initial_ats_score (positive = improvement)",
    "revision_instructions": ["list of specific instructions for the next revision"],
}


def _slim_experiences(experiences: list) -> list:
    """Strip story/outcome text — only keep fields needed for fabrication checking."""
    return [
        {
            "employer": e.get("employer"),
            "title": e.get("title"),
            "skills": e.get("skills", []),
            "themes": e.get("themes", []),
        }
        for e in experiences
    ]


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("JUDGE_MODEL", os.environ.get("GENERATION_MODEL", "claude-sonnet-4-6"))

    resume = input_data["resume"]
    ctx = input_data["writing_context"]
    ats_target = int(os.environ.get("ATS_RESUME_TARGET", 80))

    user_message = f"""\
Evaluate this draft resume.

<job_description_brief>
{json.dumps(ctx.get("jd_brief", {}), indent=2)}
</job_description_brief>

<experience_bank>
{json.dumps(_slim_experiences(ctx.get("experiences", [])), indent=2)}
</experience_bank>

<draft_resume>
{json.dumps(resume, indent=2)}
</draft_resume>

Evaluation criteria:
- Rubric: all 8 criteria above must pass
- ATS target: resume must score >= {ats_target}
- Fabrication: hard fail if any skill/achievement appears that isn't supported by the experience bank

Set passed=true only if ALL rubric criteria pass AND ats_score >= {ats_target}.

Return a JSON object with exactly this schema:
{json.dumps(EVAL_SCHEMA, indent=2)}

Return ONLY valid JSON. No markdown fences, no explanation.
"""

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    try:
        result = _parse_json(raw)
    except json.JSONDecodeError:
        retry_response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": user_message + "\n\nIMPORTANT: Return ONLY the raw JSON object. No markdown, no explanation, no preamble.",
            }],
        )
        retry_raw = retry_response.content[0].text.strip()
        if not retry_raw:
            raise ValueError("evaluate_resume: model returned empty response on retry")
        result = _parse_json(retry_raw)

    return result
