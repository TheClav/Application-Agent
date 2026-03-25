"""
Orchestrator — main agent loop.
Follows the exact sequence from the build plan (section 6).

Loop strategy:
- Run up to MAX_REVISION_LOOPS iterations for both resume and cover letter.
- Track best result by ATS score (resume) or pass status (cover letter).
- Early exit if score improvement < ATS_MIN_DELTA between iterations.
- Early exit if score hits ATS_CEILING.
- Always use the highest-scoring draft, even if no iteration fully passed.
"""

import json
import os
import traceback
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from job_agent.tools import (
    get_candidate_meta,
    get_soft_signals,
    search_profile,
    hard_filter,
    distill_context,
    generate_plan,
    generate_resume,
    evaluate_resume,
    generate_cover_letter,
    evaluate_cover_letter,
)
from job_agent.db.connection import get_conn, get_cursor
from job_agent.rendering import render_resume_pdf, render_cover_letter_pdf
from job_agent.logger import init_run_logger

import anthropic

MAX_REVISION_LOOPS = int(os.environ.get("MAX_REVISION_LOOPS", 5))
ATS_MIN_DELTA = int(os.environ.get("ATS_MIN_DELTA", 2))   # stop if improvement < this
ATS_CEILING = int(os.environ.get("ATS_CEILING", 95))      # stop if score hits this
MODEL = os.environ.get("GENERATION_MODEL", "claude-sonnet-4-20250514")


