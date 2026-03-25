-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 4.1 candidate_meta
CREATE TABLE IF NOT EXISTS candidate_meta (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            text NOT NULL,
    location        text,
    remote_pref     text CHECK (remote_pref IN ('remote', 'hybrid', 'onsite')),
    target_title    text,
    salary_min      integer,
    salary_target   integer,
    years_experience integer,
    visa_status     text,
    education       jsonb,
    languages       text[],
    gpa             numeric(3,2)
);

-- 4.2 experience_entries
CREATE TABLE IF NOT EXISTS experience_entries (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer    text NOT NULL,
    title       text NOT NULL,
    start_date  date NOT NULL,
    end_date    date,
    story       text NOT NULL,
    outcome     text,
    skills      text[],
    themes      text[],
    seniority   text CHECK (seniority IN ('led', 'contributed', 'owned')),
    embedding   vector(1536)
);

-- 4.3 soft_signals
CREATE TABLE IF NOT EXISTS soft_signals (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    preferred_problems  text,
    preferred_culture   text,
    avoid               text,
    excited_about       text,
    work_style          text
);

-- 4.4 application_log
CREATE TABLE IF NOT EXISTS application_log (
    id                   uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_title            text,
    company              text,
    jd_text              text,
    initial_ats_score    integer,
    final_ats_score      integer,
    resume_path          text,
    cover_letter_path    text,
    status               text CHECK (status IN ('applied', 'skipped', 'error')),
    created_at           timestamp DEFAULT now(),
    cl_passed            boolean,
    resume_iterations    integer,
    cl_iterations        integer,
    skip_reason          text,
    strategy             text,
    log_path             text,
    fabrication_detected boolean,
    resume_json          jsonb,
    cover_letter_text    text
);
