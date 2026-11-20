"""Tests for the AI report: the facts builder, the number check, the writer
with a mocked client, the no-key path, the error paths and saving ai_text.
The real API is never called: every test passes a fake client or patches
make_client."""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.report import check, config, writer
from app.report.facts import build_facts

SECTIONS = {
    "opponent_identity": "They are 2-5 and have lost 2 straight.",
    "keys_to_the_game": [{"title": "Key one", "detail": "Detail."}, {"title": "Key two", "detail": "Detail."},
                         {"title": "Key three", "detail": "Detail."}],
    "players_to_watch": [{"player": "P210", "note": "Watch him."}],
    "matchup_notes": [{"their_player": "P210", "our_defender": "P110", "note": "Fine."}],
}


def fake_response(payload=SECTIONS, stop_reason="end_turn", model="claude-sonnet-5-5"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason, model=model,
                           usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


class FakeClient:
    """Records the request and returns (or raises) what it is told."""

    def __init__(self, result):
        self.result, self.calls = result, []
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("REPORT_MODEL", raising=False)


REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, status, headers=None):
    return cls("error", response=httpx2.Response(status, request=REQUEST, headers=headers or {}), body=None)


# ---- Facts builder --------------------------------------------------------

def test_facts_builder_has_every_section(client_app, matchup_data):
    built, err = build_facts(1, 2)
    assert err is None
    f = built["facts"]
    for k in ("us", "them", "next_meeting", "last_meeting", "who_runs_the_offense", "last_game_standouts",
              "injuries", "lineups", "matchups", "key_opposing_players", "units"):
        assert k in f
    assert f["us"]["abbreviation"] == "AAA" and f["them"]["record"] == "2-5"
    assert len(f["matchups"]) == 5
    m = f["matchups"][0]
    assert {"their_player", "our_defender", "vs_his_norm_per100", "history_possessions", "small_history", "top_three_options"} <= set(m)
    # Sorted by their usage, the highest first.
    usg = [row["usg_pct"] for row in f["matchups"]]
    assert usg == sorted(usg, reverse=True)
    # 112 is Out in the fixture and listed with injuries.
    assert {"player": "P112", "status": "Out", "set_for_this_game": False} in f["injuries"]["AAA"]
    json.dumps(f)  # must be plain JSON


def test_facts_builder_applies_overrides(client_app, matchup_data):
    built, err = build_facts(1, 2, us_lineup=[110, 111, 112, 113, 114],
                             us_overrides=[{"player_id": 112, "status": "Available"}])
    assert err is None
    f = built["facts"]
    assert "P112" in f["lineups"]["AAA"]
    assert {"player": "P112", "status": "Available", "set_for_this_game": True} in f["injuries"]["AAA"]


def test_facts_builder_rejects_an_out_player(client_app, matchup_data):
    built, err = build_facts(1, 2, us_lineup=[110, 111, 112, 113, 114])
    assert built is None and "Out" in err


# ---- Number check ---------------------------------------------------------

FACTS = {
    "data_as_of": "2026-11-17", "season": "2026-27",
    "last_meeting": {"date": "2026-11-06", "season": "2025-26", "score": "124-118"},
    "them": {"record": "13-2", "streak": "W 9"},
    "players": [{"usg_pct": 39.3, "ts_pct": 64.4, "vs_his_norm_per100": -7.4, "history_possessions": 6}],
}


def flags_for(text):
    return [f["number"] for f in check.check_text(text, check.facts_vocabulary(FACTS))]


def test_check_accepts_numbers_from_the_facts():
    assert flags_for("They are 13-2 and won 9 straight, beat us 124-118, usage 39.3 on 64.4% true shooting.") == []


def test_check_ignores_sign_and_allows_small_counts_and_per_100():
    assert flags_for("Lillard is 7.4 below his norm per 100 on 6 possessions. Here are 3 keys.") == []


