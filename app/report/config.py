"""Settings for the AI report. Change the model here (or with REPORT_MODEL in
.env); only the two models below are accepted."""

import os
from pathlib import Path

ALLOWED_MODELS = ["claude-sonnet-5-5", "claude-haiku-5-5"]
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 4000
EFFORT = "medium"
TIMEOUT_SECONDS = 90
MAX_RETRIES = 2
# Bump this whenever system_prompt.md changes, so saved reports record which
# prompt wrote them.
PROMPT_VERSION = "report-v2"
# Refusal fallback: on Sonnet 5.5 the API reruns a declined request on a
# fallback model it picks. Haiku 5.5 has no server-side fallback.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")


def model():
    chosen = os.environ.get("REPORT_MODEL", DEFAULT_MODEL).strip()
    return chosen if chosen in ALLOWED_MODELS else DEFAULT_MODEL


def system_prompt():
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def api_key_set():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return bool(key) and key != "your-key-here"
