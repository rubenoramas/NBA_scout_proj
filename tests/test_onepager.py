"""Tests for the player one-pager: the page endpoint, the facts builder, the
"How to guard him" text with a mocked client, the cache (hit and miss), the
no-key path and error paths. The real API is never called: every test that
writes text patches writer.make_client with a fake client."""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.db import db
from app.report import config, writer
from app.report.onepager import onepager_facts
from app.services.matchups import best_defenders
from app.services.onepager import build_page

# Opposing player 210 (BBB, a guard) against us, AAA (team 1). Players come
# from the matchup_data fixture: AAA 110-115, BBB 210-215; 112 is Out.
URL = "/api/players/210/onepager?vs=1"
NOTE_URL = "/api/players/210/onepager/note?vs=1"
GOOD_TEXT = "P113 is the best option. He ends 40.0% of his possessions in isolation at 1.10 points per possession."


@pytest.fixture
def onepager_data(matchup_data):
    """Play types and assists for player 210, on top of the matchup fixture."""
    db.play_type_mix.insert_many([
        # 210: 100 possessions in all; isolation 40, spot up 30, cut 10 (a small sample).
        {"_id": "210_2026-27_Isolation", "player_id": 210, "season": "2026-27", "play_type": "Isolation",
         "poss": 40, "pts": 44, "fga": 35, "fgm": 15, "tov_poss": 4, "total_poss": 100},
        {"_id": "210_2026-27_Spotup", "player_id": 210, "season": "2026-27", "play_type": "Spotup",
         "poss": 30, "pts": 27, "fga": 30, "fgm": 10, "tov_poss": 1, "total_poss": 100},
        {"_id": "210_2026-27_Cut", "player_id": 210, "season": "2026-27", "play_type": "Cut",
         "poss": 10, "pts": 14, "fga": 9, "fgm": 7, "tov_poss": 0, "total_poss": 100},
        # Another player, so the league PPP for isolation is (44 + 36) / (40 + 40) = 1.0.
        {"_id": "211_2026-27_Isolation", "player_id": 211, "season": "2026-27", "play_type": "Isolation",
         "poss": 40, "pts": 36, "fga": 35, "fgm": 15, "tov_poss": 4, "total_poss": 80},
    ])
    db.assist_pairs.insert_many([
        {"_id": "2026-27_210_211", "season": "2026-27", "scorer_id": 210, "passer_id": 211, "ast": 12, "ast_fg3": 5,
         "scorer_fgm": 50, "scorer_assisted": 30},
        {"_id": "2026-27_210_212", "season": "2026-27", "scorer_id": 210, "passer_id": 212, "ast": 9, "ast_fg3": 1,
         "scorer_fgm": 50, "scorer_assisted": 30},
        {"_id": "2026-27_210_213", "season": "2026-27", "scorer_id": 210, "passer_id": 213, "ast": 6, "ast_fg3": 0,
         "scorer_fgm": 50, "scorer_assisted": 30},
        {"_id": "2026-27_210_214", "season": "2026-27", "scorer_id": 210, "passer_id": 214, "ast": 3, "ast_fg3": 0,
         "scorer_fgm": 50, "scorer_assisted": 30},
    ])
    yield


def reply(text=GOOD_TEXT, stop_reason="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps({"how_to_guard": text}))],
                           stop_reason=stop_reason, model="claude-sonnet-5-5",
                           usage=SimpleNamespace(input_tokens=900, output_tokens=80))


class FakeClient:
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


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(writer, "make_client", lambda: pytest.fail("a client was built without a key"))


# ---- Page data ------------------------------------------------------------

def test_page_has_every_part(client_app, onepager_data, no_key):
    res = client_app.get(URL)
    assert res.status_code == 200
    p = res.get_json()
    for k in ("player", "team", "us", "injury", "season", "usage", "attributes", "defenders", "shots",
              "play_types", "feeders", "data_as_of", "note"):
        assert k in p
    assert p["player"]["player_name"] == "P210" and p["us"]["abbreviation"] == "AAA"
    assert p["data_as_of"] == "2026-11-10"
    # Best three defenders: three, lowest expected first, nobody Out (112).
    opts = p["defenders"]["options"]
    assert len(opts) == 3
    assert [o["expected_per100"] for o in opts] == sorted(o["expected_per100"] for o in opts)
    assert 112 not in [o["defender_id"] for o in opts]
    # Play types: most used first, share of his 100 possessions, league PPP.
    rows = p["play_types"]["rows"]
    assert [r["play_type"] for r in rows] == ["Isolation", "Spotup", "Cut"]
    assert rows[0]["label"] == "Isolation" and rows[0]["share"] == pytest.approx(0.4)
    assert rows[0]["ppp"] == pytest.approx(1.1) and rows[0]["league_ppp"] == pytest.approx(1.0)
    assert rows[2]["small_sample"] is True and rows[0]["small_sample"] is False
    # Who feeds him: top three passers, share of his 30 assisted makes.
    f = p["feeders"]
    assert f["fgm"] == 50 and f["assisted_fgm"] == 30 and f["assisted_share"] == pytest.approx(0.6)
    assert [x["player_id"] for x in f["passers"]] == [211, 212, 213]
    assert f["passers"][0]["share_of_assisted"] == pytest.approx(0.4) and f["passers"][0]["now_with"] is None
    # No key and nothing cached: the page says so and calls nobody.
    assert p["note"]["key_set"] is False and p["note"]["cached"] is None
    assert "API key" in p["note"]["no_key_message"]


