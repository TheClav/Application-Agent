"""
Logging setup — one log file per run, written to logs/.
Call init_run_logger() at the start of each orchestrator run to get a configured logger.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _slugify(text: str, max_len: int = 25) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text[:max_len].strip("_")


def init_run_logger(company: str = "unknown", role: str = "unknown") -> logging.Logger:
    """
    Create and return a logger for one agent run.
    Writes to both stdout (INFO) and a per-run log file (DEBUG).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{_slugify(company)}_{_slugify(role)}.log"
    log_path = LOGS_DIR / filename

    logger = logging.getLogger(f"job_agent.{timestamp}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = True  # propagates up to job_agent parent for UI capture

    # File handler — DEBUG level, full detail
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    ))

    # Console handler — INFO level, clean output
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info(f"Log file: {log_path}")
    return logger, str(log_path)
