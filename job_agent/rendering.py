"""
PDF rendering — Jinja2 templates + WeasyPrint.
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"

OUTPUTS_DIR.mkdir(exist_ok=True)

_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def render_resume_pdf(resume: dict, candidate_meta: dict, base_name: str) -> str:
    """Render resume dict to PDF. Returns absolute path to the output file."""
    template = _jinja_env.get_template("resume.html")
    html_content = template.render(resume=resume, meta=candidate_meta)
    output_path = str(OUTPUTS_DIR / f"{base_name}_resume.pdf")
    HTML(string=html_content).write_pdf(output_path)
    return output_path


def render_cover_letter_pdf(
    cover_letter_text: str,
    candidate_meta: dict,
    jd_brief: dict,
    base_name: str,
) -> str:
    """Render cover letter to PDF. Returns absolute path to the output file."""
    template = _jinja_env.get_template("cover_letter.html")
    html_content = template.render(
        cover_letter=cover_letter_text,
        meta=candidate_meta,
        jd_brief=jd_brief,
    )
    output_path = str(OUTPUTS_DIR / f"{base_name}_cover_letter.pdf")
    HTML(string=html_content).write_pdf(output_path)
    return output_path
