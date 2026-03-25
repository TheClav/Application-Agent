"""
Tool: hard_filter
Extracts dealbreakers from a JD and checks each against the candidate profile.
Returns passed=True only if no dealbreakers are triggered.
"""

import json
import os
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """\
You are a pragmatic job application screener. Your job is to find EXPLICIT hard blockers \
that would cause automatic rejection — not to assess fit or seniority.

A dealbreaker must be EXPLICITLY stated in the JD as a hard requirement. Examples:
- Minimum years explicitly required ("5+ years required", "minimum 3 years")
- Degrees explicitly required with no alternatives ("PhD required")
- Mandatory certifications ("must hold active X certification")
- Work authorization ("no sponsorship available")
- Security clearance requirements
- Minimum GPA explicitly required ("3.5 GPA required", "minimum 3.0 GPA") — check the candidate's
  actual GPA from their profile against any stated minimum

Do NOT flag any of the following — these are NOT dealbreakers:
- Descriptive language about the team or work ("small senior team", "production systems", "architectural ownership") — this describes the environment, not a candidate requirement
- Preference or aspiration language ("meaningful edge in X", "strong foundation in", "ideally", "a plus", "preferred")
- Technical skills that are listed as desired but not as explicit requirements
- Seniority implied by team composition or salary — only flag if years of experience are EXPLICITLY required
- Degree requirements with "or equivalent experience" clauses
- Requirements the candidate clearly meets

When in doubt: PASS. Only fail if the JD uses explicit blocking language like "required", \
"must have", "minimum", or "will not consider candidates without".

Always return valid JSON.
"""

OUTPUT_SCHEMA = {
    "passed": "boolean — true if no dealbreakers are triggered",
    "dealbreakers_checked": [
        {
            "requirement": "string — the exact requirement from the JD",
            "met": "boolean",
            "reason": "string — brief explanation of why it is or is not met",
        }
    ],
    "failures": ["list of requirement strings the candidate does not meet"],
}


def run(input_data: dict) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("GENERATION_MODEL", "claude-sonnet-4-20250514")

    jd_text = input_data["jd_text"]
    candidate_meta = input_data["candidate_meta"]
    profile_summary = input_data.get("profile_summary", "")

    user_message = f"""\
Check this candidate against all dealbreakers in the job description.

<job_description>
{jd_text}
</job_description>

<candidate_profile>
{json.dumps(candidate_meta, indent=2, default=str)}
</candidate_profile>

{f'<experience_summary>{profile_summary}</experience_summary>' if profile_summary else ""}

Extract every dealbreaker from the JD and check each against the candidate.

Return a JSON object with exactly this schema:
{json.dumps(OUTPUT_SCHEMA, indent=2)}

Return ONLY valid JSON. No markdown fences, no explanation.
"""

    for attempt in range(4):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1500,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            break
        except anthropic.APIStatusError as e:
            if e.status_code in (500, 529) and attempt < 3:
                time.sleep(5 * (attempt + 1))
            else:
                raise

    raw = response.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Strip markdown fences if present
        cleaned = raw
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Retry as a fresh call — don't pass the broken output back
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
                raise ValueError("hard_filter: model returned empty response on retry")
            result = json.loads(retry_raw)

    return result