def test_page_marks_a_traded_passer(client_app, onepager_data):
    db.players.update_one({"_id": 211}, {"$set": {"team_id": 3, "team_abbr": "CCC"}})
    p = client_app.get(URL).get_json()
    assert p["feeders"]["passers"][0]["now_with"] == "CCC"


def test_play_types_fall_back_to_last_season(client_app, onepager_data):
    db.meta.update_one({"_id": "seed"}, {"$set": {"last_season": "2025-26"}})
    db.play_type_mix.insert_one({"_id": "212_2025-26_Postup", "player_id": 212, "season": "2025-26",
                                 "play_type": "Postup", "poss": 50, "pts": 50, "total_poss": 200})
    page, err = build_page(212, 1)
    assert err is None
    assert page["play_types"]["last_season_only"] is True and page["play_types"]["season"] == "2025-26"
    assert page["play_types"]["rows"][0]["label"] == "Post up"


@pytest.mark.parametrize("url, status, words", [
    ("/api/players/210/onepager", 400, "missing"),
    ("/api/players/210/onepager?vs=abc", 400, "must be a number"),
    ("/api/players/abc/onepager?vs=1", 400, "must be a number"),
    ("/api/players/999/onepager?vs=1", 404, "No player"),
    ("/api/players/210/onepager?vs=99", 404, "No team"),
    ("/api/players/210/onepager?vs=2", 400, "plays for BBB"),
])
def test_page_validates_input(client_app, onepager_data, url, status, words):
    res = client_app.get(url)
    assert res.status_code == status and words in res.get_json()["error"]


def test_best_defenders_skip_out_players_and_guard_center_pairs(client_app, onepager_data):
    # 214 is a center. Cut our guards' (110, 111, 115) history with him to 5
    # possessions, under the 20 the position guard needs. 112 is Out.
    db.matchup_pairs.update_many({"off_id": 214, "def_id": {"$in": [110, 111, 115]}}, {"$set": {"poss": 5.0}})
    import app.services.matchups as svc
    svc._cache.update(key=None, model=None)
    ids = [o["defender_id"] for o in best_defenders(1, 214)["options"]]
    assert not set(ids) & {110, 111, 115, 112}


# ---- Facts builder ----------------------------------------------------------

def test_facts_builder(client_app, onepager_data):
    page, err = build_page(210, 1)
    assert err is None
    f = onepager_facts(page)
    for k in ("data_as_of", "units", "player", "guarded_by_team", "season_line", "ratings_0_to_99", "badges",
              "best_defenders", "favorite_shots", "play_types", "who_feeds_him"):
        assert k in f
    assert f["player"]["name"] == "P210" and f["guarded_by_team"] == "AAA"
    assert len(f["best_defenders"]) == 3
    assert {"defender", "vs_his_norm_per100", "history_possessions", "small_history"} <= set(f["best_defenders"][0])
    iso = f["play_types"]["types"][0]
    # Rounded once, as shown on the page: percent numbers and 2-digit PPP.
    assert iso == {"play_type": "Isolation", "possessions": 40, "share_pct": 40.0, "points_per_possession": 1.1,
                   "league_points_per_possession": 1.0, "small_sample": False}
    assert f["who_feeds_him"]["assisted_pct"] == 60.0
    assert f["who_feeds_him"]["top_passers"][0] == {"passer": "P211", "assists": 12, "assists_on_threes": 5,
                                                    "share_of_assisted_pct": 40.0, "traded_since": False}
    # No shots and no ratings in the fixture: those parts are left out, not invented.
    assert f["favorite_shots"] is None and f["ratings_0_to_99"] is None
    json.dumps(f)  # must be plain JSON