def test_check_allows_dates_and_seasons_in_the_facts():
    assert flags_for("They beat us on Nov 6 and on 2026-11-06. Data as of November 17, 2026. Last season, 2025-26.") == []


def test_check_flags_made_up_numbers():
    assert flags_for("He shoots 38.2% from three and scored 31 in 2024-25. Data as of Nov 18.") == ["38.2%", "31", "2024-25", "18"]


def test_check_sections_reports_where_the_number_is():
    sections = {**SECTIONS, "keys_to_the_game": [{"title": "Stop him", "detail": "He averages 27.7 points."}]}
    flags = check.check_sections(sections, FACTS)
    assert [(f["section"], f["item"], f["number"]) for f in flags] == [("Keys to the game", 1, "27.7")]


# ---- Writer, with a mocked client ----------------------------------------

def test_writer_sends_the_facts_with_the_configured_model(key):
    client = FakeClient(fake_response())
    draft = writer.generate(FACTS, client=client)
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["max_tokens"] == config.MAX_TOKENS
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "medium"
    assert call["betas"] == [config.FALLBACK_BETA] and call["fallbacks"] == "default"
    assert "Use only the facts" in call["system"]
    assert json.loads(call["messages"][0]["content"].split("\n", 1)[1]) == FACTS
    assert draft["sections"] == SECTIONS
    assert draft["prompt_version"] == config.PROMPT_VERSION
    assert draft["model"] == "claude-sonnet-5-5"
    assert draft["flags"] == [] or all("number" in f for f in draft["flags"])


def test_writer_can_switch_to_haiku(key, monkeypatch):
    monkeypatch.setenv("REPORT_MODEL", "claude-haiku-5-5")
    client = FakeClient(fake_response(model="claude-haiku-5-5"))
    writer.generate(FACTS, client=client)
    assert client.calls[0]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in client.calls[0]  # no server-side fallback on Haiku


def test_writer_ignores_an_unknown_model(key, monkeypatch):
    monkeypatch.setenv("REPORT_MODEL", "some-other-model")
    assert config.model() == "claude-sonnet-5-5"


# ---- No key ---------------------------------------------------------------

@pytest.mark.parametrize("value", ["", "your-key-here"])
def test_no_key_never_builds_a_client(monkeypatch, value):
    monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    monkeypatch.setattr(writer, "make_client", lambda: pytest.fail("a client was built without a key"))
    with pytest.raises(writer.ReportError) as err:
        writer.generate(FACTS)
    assert err.value.status == 503 and "API key" in err.value.message


