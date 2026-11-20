"""Tests for saved lineups and reports: create, read, list, update, delete,
validation errors, 404s, and injury overrides changing the matchups."""

import pytest

BAD_ID = "not-an-id"
MISSING_ID = "64b000000000000000000000"
LINEUP = [110, 111, 113, 114, 115]  # 112 is Out in the fixture


def make_lineup(client_app, name="Starters", players=None, overrides=None):
    return client_app.post("/api/lineups", json={"team_id": 1, "name": name, "player_ids": players or LINEUP,
                                                 "overrides": overrides or []})


# ---- Lineups ---------------------------------------------------------------


def test_lineup_create_read_list_update_delete(client_app, matchup_data):
    res = make_lineup(client_app)
    assert res.status_code == 201
    created = res.get_json()
    lid = created["id"]
    assert len(lid) == 24 and created["player_ids"] == LINEUP and created["name"] == "Starters"
    assert created["created_at"] == created["updated_at"]

    one = client_app.get(f"/api/lineups/{lid}")
    assert one.status_code == 200 and one.get_json()["name"] == "Starters"

    make_lineup(client_app, name="Small ball")
    names = [l["name"] for l in client_app.get("/api/lineups?team=1").get_json()["lineups"]]
    assert names == ["Small ball", "Starters"]  # newest first
    assert client_app.get("/api/lineups?team=2").get_json()["lineups"] == []

    res = client_app.put(f"/api/lineups/{lid}", json={"name": "Closing five"})
    assert res.status_code == 200 and res.get_json()["name"] == "Closing five"
    assert res.get_json()["player_ids"] == LINEUP
    assert res.get_json()["updated_at"] >= created["updated_at"]

    res = client_app.put(f"/api/lineups/{lid}", json={"player_ids": [110, 111, 112, 113, 114],
                                                     "overrides": [{"player_id": 112, "status": "Probable"}]})
    assert res.status_code == 200 and 112 in res.get_json()["player_ids"]

    assert client_app.delete(f"/api/lineups/{lid}").status_code == 204
    assert client_app.get(f"/api/lineups/{lid}").status_code == 404
    assert client_app.delete(f"/api/lineups/{lid}").status_code == 404


def test_lineup_validation(client_app, matchup_data):
    cases = [
        ({"team_id": 1, "name": "", "player_ids": LINEUP}, "name"),
        ({"team_id": 1, "name": "x" * 61, "player_ids": LINEUP}, "at most"),
        ({"team_id": 1, "name": "A", "player_ids": LINEUP[:4]}, "exactly 5"),
        ({"team_id": 1, "name": "A", "player_ids": [110, 110, 111, 113, 114]}, "twice"),
        ({"team_id": 1, "name": "A", "player_ids": [110, 111, 113, 114, 210]}, "not on this team"),
        ({"team_id": 1, "name": "A", "player_ids": [110, 111, 112, 113, 114]}, "Out"),
        ({"team_id": 1, "name": "A", "player_ids": LINEUP, "overrides": [{"player_id": 110, "status": "Hurt"}]}, "not a status"),
        ({"team_id": 1, "name": "A", "player_ids": LINEUP, "overrides": [{"player_id": 210, "status": "Out"}]}, "not on this team"),
        ({"name": "A", "player_ids": LINEUP}, "team id"),
    ]
    for body, words in cases:
        res = client_app.post("/api/lineups", json=body)
        assert res.status_code == 400, body
        assert words in res.get_json()["error"], (body, res.get_json())
    assert client_app.post("/api/lineups", json={"team_id": 999, "name": "A", "player_ids": LINEUP}).status_code == 404
    assert client_app.post("/api/lineups", data="x", content_type="text/plain").status_code == 400


def test_lineup_override_lets_an_out_player_play(client_app, matchup_data):
    res = make_lineup(client_app, players=[110, 111, 112, 113, 114],
                      overrides=[{"player_id": 112, "status": "Available"}])
    assert res.status_code == 201
    assert res.get_json()["overrides"] == [{"player_id": 112, "status": "Available"}]


def test_lineup_ids_and_updates(client_app, matchup_data):
    assert client_app.get(f"/api/lineups/{BAD_ID}").status_code == 400
    assert client_app.get(f"/api/lineups/{MISSING_ID}").status_code == 404
    assert client_app.put(f"/api/lineups/{MISSING_ID}", json={"name": "A"}).status_code == 404
    assert client_app.delete(f"/api/lineups/{BAD_ID}").status_code == 400
    lid = make_lineup(client_app).get_json()["id"]
    assert client_app.put(f"/api/lineups/{lid}", json={}).status_code == 400
    assert client_app.put(f"/api/lineups/{lid}", json={"player_ids": [110, 111]}).status_code == 400
    assert client_app.get("/api/lineups?team=abc").status_code == 400


# ---- Overrides change the matchups ------------------------------------------