# ---- How to guard him: no key, miss, hit -------------------------------------

def test_note_without_a_key(client_app, onepager_data, no_key):
    res = client_app.post(NOTE_URL)
    assert res.status_code == 503 and "API key" in res.get_json()["error"]
    assert db.onepager_notes.count_documents({}) == 0


def test_note_cache_miss_then_hit(client_app, onepager_data, key, monkeypatch):
    fake = FakeClient(reply())
    monkeypatch.setattr(writer, "make_client", lambda: fake)
    first = client_app.post(NOTE_URL)
    assert first.status_code == 201
    body = first.get_json()
    assert body["cached"] is False and body["note"]["text"] == GOOD_TEXT and body["note"]["flags"] == []
    assert body["note"]["prompt_version"] == config.ONEPAGER_PROMPT_VERSION
    # The request: the one-pager prompt, its schema, and only the facts.
    call = fake.calls[0]
    assert call["system"] == config.onepager_prompt()
    assert call["output_config"]["format"]["schema"]["required"] == ["how_to_guard"]
    assert call["messages"][0]["content"].startswith("Facts:\n")
    # Stored once, under the four-part key.
    doc = db.onepager_notes.find_one()
    assert (doc["player_id"], doc["vs_team_id"], doc["data_as_of"], doc["prompt_version"]) == \
        (210, 1, "2026-11-10", config.ONEPAGER_PROMPT_VERSION)

    # Opening the page again: GET shows the cached text, POST answers from
    # MongoDB, and the API is not called again.
    page = client_app.get(URL).get_json()
    assert page["note"]["cached"]["text"] == GOOD_TEXT
    again = client_app.post(NOTE_URL)
    assert again.status_code == 200 and again.get_json()["cached"] is True
    assert len(fake.calls) == 1
    assert db.onepager_notes.count_documents({}) == 1


def test_cached_text_still_shows_without_a_key(client_app, onepager_data, key, monkeypatch):
    monkeypatch.setattr(writer, "make_client", lambda: FakeClient(reply()))
    client_app.post(NOTE_URL)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    page = client_app.get(URL).get_json()
    assert page["note"]["key_set"] is False and page["note"]["cached"]["text"] == GOOD_TEXT
    assert client_app.post(NOTE_URL).status_code == 200


@pytest.mark.parametrize("change", [
    ("meta", {"data_as_of": "2026-11-11"}),   # new data
    ("version", "onepager-v999"),             # new prompt
    ("vs", 3),                                # another team guarding him
])
def test_each_key_part_misses_the_cache(client_app, onepager_data, key, monkeypatch, change):
    fake = FakeClient(reply())
    monkeypatch.setattr(writer, "make_client", lambda: fake)
    assert client_app.post(NOTE_URL).status_code == 201
    what, value = change
    url = NOTE_URL
    if what == "meta":
        db.meta.update_one({"_id": "seed"}, {"$set": value})
    elif what == "version":
        monkeypatch.setattr(config, "ONEPAGER_PROMPT_VERSION", value)
    else:
        url = f"/api/players/210/onepager/note?vs={value}"
    assert client_app.post(url).status_code == 201
    assert len(fake.calls) == 2 and db.onepager_notes.count_documents({}) == 2


def test_made_up_numbers_are_flagged(client_app, onepager_data, key, monkeypatch):
    monkeypatch.setattr(writer, "make_client", lambda: FakeClient(reply("He shoots 47.9% from the corner.")))
    note = client_app.post(NOTE_URL).get_json()["note"]
    assert [f["number"] for f in note["flags"]] == ["47.9%"]
    assert note["flags"][0]["section"] == "How to guard him"


REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize("result, status, words", [
    (anthropic.RateLimitError("e", response=httpx2.Response(429, request=REQUEST, headers={"retry-after": "9"}), body=None),
     429, "9 seconds"),
    (reply(stop_reason="refusal"), 502, "declined to write this note"),
    (reply(stop_reason="max_tokens"), 502, "note was cut off"),
])
def test_errors_are_plain_and_not_cached(client_app, onepager_data, key, monkeypatch, result, status, words):
    monkeypatch.setattr(writer, "make_client", lambda: FakeClient(result))
    res = client_app.post(NOTE_URL)
    assert res.status_code == status and words in res.get_json()["error"]
    assert db.onepager_notes.count_documents({}) == 0


def test_one_pager_pages_render(client_app):
    assert client_app.get("/onepager/210?vs=1").status_code == 200
    assert client_app.get("/onepagers?vs=1&ids=210,211").status_code == 200
