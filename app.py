"""
Flask web UI for the Job Application Agent.
Run: python app.py
Then open http://localhost:5000
"""

import os
import logging
import threading
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file, render_template_string

app = Flask(__name__)

# Track jobs: job_id -> {status, result, error, log_lines}
_jobs: dict = {}
_jobs_lock = threading.Lock()


class _LogCaptureHandler(logging.Handler):
    """Append INFO+ log records for a single job into a shared list."""
    def __init__(self, lines: list):
        super().__init__()
        self._lines = lines

    def emit(self, record):
        msg = record.getMessage().strip()
        if msg:
            self._lines.append(msg)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Job Application Agent</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f0f12;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }

    .card {
      width: 100%;
      max-width: 720px;
      background: #1a1a24;
      border: 1px solid #2d2d3d;
      border-radius: 16px;
      padding: 2.5rem;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    }

    h1 {
      font-size: 1.5rem;
      font-weight: 700;
      color: #f8fafc;
      margin-bottom: 0.4rem;
    }

    .subtitle {
      font-size: 0.875rem;
      color: #64748b;
      margin-bottom: 2rem;
    }

    label {
      display: block;
      font-size: 0.8rem;
      font-weight: 600;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 0.5rem;
    }

    textarea {
      width: 100%;
      height: 260px;
      background: #0f0f12;
      border: 1px solid #2d2d3d;
      border-radius: 10px;
      color: #e2e8f0;
      font-size: 0.875rem;
      line-height: 1.6;
      padding: 1rem;
      resize: vertical;
      outline: none;
      transition: border-color 0.2s;
    }

    textarea:focus {
      border-color: #6366f1;
    }

    textarea::placeholder {
      color: #3d3d52;
    }

    .mode-group {
      display: flex;
      gap: 0.75rem;
      margin: 1.5rem 0;
    }

    .mode-btn {
      flex: 1;
      padding: 0.75rem 1rem;
      border: 1px solid #2d2d3d;
      border-radius: 10px;
      background: #0f0f12;
      color: #64748b;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      text-align: center;
    }

    .mode-btn:hover {
      border-color: #6366f1;
      color: #a5b4fc;
    }

    .mode-btn.active {
      border-color: #6366f1;
      background: #1e1e38;
      color: #a5b4fc;
    }

    .run-btn {
      width: 100%;
      padding: 0.9rem;
      background: #6366f1;
      border: none;
      border-radius: 10px;
      color: #fff;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s, opacity 0.2s;
    }

    .run-btn:hover:not(:disabled) { background: #4f46e5; }
    .run-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .status-box {
      margin-top: 1.5rem;
      padding: 1rem 1.25rem;
      border-radius: 10px;
      font-size: 0.875rem;
      display: none;
    }

    .status-box.running {
      display: block;
      background: #1e2035;
      border: 1px solid #2d3060;
      color: #a5b4fc;
    }

    .status-box.done {
      display: block;
      background: #0f2320;
      border: 1px solid #166534;
      color: #86efac;
    }

    .status-box.error {
      display: block;
      background: #2a0f0f;
      border: 1px solid #7f1d1d;
      color: #fca5a5;
    }

    .spinner {
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid #4f46e5;
      border-top-color: #a5b4fc;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      margin-right: 8px;
      vertical-align: middle;
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    .download-group {
      display: flex;
      gap: 0.75rem;
      margin-top: 1rem;
    }

    .dl-btn {
      flex: 1;
      padding: 0.7rem 1rem;
      border: 1px solid #166534;
      border-radius: 10px;
      background: #052e16;
      color: #86efac;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      text-align: center;
      transition: background 0.2s;
      display: none;
    }

    .dl-btn:hover { background: #0a3d1e; }

    .meta {
      margin-top: 0.75rem;
      font-size: 0.8rem;
      color: #4ade80;
      opacity: 0.8;
    }

    .log-box {
      margin-top: 0.75rem;
      background: #07070a;
      border: 1px solid #1e1e2e;
      border-radius: 8px;
      padding: 0.75rem 1rem;
      font-family: "SF Mono", "Fira Code", ui-monospace, monospace;
      font-size: 0.72rem;
      color: #475569;
      max-height: 220px;
      overflow-y: auto;
      display: none;
    }

    .log-box.visible { display: block; }

    .log-line { line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
    .log-line.step  { color: #818cf8; }
    .log-line.good  { color: #4ade80; }
    .log-line.warn  { color: #fbbf24; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Job Application Agent</h1>
    <p class="subtitle">Paste a job description, pick what to generate, and get tailored PDFs.</p>

    <label for="jd">Job Description</label>
    <textarea id="jd" placeholder="Paste the full job description here..."></textarea>

    <label style="margin-top:1.5rem">Generate</label>
    <div class="mode-group">
      <button class="mode-btn" data-mode="resume">Resume only</button>
      <button class="mode-btn active" data-mode="both">Resume + Cover Letter</button>
      <button class="mode-btn" data-mode="cover_letter">Cover Letter only</button>
    </div>

    <button class="run-btn" id="runBtn">Run Agent</button>

    <div class="status-box" id="statusBox">
      <span class="spinner" id="spinner"></span>
      <span id="statusMsg">Starting...</span>
      <div class="meta" id="statusMeta"></div>
      <div class="log-box" id="logBox"></div>
    </div>

    <div class="download-group" id="downloadGroup">
      <a class="dl-btn" id="dlResume" href="#">Download Resume PDF</a>
      <a class="dl-btn" id="dlCL" href="#">Download Cover Letter PDF</a>
    </div>
  </div>

  <script>
    let selectedMode = 'both';
    let pollInterval = null;

    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedMode = btn.dataset.mode;
      });
    });

    document.getElementById('runBtn').addEventListener('click', async () => {
      const jd = document.getElementById('jd').value.trim();
      if (!jd) { alert('Please paste a job description first.'); return; }

      setRunning(true);
      clearDownloads();
      showStatus('running', 'Pipeline running... this takes 2–4 minutes.');

      const resp = await fetch('/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd_text: jd, output_mode: selectedMode }),
      });
      const { job_id } = await resp.json();

      pollInterval = setInterval(() => pollStatus(job_id), 3000);
    });

    async function pollStatus(job_id) {
      const resp = await fetch(`/status/${job_id}`);
      const data = await resp.json();

      if (data.log_lines) updateLogs(data.log_lines);

      if (data.status === 'running') return;

      clearInterval(pollInterval);
      setRunning(false);

      if (data.status === 'done') {
        const r = data.result;
        if (r.status === 'skipped') {
          showStatus('error', `Skipped: ${r.reason || 'dealbreaker or low score'}`);
          return;
        }
        if (r.status === 'error') {
          showStatus('error', `Error: ${r.reason || 'unknown error'}`);
          return;
        }

        const ats = r.final_ats_score != null ? `ATS score: ${r.final_ats_score}` : '';
        showStatus('done', `Done! ${ats}`);

        if (r.resume_path) showDownload('dlResume', r.resume_path);
        if (r.cover_letter_path) showDownload('dlCL', r.cover_letter_path);

      } else if (data.status === 'error') {
        showStatus('error', `Error: ${data.error}`);
      }
    }

    function updateLogs(lines) {
      const box = document.getElementById('logBox');
      if (!lines || lines.length === 0) return;
      box.classList.add('visible');
      box.innerHTML = lines.map(l => {
        const esc = l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        const cls = /\\[\\d+\\/\\d+\\]/.test(l) ? 'step'
                  : /score|ATS|Done/.test(l) ? 'good'
                  : /SKIP|FAIL|fabricat/i.test(l) ? 'warn'
                  : '';
        return `<div class="log-line ${cls}">${esc}</div>`;
      }).join('');
      box.scrollTop = box.scrollHeight;
    }

    function setRunning(running) {
      document.getElementById('runBtn').disabled = running;
      document.getElementById('spinner').style.display = running ? 'inline-block' : 'none';
    }

    function showStatus(type, msg) {
      const box = document.getElementById('statusBox');
      box.className = `status-box ${type}`;
      document.getElementById('statusMsg').textContent = msg;
      document.getElementById('spinner').style.display = type === 'running' ? 'inline-block' : 'none';
    }

    function clearDownloads() {
      document.querySelectorAll('.dl-btn').forEach(b => b.style.display = 'none');
    }

    function showDownload(id, path) {
      const btn = document.getElementById(id);
      btn.href = `/download?path=${encodeURIComponent(path)}`;
      btn.style.display = 'block';
    }
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/run", methods=["POST"])
def run_agent():
    data = request.get_json()
    jd_text = data.get("jd_text", "").strip()
    output_mode = data.get("output_mode", "both")

    import uuid
    job_id = str(uuid.uuid4())[:8]

    log_lines: list = []
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "log_lines": log_lines}

    def _worker():
        handler = _LogCaptureHandler(log_lines)
        handler.setLevel(logging.INFO)
        root = logging.getLogger("job_agent")
        root.setLevel(logging.INFO)
        root.propagate = False  # don't leak into Flask's root logger
        root.addHandler(handler)
        try:
            from job_agent.agent.orchestrator import run
            result = run(jd_text, output_mode)
            with _jobs_lock:
                _jobs[job_id].update({"status": "done", "result": result})
        except Exception as e:
            with _jobs_lock:
                _jobs[job_id].update({"status": "error", "error": str(e)})
        finally:
            root.removeHandler(handler)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def job_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id, {"status": "not_found"})
    return jsonify(job)


@app.route("/download")
def download_file():
    path = request.args.get("path", "")
    p = Path(path)
    if not p.exists() or not p.is_file():
        return "File not found", 404
    return send_file(str(p.resolve()), as_attachment=True)


if __name__ == "__main__":
    print("Starting Job Application Agent UI at http://localhost:8080")
    app.run(debug=False, port=8080)