def _log_run(
    job_title, company, jd_text,
    initial_ats_score, final_ats_score,
    resume_path, cover_letter_path,
    status, log_path=None,
    cl_passed=None, resume_iterations=None, cl_iterations=None,
    skip_reason=None, strategy=None, fabrication_detected=None,
    resume_json=None, cover_letter_text=None,
):
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute(
        """
        INSERT INTO application_log
            (job_title, company, jd_text, initial_ats_score, final_ats_score,
             resume_path, cover_letter_path, status, created_at,
             cl_passed, resume_iterations, cl_iterations,
             skip_reason, strategy, log_path, fabrication_detected,
             resume_json, cover_letter_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            job_title, company, jd_text,
            initial_ats_score, final_ats_score,
            resume_path, cover_letter_path,
            status, datetime.now(),
            cl_passed, resume_iterations, cl_iterations,
            skip_reason, strategy, log_path, fabrication_detected,
            json.dumps(resume_json) if resume_json else None,
            cover_letter_text,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def _parse_jd(jd_text: str, client: anthropic.Anthropic, log) -> dict:
    schema = {
        "role_title": "string",
        "company": "string or null",
        "required_skills": ["list"],
        "nice_to_have": ["list"],
        "seniority": "string",
        "domain": "string",
        "key_themes": ["2-4 strings"],
        "company_size_hint": "string or null",
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                f"Parse this job description into structured JSON.\n\n"
                f"<job_description>\n{jd_text}\n</job_description>\n\n"
                f"Return a JSON object with exactly this schema:\n{json.dumps(schema, indent=2)}\n\n"
                f"Return ONLY valid JSON."
            ),
        }],
    )
    raw = response.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

    log.debug(f"JD parsed: {json.dumps(result, indent=2)}")
    return result


def _profile_summary(candidate_meta: dict, experiences: list[dict]) -> str:
    lines = [
        f"{candidate_meta.get('name')} — {candidate_meta.get('target_title')}",
        f"Location: {candidate_meta.get('location')} | Remote: {candidate_meta.get('remote_pref')}",
        f"Years experience: {candidate_meta.get('years_experience')} | Visa: {candidate_meta.get('visa_status')}",
        "",
        "Experience highlights:",
    ]
    for exp in experiences[:8]:
        lines.append(f"- {exp.get('employer')} ({exp.get('title')}): {exp.get('story', '')[:200]}")
        if exp.get("skills"):
            lines.append(f"  Skills: {', '.join(exp['skills'])}")
    return "\n".join(lines)


def _merge_dedupe_experiences(lists: list[list[dict]], max_count: int = 12) -> list[dict]:
    seen_ids = set()
    seen_titles = set()
    merged = []
    for result_list in lists:
        for exp in result_list:
            eid = str(exp.get("id", ""))
            title_key = (exp.get("employer", ""), exp.get("title", ""))
            if (eid and eid in seen_ids) or title_key in seen_titles:
                continue
            seen_ids.add(eid)
            seen_titles.add(title_key)
            merged.append(exp)
    merged.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    return merged[:max_count]


def run(jd_text: str, output_mode: str = "both") -> dict:
    # output_mode: "resume" | "cover_letter" | "both"
    import logging

    # Temporary logger before we know company/role
    tmp_log = logging.getLogger("job_agent.init")
    if not tmp_log.handlers:
        tmp_log.addHandler(logging.StreamHandler())
        tmp_log.setLevel(logging.INFO)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("\n=== Job Application Agent ===\n")

    # ── Step 1: Parse JD ──────────────────────────────────────────────────────
    print("[1/10] Parsing job description...")
    jd_brief = _parse_jd(jd_text, client, tmp_log)
    company = jd_brief.get("company") or "Unknown"
    role = jd_brief.get("role_title") or "Unknown"
    print(f"      Role: {role} @ {company}")

    # Now we know company/role — init the real logger
    log, log_path = init_run_logger(company, role)
    log.info(f"\n=== Job Application Agent ===")
    log.info(f"Role: {role} @ {company}")
    log.debug(f"JD text length: {len(jd_text)} chars")
    log.debug(f"JD brief:\n{json.dumps(jd_brief, indent=2)}")

    try:
        return _run_pipeline(
            jd_text, output_mode, jd_brief, company, role,
            client, log, log_path,
        )
    except Exception:
        tb = traceback.format_exc()
        log.error(f"\n!!! UNHANDLED EXCEPTION — full traceback:\n{tb}")
        try:
            _log_run(role, company, jd_text, None, None, None, None, "error", log_path)
        except Exception:
            log.error("Also failed to write error status to application_log")
        raise


def _run_pipeline(
    jd_text, output_mode, jd_brief, company, role,
    client, log, log_path,
) -> dict:
    # ── Step 2: Candidate meta + hard filter ─────────────────────────────────
    log.info("\n[2/10] Fetching candidate meta...")
    candidate_meta = get_candidate_meta.run({})
    log.debug(f"Candidate meta: {json.dumps(candidate_meta, indent=2, default=str)}")

    visa = candidate_meta.get("visa_status", "")
    if visa == "requires_sponsorship":
        log.info("      SKIP: Candidate requires visa sponsorship")
        _log_run(role, company, jd_text, 0, None, None, None, "skipped", log_path,
                 skip_reason="visa_sponsorship_required")
        return {"status": "skipped", "reason": "visa_sponsorship_required"}

    # ── Step 3: Hard filter (dealbreaker check) ───────────────────────────────
    log.info("[3/10] Running hard filter (dealbreaker check)...")
    broad = search_profile.run({"query": role, "top_k": 8})
    profile_summary = _profile_summary(candidate_meta, broad)
    log.debug(f"Profile summary for hard filter:\n{profile_summary}")

    hf_result = hard_filter.run({
        "jd_text": jd_text,
        "candidate_meta": candidate_meta,
        "profile_summary": profile_summary,
    })
    log.debug(f"Hard filter result: {json.dumps(hf_result, indent=2)}")
    for check in hf_result.get("dealbreakers_checked", []):
        status = "PASS" if check.get("met") else "FAIL"
        log.info(f"      [{status}] {check.get('requirement')} — {check.get('reason')}")

    if not hf_result.get("passed", True):
        failures = hf_result.get("failures", [])
        log.info(f"      SKIP: Dealbreaker(s) triggered: {failures}")
        _log_run(role, company, jd_text, None, None, None, None, "skipped", log_path,
                 skip_reason=f"dealbreaker: {', '.join(failures)}")
        return {"status": "skipped", "reason": "dealbreaker", "failures": failures}

    # ── Step 4: Three search_profile queries + merge ──────────────────────────
    log.info("[4/10] Searching experience bank (3 queries)...")
    theme_query = " ".join(jd_brief.get("key_themes", [jd_brief.get("domain", "engineering")]))
    required_skills = jd_brief.get("required_skills", [])
    gap_query = " ".join(required_skills) if required_skills else theme_query
    seniority_query = "owned end-to-end delivered independently shipped solo"

    log.debug(f"Theme query:    {theme_query}")
    log.debug(f"Gap query:      {gap_query}")
    log.debug(f"Seniority query:{seniority_query}")

    theme_results   = search_profile.run({"query": theme_query, "top_k": 5})
    gap_results     = search_profile.run({"query": gap_query, "top_k": 5})
    seniority_results = search_profile.run({
        "query": seniority_query, "top_k": 5, "filters": {"seniority": "owned"},
    })

    experiences = _merge_dedupe_experiences(
        [theme_results, gap_results, seniority_results], max_count=12
    )
    log.info(f"      Found {len(experiences)} unique experiences")
    for exp in experiences:
        log.debug(
            f"  [{exp.get('similarity', 0):.3f}] {exp.get('employer')} — "
            f"{exp.get('title')} | skills: {exp.get('skills', [])}"
        )

    # ── Step 5: Soft signals ──────────────────────────────────────────────────
    log.info("[5/10] Fetching soft signals...")
    soft_signals = get_soft_signals.run({})
    log.debug(f"Soft signals: {json.dumps(soft_signals, indent=2, default=str)}")

    # ── Step 6: Distill context (Haiku) ──────────────────────────────────────
    log.info("[6/10] Distilling context...")
    distilled = distill_context.run({
        "jd_brief": jd_brief,
        "candidate_meta": candidate_meta,
        "experiences": experiences,
        "soft_signals": soft_signals,
    })
    log.info(f"      Strong matches: {len(distilled.get('strong_matches', []))}")
    log.info(f"      Weak matches:   {len(distilled.get('weak_matches', []))}")
    log.info(f"      Hard misses:    {len(distilled.get('hard_misses', []))}")
    log.debug(f"Distilled context:\n{json.dumps(distilled, indent=2)}")

    # ── Step 7: Generate plan (Opus) ──────────────────────────────────────────
    log.info("[7/10] Generating application plan (Opus)...")
    plan = generate_plan.run({
        "distilled_context": distilled,
        "jd_brief": jd_brief,
        "candidate_meta": candidate_meta,
    })
    log.info(f"      Strategy: {plan.get('strategy_summary', '')}")
    log.info(f"      Resume angle: {plan.get('resume_angle', '')}")
    log.info(f"      CL hook: {plan.get('cover_letter_hook', '')}")
    log.debug(f"Full plan:\n{json.dumps(plan, indent=2)}")

    writing_context = {
        "jd_brief": jd_brief,
        "experiences": experiences,
        "candidate_meta": candidate_meta,
        "soft_signals": soft_signals,
        "distilled_context": distilled,
        "plan": plan,
        "revision_instructions": [],
        "cl_revision_instructions": [],
    }

    # ── Step 8: Resume loop ───────────────────────────────────────────────────
    log.info(f"[8/10] Resume loop (max {MAX_REVISION_LOOPS} iterations, "
             f"early exit if delta < {ATS_MIN_DELTA} or score >= {ATS_CEILING})...")

    best_resume = None
    best_resume_score = 0
    prev_score = 0
    resume_iterations = 0
    any_fabrication = False

    for i in range(MAX_REVISION_LOOPS):
        resume_iterations = i + 1
        log.info(f"\n      ── Resume iteration {i+1}/{MAX_REVISION_LOOPS} ──")

        log.info(f"      Generating resume...")
        resume = generate_resume.run({"writing_context": writing_context})
        log.debug(f"Generated resume:\n{json.dumps(resume, indent=2)}")

        log.info(f"      Evaluating resume...")
        ev = evaluate_resume.run({"resume": resume, "writing_context": writing_context})
        score = ev.get("ats_score", 0)
        delta = score - prev_score if i > 0 else score
        log.info(f"      ATS score: {score}  |  delta: {'+' if delta >= 0 else ''}{delta}  |  passed: {ev.get('passed')}  |  fabrication: {ev.get('fabrication_detected')}")

        if ev.get("rubric_failures"):
            log.info(f"      Rubric failures:")
            for f in ev["rubric_failures"]:
                log.info(f"        • {f}")

        if ev.get("revision_instructions"):
            log.debug(f"      Revision instructions: {ev['revision_instructions']}")

        log.debug(f"Full eval result:\n{json.dumps(ev, indent=2)}")

        if ev.get("fabrication_detected"):
            any_fabrication = True
            log.info("      !! Fabrication detected — injecting correction and retrying")
            fabrication_fix = [
                "CRITICAL: Fabrication was detected. Only use skills and technologies that appear "
                "verbatim in the experience bank entries. Do not add any library, tool, or skill "
                "unless it explicitly appears in an experience entry. "
                "When in doubt, omit the skill entirely."
            ] + ev.get("rubric_failures", [])
            writing_context["revision_instructions"] = fabrication_fix
            prev_score = score
            continue

        if score > best_resume_score:
            best_resume_score = score
            best_resume = resume
            log.info(f"      ✓ New best resume (score {score})")

        # Early exit: ceiling hit
        if score >= ATS_CEILING:
            log.info(f"      Ceiling {ATS_CEILING} reached — stopping loop")
            break

        # Early exit: diminishing returns (skip check on first iteration)
        if i > 0 and abs(score - prev_score) < ATS_MIN_DELTA:
            log.info(f"      Score delta {abs(score - prev_score)} < {ATS_MIN_DELTA} — stopping loop (diminishing returns)")
            break

        prev_score = score
        writing_context["revision_instructions"] = ev.get("revision_instructions", [])

    log.info(f"\n      Resume loop complete. Best score: {best_resume_score}")

    # ── Post-loop score gate ───────────────────────────────────────────────────
    resume_gate = int(os.environ.get("RESUME_SCORE_GATE", 70))
    if best_resume_score < resume_gate:
        log.info(f"      SKIP: Resume score {best_resume_score} < gate {resume_gate} — not worth applying")
        _log_run(role, company, jd_text, None, best_resume_score, None, None, "skipped", log_path,
                 resume_iterations=resume_iterations, skip_reason=f"resume_score_below_gate ({best_resume_score})",
                 fabrication_detected=any_fabrication)
        return {"status": "skipped", "reason": f"resume_score_below_gate ({best_resume_score})"}

    # ── Step 9: Cover letter loop ─────────────────────────────────────────────
    best_cl_text = None
    best_cl_word_count = None
    best_cl_passed = False
    cl_iterations = 0

    if output_mode == "resume":
        log.info("\n[9/10] Skipping cover letter (resume only)")
    else:
        log.info("\n[9/10] Generating cover letter...")

        for i in range(2):
            cl_iterations = i + 1
            cl_result = generate_cover_letter.run({
                "writing_context": writing_context,
                "resume": best_resume,
            })
            cl_text = cl_result.get("cover_letter", "")
            word_count = cl_result.get("word_count", len(cl_text.split()))
            log.info(f"      Word count: {word_count}  |  confidence: {cl_result.get('confidence')}")

            cl_ev = evaluate_cover_letter.run({
                "cover_letter": cl_text,
                "writing_context": writing_context,
            })
            log.info(f"      Fabrication check: {cl_ev.get('fabrication_detected', False)}")

            if cl_ev.get("fabrication_detected") and i == 0:
                log.info("      !! Fabrication detected — retrying once with correction")
                writing_context["cl_revision_instructions"] = [
                    "CRITICAL: Fabrication was detected. Only reference skills, experiences, and "
                    "durations that exist in the experience bank. Do not invent tenure claims or add "
                    "skills not present in the experience entries."
                ]
                any_fabrication = True
                continue

            best_cl_text = cl_text
            best_cl_word_count = word_count
            best_cl_passed = not cl_ev.get("fabrication_detected", False)
            break

        log.info(f"      Cover letter complete.")

    # ── Step 8: Render PDFs ───────────────────────────────────────────────────
    log.info("\n[10/10] Rendering PDFs...")
    run_id = str(uuid.uuid4())[:8]
    company_slug = (company or "company").lower().replace(" ", "_")[:20]
    role_slug = (role or "role").lower().replace(" ", "_")[:20]
    base_name = f"{company_slug}_{role_slug}_{run_id}"

    resume_path = render_resume_pdf(best_resume, candidate_meta, base_name) if output_mode != "cover_letter" else None
    cl_path = render_cover_letter_pdf(best_cl_text, candidate_meta, jd_brief, base_name) if (output_mode != "resume" and best_cl_text) else None
    if resume_path:
        log.info(f"      Resume:       {resume_path}")
    if cl_path:
        log.info(f"      Cover letter: {cl_path}")

    # ── Log to application_log ────────────────────────────────────────────────
    _log_run(
        role, company, jd_text,
        None, best_resume_score,
        resume_path, cl_path,
        "applied", log_path,
        cl_passed=best_cl_passed,
        resume_iterations=resume_iterations,
        cl_iterations=cl_iterations if output_mode != "resume" else None,
        strategy=plan.get("strategy_summary"),
        fabrication_detected=any_fabrication,
        resume_json=best_resume,
        cover_letter_text=best_cl_text,
    )

    log.info(f"\n=== Done ===")
    log.info(f"Final ATS:    {best_resume_score}")
    log.info(f"CL passed:    {best_cl_passed}")
    log.info(f"Log file:     {log_path}")

    return {
        "status": "applied",
        "resume_path": resume_path,
        "cover_letter_path": cl_path,
        "final_ats_score": best_resume_score,
        "cl_passed": best_cl_passed,
        "log_path": log_path,
    }
