"""Send the facts to Claude and get back the four report sections.

The model sees only the system prompt (system_prompt.md) and the facts. The
reply is constrained to JSON by structured outputs, then every number in it
is checked against the facts (check.py).
"""

import json
from datetime import datetime, timezone

import anthropic

from app.report import config
from app.report.check import check_sections

NO_KEY_MESSAGE = ("AI reports need an API key. Add ANTHROPIC_API_KEY to the .env file and restart the app. "
                  "Everything else works without it.")

# The four sections, as a JSON schema for structured outputs.
SCHEMA = {
    "type": "object",
    "properties": {
        "opponent_identity": {"type": "string"},
        "keys_to_the_game": {
            "type": "array",
            "items": {"type": "object", "properties": {"title": {"type": "string"}, "detail": {"type": "string"}},
                      "required": ["title", "detail"], "additionalProperties": False},
        },
        "players_to_watch": {
            "type": "array",
            "items": {"type": "object", "properties": {"player": {"type": "string"}, "note": {"type": "string"}},
                      "required": ["player", "note"], "additionalProperties": False},
        },
        "matchup_notes": {
            "type": "array",
            "items": {"type": "object",
                      "properties": {"their_player": {"type": "string"}, "our_defender": {"type": "string"},
                                     "note": {"type": "string"}},
                      "required": ["their_player", "our_defender", "note"], "additionalProperties": False},
        },
    },
    "required": ["opponent_identity", "keys_to_the_game", "players_to_watch", "matchup_notes"],
    "additionalProperties": False,
}


class ReportError(Exception):
    """A plain-language error with the HTTP status the API should answer."""

    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def make_client():
    return anthropic.Anthropic(timeout=config.TIMEOUT_SECONDS, max_retries=config.MAX_RETRIES)


def call_model(client, model, facts):
    kwargs = {
        "model": model,
        "max_tokens": config.MAX_TOKENS,
        "system": config.system_prompt(),
        "messages": [{"role": "user", "content": "Facts:\n" + json.dumps(facts, ensure_ascii=False, indent=1)}],
        "output_config": {"effort": config.EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
    }
    if model == "claude-sonnet-5-5":
        # Refusal fallback: the API reruns a declined request on a fallback model.
        return client.beta.messages.create(**kwargs, betas=[config.FALLBACK_BETA], fallbacks="default")
    return client.messages.create(**kwargs)


def generate(facts, client=None):
    """Returns a draft: {sections, flags, model, prompt_version, generated_at, usage}.
    Raises ReportError with a plain message on any failure."""
    if not config.api_key_set():
        raise ReportError(NO_KEY_MESSAGE, 503)
    model = config.model()
    client = client or make_client()
    try:
        response = call_model(client, model, facts)
    except anthropic.AuthenticationError:
        raise ReportError("The API key in .env was rejected. Check that it is correct and still active.", 401) from None
    except anthropic.PermissionDeniedError:
        raise ReportError("The API key does not have access to this model.", 403) from None
    except anthropic.RateLimitError as err:
        wait = err.response.headers.get("retry-after") if getattr(err, "response", None) is not None else None
        raise ReportError(f"Too many requests to the AI service. Try again in {wait or 'a few'} seconds.", 429) from None
    except anthropic.APITimeoutError:
        raise ReportError("The AI service took too long to answer. Try again.", 504) from None
    except anthropic.APIConnectionError:
        raise ReportError("Could not reach the AI service. Check the internet connection and try again.", 502) from None
    except anthropic.APIStatusError as err:
        if err.status_code >= 500:
            raise ReportError("The AI service had a problem on its side. Try again in a moment.", 502) from None
        raise ReportError(f"The AI service rejected the request ({err.status_code}).", 502) from None

    if response.stop_reason == "refusal":
        raise ReportError("The model declined to write this report. Try again, or write the notes by hand.", 502)
    if response.stop_reason == "max_tokens":
        raise ReportError("The report was cut off before it finished. Try again.", 502)
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    try:
        sections = json.loads(text) if text else None
    except json.JSONDecodeError:
        sections = None
    if not isinstance(sections, dict):
        raise ReportError("The AI reply could not be read. Try again.", 502)

    usage = getattr(response, "usage", None)
    return {
        "sections": sections,
        "flags": check_sections(sections, facts),
        "model": getattr(response, "model", model) or model,
        "requested_model": model,
        "prompt_version": config.PROMPT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "usage": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None)} if usage else None,
    }