def test_override_changes_matchup_result(client_app, matchup_data):
    base = client_app.post("/api/matchups", json={"us": 1, "them": 2}).get_json()
    assert 112 not in [p["player_id"] for p in base["us_lineup"]]
    # Overriding the Out starter to Available puts him back in the default five
    back = client_app.post("/api/matchups", json={"us": 1, "them": 2,
                                                  "us_overrides": [{"player_id": 112, "status": "Available"}]}).get_json()
    assert 112 in [p["player_id"] for p in back["us_lineup"]]
    assert back["us_lineup"] != base["us_lineup"]
    # Marking a starter Out takes him out of the default five
    out = client_app.post("/api/matchups", json={"us": 1, "them": 2,
                                                 "us_overrides": [{"player_id": 110, "status": "Out"}]}).get_json()
    assert 110 not in [p["player_id"] for p in out["us_lineup"]]
    # Doubtful players are skipped by the default lineup, but can be picked by hand
    doubt = client_app.post("/api/matchups", json={"us": 1, "them": 2,
                                                   "us_overrides": [{"player_id": 111, "status": "Doubtful"}]}).get_json()
    assert 111 not in [p["player_id"] for p in doubt["us_lineup"]]
    hand = client_app.post("/api/matchups", json={"us": 1, "them": 2, "us_lineup": [110, 111, 113, 114, 115],
                                                  "us_overrides": [{"player_id": 111, "status": "Doubtful"}]})
    assert hand.status_code == 200
    statuses = {p["player_id"]: p["status"] for p in hand.get_json()["us_lineup"]}
    assert statuses[111] == "Doubtful"


# ---- Reports ---------------------------------------------------------------


def make_report(client_app, **extra):
    body = {"us_team_id": 1, "them_team_id": 2, "title": "AAA vs BBB", "notes": "Run them off the line.",
            "us_lineup": {"player_ids": LINEUP, "overrides": []}, "them_lineup": {"overrides": []}}
    body.update(extra)
    return client_app.post("/api/reports", json=body)


def test_report_create_read_list_update_delete(client_app, matchup_data):
    res = make_report(client_app, game_id="0022600005")
    assert res.status_code == 201
    r = res.get_json()
    rid = r["id"]
    assert r["title"] == "AAA vs BBB" and r["notes"] == "Run them off the line."
    assert r["ai_text"] is None
    assert r["game_id"] == "0022600005" and r["game_date"] == "2026-12-01"
    assert r["us_lineup"]["player_ids"] == LINEUP
    assert len(r["them_lineup"]["player_ids"]) == 5      # default lineup filled in
    assert len(r["matchup_snapshot"]["rows"]) == 5
    assert r["us_abbr"] == "AAA" and r["them_abbr"] == "BBB"

    full = client_app.get(f"/api/reports/{rid}").get_json()
    assert full["matchup_snapshot"] == r["matchup_snapshot"]

    make_report(client_app, title="Second")
    listed = client_app.get("/api/reports").get_json()["reports"]
    assert [x["title"] for x in listed] == ["Second", "AAA vs BBB"]     # newest first
    assert "matchup_snapshot" not in listed[0]                          # the list stays light

    res = client_app.put(f"/api/reports/{rid}", json={"title": "Game plan", "notes": "Switch everything."})
    assert res.status_code == 200
    assert res.get_json()["title"] == "Game plan" and res.get_json()["notes"] == "Switch everything."

    assert client_app.delete(f"/api/reports/{rid}").status_code == 204
    assert client_app.get(f"/api/reports/{rid}").status_code == 404
    assert client_app.delete(f"/api/reports/{rid}").status_code == 404


def test_report_validation(client_app, matchup_data):
    assert make_report(client_app, title="").status_code == 400
    assert make_report(client_app, title="x" * 121).status_code == 400
    assert make_report(client_app, notes="x" * 10001).status_code == 400
    assert make_report(client_app, them_team_id=1).status_code == 400
    assert make_report(client_app, them_team_id=999).status_code == 404
    res = make_report(client_app, us_lineup={"player_ids": [110, 111, 112, 113, 114]})
    assert res.status_code == 400 and "Out" in res.get_json()["error"]
    assert client_app.get(f"/api/reports/{BAD_ID}").status_code == 400
    assert client_app.get(f"/api/reports/{MISSING_ID}").status_code == 404
    assert client_app.put(f"/api/reports/{MISSING_ID}", json={"title": "A"}).status_code == 404
    rid = make_report(client_app).get_json()["id"]
    res = client_app.put(f"/api/reports/{rid}", json={"matchup_snapshot": {}})
    assert res.status_code == 400 and "cannot be changed" in res.get_json()["error"]
    assert client_app.put(f"/api/reports/{rid}", json={}).status_code == 400
    assert client_app.put(f"/api/reports/{rid}", json={"title": " "}).status_code == 400


def test_report_snapshot_does_not_change_with_the_data(client_app, matchup_data):
    import app.services.matchups as svc
    from app.db import db

    rid = make_report(client_app).get_json()["id"]
    before = client_app.get(f"/api/reports/{rid}").get_json()["matchup_snapshot"]
    # The data changes: every pair now scores far more, and the model refits
    db.matchup_pairs.update_many({}, {"$inc": {"pts": 20}})
    svc._cache.update(key=None, model=None)
    live = client_app.post("/api/matchups", json={"us": 1, "them": 2, "us_lineup": LINEUP}).get_json()
    assert live["rows"][0]["assigned"]["expected_per100"] != before["rows"][0]["assigned"]["expected_per100"]
    after = client_app.get(f"/api/reports/{rid}").get_json()["matchup_snapshot"]
    assert after == before
