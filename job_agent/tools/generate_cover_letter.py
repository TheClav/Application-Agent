"""
Tool: generate_cover_letter
Generates a tailored cover letter from writing_context + finished resume.
Hard cap: 350 words.
"""

import json
import os
import anthropic

SYSTEM_PROMPT = """\
You are an expert cover letter writer. You write cover letters that are specific, genuine, and brief.

Rules:
1. Never repeat bullet points or phrases from the resume — the cover letter extends it.
2. Never fabricate. Only reference skills and experiences that exist in the experience bank.
3. Never state or imply a specific duration of experience (e.g. "2 years at X", "over the past year", \
"years of experience with Y") unless that exact figure is explicitly derivable from the dates in the \
resume. If you need to reference tenure, use the employer name and role — never invent a time span.
4. Hard cap: 350 words. Count carefully.
4. Structure:
   - Hook: a specific, non-generic opening that names the role and signals genuine understanding \
of what the company/team does. Not "I am excited to apply for..."
   - Fit paragraph: name 1-2 specific challenges from the JD and reference concrete experience that \
addresses them.
   - Gap paragraph (only if gap_brief is non-trivial): acknowledge the gap honestly, briefly, \
and redirect to adjacent strength.
   - Interest paragraph: use soft_signals to write a genuine 2-3 sentence signal of why this \
specific company/role is interesting. If soft_signals data is thin, flag low confidence.
5. Never invent or aggregate tenure. Do not write phrases like "I've spent the last 2 years" or \
"years of experience with X" unless the resume dates make this exactly true. Reference employers \
and roles by name instead.
6. Tone: direct, confident, no corporate filler.
7. Never use em dashes (—). Use commas, colons, or restructure the sentence instead.

Always return valid JSON matching the exact schema.
"""

CL_SCHEMA = {
    "cover_letter": "string — the full cover letter text",
    "word_count": "integer",
    "gaps_addressed": ["list of strings — gaps from gap_brief that were addressed"],
    "confidence": "string: 'high' | 'medium' | 'low' — how well soft_signals supported the interest paragraph",
}


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("GENERATION_MODEL", "claude-sonnet-4-20250514")

    ctx = input_data["writing_context"]
    resume = input_data["resume"]

    # Only pass CL-relevant plan fields — resume_angle, lead_with, deprioritize not needed here
    cl_plan = {k: ctx["plan"][k] for k in ("cover_letter_hook", "cover_letter_fit", "gap_handling", "key_themes", "tone", "strategy_summary") if k in ctx.get("plan", {})} if ctx.get("plan") else None

    user_message = f"""\
Write a cover letter for this candidate.

<job_brief>
{json.dumps(ctx.get("jd_brief", {}), indent=2)}
</job_brief>

<candidate_meta>
{json.dumps(ctx.get("candidate_meta", {}), indent=2)}
</candidate_meta>

<soft_signals>
{json.dumps(ctx.get("soft_signals", {}), indent=2)}
</soft_signals>

<finished_resume>
{json.dumps(resume, indent=2)}
</finished_resume>

{f'<application_plan>{json.dumps(cl_plan, indent=2)}</application_plan>' if cl_plan else ""}

{f'<revision_instructions>{chr(10).join(ctx["cl_revision_instructions"])}</revision_instructions>' if ctx.get("cl_revision_instructions") else ""}

Use cover_letter_hook as your opening and cover_letter_fit as the body angle from the application_plan.
Do NOT repeat anything from the resume bullets. Extend the story, don't repeat it.
Hard cap: 350 words. Count carefully.

Return a JSON object with exactly this schema:
{json.dumps(CL_SCHEMA, indent=2)}

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
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": user_message + "\n\nIMPORTANT: Return ONLY the raw JSON object. No markdown, no explanation, no preamble.",
                }],
            )
            retry_raw = retry_response.content[0].text.strip()
            if not retry_raw:
                raise ValueError("generate_cover_letter: model returned empty response on retry")
            if retry_raw.startswith("```"):
                retry_raw = retry_raw.split("```")[1]
                if retry_raw.startswith("json"):
                    retry_raw = retry_raw[4:]
                retry_raw = retry_raw.strip()
            result = json.loads(retry_raw)

    return result