def test_draft_endpoint_without_a_key(client_app, matchup_data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = client_app.post("/api/reports/draft", json={"us": 1, "them": 2})
    assert res.status_code == 503
    body = res.get_json()
    assert "ANTHROPIC_API_KEY" in body["error"]
    assert body["facts"]["us"]["abbreviation"] == "AAA"  # the facts still work
    # The rest of the app keeps working.
    assert client_app.get("/api/teams").status_code == 200
    assert client_app.post("/api/matchups", json={"us": 1, "them": 2}).status_code == 200


def test_draft_endpoint_validates_input(client_app, matchup_data):
    assert client_app.post("/api/reports/draft", data="x", content_type="text/plain").status_code == 400
    assert client_app.post("/api/reports/draft", json={"us": 1, "them": 1}).status_code == 400
    assert client_app.post("/api/reports/draft", json={"us": 1, "them": 999}).status_code == 404


def test_draft_endpoint_with_a_mocked_client(client_app, matchup_data, key, monkeypatch):
    client = FakeClient(fake_response({**SECTIONS, "opponent_identity": "They are 2-5. He scored 77."}))
    monkeypatch.setattr(writer, "make_client", lambda: client)
    res = client_app.post("/api/reports/draft", json={"us": 1, "them": 2})
    assert res.status_code == 200
    d = res.get_json()
    assert d["sections"]["opponent_identity"].startswith("They are 2-5")
    assert [f["number"] for f in d["flags"]] == ["77"]
    assert d["facts"]["them"]["record"] == "2-5"
    assert d["model"] == "claude-sonnet-5-5" and d["prompt_version"] == config.PROMPT_VERSION


# ---- Error paths ----------------------------------------------------------

@pytest.mark.parametrize("raised, status, words", [
    (status_error(anthropic.AuthenticationError, 401), 401, "rejected"),
    (status_error(anthropic.RateLimitError, 429, {"retry-after": "30"}), 429, "Try again in 30 seconds"),
    (anthropic.APITimeoutError(request=REQUEST), 504, "too long"),
    (anthropic.APIConnectionError(request=REQUEST), 502, "Could not reach"),
    (status_error(anthropic.InternalServerError, 500), 502, "on its side"),
    (status_error(anthropic.BadRequestError, 400), 502, "rejected the request"),
])
def test_api_errors_become_plain_messages(key, raised, status, words):
    with pytest.raises(writer.ReportError) as err:
        writer.generate(FACTS, client=FakeClient(raised))
    assert err.value.status == status and words in err.value.message


@pytest.mark.parametrize("response, words", [
    (fake_response(stop_reason="refusal"), "declined"),
    (fake_response(stop_reason="max_tokens"), "cut off"),
    (fake_response(payload="not json"), "could not be read"),
])
def test_bad_replies_become_plain_messages(key, response, words):
    with pytest.raises(writer.ReportError) as err:
        writer.generate(FACTS, client=FakeClient(response))
    assert err.value.status == 502 and words in err.value.message


def test_draft_endpoint_passes_the_status_through(client_app, matchup_data, key, monkeypatch):
    monkeypatch.setattr(writer, "make_client", lambda: FakeClient(status_error(anthropic.RateLimitError, 429, {"retry-after": "12"})))
    res = client_app.post("/api/reports/draft", json={"us": 1, "them": 2})
    assert res.status_code == 429 and "12 seconds" in res.get_json()["error"]


# ---- Saving the AI text ---------------------------------------------------

AI = {"sections": SECTIONS, "model": "claude-sonnet-5-5", "prompt_version": "report-v1",
      "generated_at": "2026-11-20T12:00:00Z", "flags": [], "facts": {"them": {"record": "2-5"}}, "edited": False,
      "junk": "dropped"}


def test_report_saves_and_updates_ai_text(client_app, matchup_data):
    body = {"us_team_id": 1, "them_team_id": 2, "title": "AAA vs BBB", "notes": "",
            "us_lineup": {"player_ids": [110, 111, 113, 114, 115]}, "them_lineup": {}, "ai_text": AI}
    res = client_app.post("/api/reports", json=body)
    assert res.status_code == 201
    r = res.get_json()
    assert r["ai_text"]["model"] == "claude-sonnet-5-5" and r["ai_text"]["prompt_version"] == "report-v1"
    assert "junk" not in r["ai_text"]
    edited = {**AI, "sections": {**SECTIONS, "opponent_identity": "Edited."}, "edited": True}
    res = client_app.put(f"/api/reports/{r['id']}", json={"ai_text": edited})
    assert res.status_code == 200
    got = client_app.get(f"/api/reports/{r['id']}").get_json()
    assert got["ai_text"]["sections"]["opponent_identity"] == "Edited." and got["ai_text"]["edited"] is True


@pytest.mark.parametrize("bad", ["text", {"model": "m", "prompt_version": "v"}, {"sections": {}, "model": "m"}])
def test_report_rejects_bad_ai_text(client_app, matchup_data, bad):
    body = {"us_team_id": 1, "them_team_id": 2, "title": "T", "us_lineup": {"player_ids": [110, 111, 113, 114, 115]},
            "them_lineup": {}, "ai_text": bad}
    assert client_app.post("/api/reports", json=body).status_code == 400
