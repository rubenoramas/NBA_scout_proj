"""Tests for on/off impact: the rating math, the season line across teams,
the cutoffs, and the API fields on the roster, player card and one-pager.
Totals are hand-made so every number can be checked by hand."""

import pytest

from app.db import db
from app.services.onoff import NOISE_NOTE, SHOW_MIN_POSS, SMALL_POSS, rate_line, season_line


def row(pid, team, season="2026-27", on=(1100, 1000, 1200, 1100), off=(500, 500, 480, 520), games=10):
    """One player_onoff document. on and off are (points for, his team's
    possessions, points against, opponent possessions)."""
    return {"_id": f"{pid}_{season}_{team}", "player_id": pid, "season": season, "team_id": team, "games": games,
            "on_pts_for": on[0], "on_poss_off": on[1], "on_pts_against": on[2], "on_poss_def": on[3],
            "off_pts_for": off[0], "off_poss_off": off[1], "off_pts_against": off[2], "off_poss_def": off[3]}


def test_rating_math():
    line = rate_line(row(1, 1))
    # On: 1100 / 1000 = 110.0 for, 1200 / 1100 = 109.1 against, net +0.9.
    assert line["on"] == {"off_rating": 110.0, "def_rating": 109.1, "net_rating": 0.9, "poss": 1050}
    # Off: 500 / 500 = 100.0, 480 / 520 = 92.3, net +7.7.
    assert line["off"] == {"off_rating": 100.0, "def_rating": 92.3, "net_rating": 7.7, "poss": 510}
    assert line["on_off_net"] == pytest.approx(0.9 - 7.7)
    # 510 possessions off is under 1,000: a small sample.
    assert line["shown"] is True and line["small_sample"] is True


def test_cutoffs():
    hidden = rate_line(row(1, 1, on=(250, 240, 250, 240)))
    assert hidden["shown"] is False and hidden["on_off_net"] is None and hidden["on"]["poss"] < SHOW_MIN_POSS
    big = rate_line(row(1, 1, on=(1100, 1000, 1000, 1000), off=(1100, 1000, 1100, 1000)))
    assert big["small_sample"] is False and big["on"]["poss"] >= SMALL_POSS and big["on_off_net"] == 10.0


def test_a_traded_player_sums_both_teams():
    a = row(1, 1, on=(600, 500, 500, 500), off=(200, 200, 200, 200))
    b = row(1, 2, on=(500, 500, 600, 500), off=(300, 300, 300, 300))
    line = season_line([a, b])
    # Summed: on 1100 / 1000 for, 1100 / 1000 against; off 500 / 500 both.
    assert line["on"]["net_rating"] == 0.0 and line["off"]["net_rating"] == 0.0 and line["games"] == 20
    assert [t["team_id"] for t in line["teams"]] == [1, 2] and line["teams"][0]["on"]["net_rating"] == 20.0
    assert season_line([a])["teams"] is None and season_line([]) is None


def test_player_card_and_roster_carry_on_off(client_app):
    db.meta.update_one({"_id": "seed"}, {"$set": {"last_season": "2025-26"}})
    db.player_onoff.insert_many([row(101, 1), row(101, 1, season="2025-26", on=(3300, 3000, 3000, 3000),
                                                    off=(1500, 1500, 1600, 1500))])
    o = client_app.get("/api/players/101").get_json()["onoff"]
    assert o["this_season"]["season"] == "2026-27" and o["this_season"]["on"]["off_rating"] == 110.0
    assert o["last_season"]["on_off_net"] == pytest.approx(10.0 - (-6.7))
    assert o["note"] == NOISE_NOTE and o["rules"] == {"show_min_poss": 250, "small_poss": 1000}
    # A player with no rows says so.
    assert client_app.get("/api/players/102").get_json()["onoff"]["this_season"]["empty"] is True
    players = {p["player_id"]: p for p in client_app.get("/api/teams/1/roster").get_json()["players"]}
    t = players[101]["onoff"]["this_season"]
    assert t == {"on_off_net": pytest.approx(-6.8), "shown": True, "small_sample": True, "on_poss": 1050, "off_poss": 510}
    assert players[102]["onoff"] == {"this_season": None, "last_season": None}


def test_one_pager_has_the_on_off_line_but_not_in_the_facts(client_app, matchup_data):
    from app.report.onepager import onepager_facts
    from app.services.onepager import build_page
    db.player_onoff.insert_one(row(210, 2))
    page = client_app.get("/api/players/210/onepager?vs=1").get_json()
    assert page["onoff"]["this_season"]["on_off_net"] == pytest.approx(-6.8)
    built, _ = build_page(210, 1)
    assert "onoff" not in str(onepager_facts(built).keys())
