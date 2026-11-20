"""Tests for the matchup model, the assignment and POST /api/matchups."""

import pytest

from app.model.matchups import (
    K_DEFENDER, K_PAIR, K_SCORER, best_assignment, fit, pair_estimate, position_blocked, reason_line,
)

S = ["s1", "s2", "s3", "s4", "s5"]
D = ["d1", "d2", "d3", "d4", "d5"]


def brute_force(cost, usage):
    """An independent brute force: recursive search over all orderings."""
    best = [None, float("inf")]

    def go(i, used, total, picks):
        if i == 5:
            if total < best[1]:
                best[0], best[1] = dict(picks), total
            return
        for d in D:
            if d not in used:
                picks[S[i]] = d
                go(i + 1, used | {d}, total + usage[S[i]] * cost[(S[i], d)], picks)
                del picks[S[i]]
    go(0, frozenset(), 0.0, {})
    return best


def test_assignment_picks_true_best_of_120():
    # A table where the greedy choice is wrong: d1 is best against everyone,
    # but the best total spreads the defenders out.
    values = [
        [10, 11, 30, 30, 30],
        [12, 30, 13, 30, 30],
        [14, 30, 30, 15, 30],
        [16, 30, 30, 30, 17],
        [18, 19, 30, 30, 30],
    ]
    cost = {(S[i], D[j]): values[i][j] for i in range(5) for j in range(5)}
    usage = {"s1": 0.3, "s2": 0.25, "s3": 0.2, "s4": 0.15, "s5": 0.1}
    assignment, total, _ = best_assignment(S, D, lambda s, d: cost[(s, d)], usage)
    expected, expected_total = brute_force(cost, usage)
    assert total == pytest.approx(expected_total)
    assert assignment == expected


def test_position_guard_blocks_guard_on_center_without_history():
    model = {"hist": {("c1", "g1"): {"2026-27": [5.0, 25.0]}, ("c1", "g2"): {"2026-27": [2.0, 10.0]}}}
    pos = {"c1": "C", "g1": "G", "g2": "G", "f1": "F"}
    assert position_blocked(model, "c1", "g1", pos) is False   # 25 possessions of history
    assert position_blocked(model, "c1", "g2", pos) is True    # only 10
    assert position_blocked(model, "c1", "f1", pos) is False   # forward is fine
    assert position_blocked(model, "g2", "c1", pos) is True    # no history the other way


def pairs_for(rows, season="2026-27"):
    return [{"season": season, "off_id": o, "def_id": d, "poss": p, "pts": pts} for o, d, p, pts in rows]


def test_shrinkage_at_the_edges():
    rows = [("A", "X", 400, 120), ("B", "X", 400, 80), ("A", "Y", 400, 100), ("B", "Y", 400, 100)]
    model = fit(pairs_for(rows), {}, "2026-27", {})
    league = 400 / 1600
    # Scorer A: 220 points on 800 possessions, shrunk with k = 200
    assert model["B"]["A"] == pytest.approx((220 + K_SCORER * league) / (800 + K_SCORER))
    # A scorer with no possessions gets the league rate
    assert pair_estimate(model, "nobody", "X")["baseline"] == pytest.approx(model["league_all"])
    # A defender with no possessions has no effect
    assert pair_estimate(model, "A", "Z")["defender_effect"] == 0
    # No pair history: the estimate is exactly the prior
    e = pair_estimate(model, "A", "Z")
    assert e["history_poss"] == 0 and e["expected"] == pytest.approx(e["prior"])
    # Defender X allowed 200 vs an expected sum; shrink with k = 300 toward 0
    expected_x = 400 * model["B"]["A"] + 400 * model["B"]["B"]
    assert model["D"]["X"] == pytest.approx((200 - expected_x) / (800 + K_DEFENDER))


def test_huge_history_approaches_pair_rate():
    rows = [("A", "X", 100000, 50000), ("A", "Y", 100, 25), ("B", "X", 100, 25)]
    model = fit(pairs_for(rows), {}, "2026-27", {})
    e = pair_estimate(model, "A", "X")
    assert e["expected"] == pytest.approx(0.5, abs=0.001)
    # And thin history barely moves it: 10 possessions count 10 / (10 + 50)
    thin = fit(pairs_for([("A", "X", 10, 10), ("A", "Y", 1000, 250), ("B", "X", 1000, 250)]), {}, "2026-27", {})
    e = pair_estimate(thin, "A", "X")
    assert e["expected"] == pytest.approx((1.0 * 10 + K_PAIR * e["prior"]) / (10 + K_PAIR))


def test_reason_line_leads_with_largest_part():
    est = {"baseline": 0.30, "defender_effect": -0.06, "size": 0.002, "history_poss": 4, "history_rate": 0.2,
           "history_shift": -0.005, "expected": 0.237, "gaps": {"height_in": 2, "weight_10lb": 0, "wingspan_in": 0}}
    text = reason_line(est, "Star", "Stopper")
    assert text.startswith("Star norm 30.0; Stopper allows 6.0 fewer than expected")
    assert text.endswith("Expected 23.7 per 100.")


# ---- API ------------------------------------------------------------------


def test_matchups_default_lineups_exclude_out(client_app, matchup_data):
    res = client_app.post("/api/matchups", json={"us": 1, "them": 2})
    assert res.status_code == 200
    body = res.get_json()
    ours = [p["player_id"] for p in body["us_lineup"]]
    assert 112 not in ours and len(ours) == 5 and 115 in ours   # Out starter replaced
    assert body["us_default"] is True
    assert len(body["rows"]) == 5
    usg = [r["usg_pct"] for r in body["rows"]]
    assert usg == sorted(usg, reverse=True)                       # sorted by USG%
    for r in body["rows"]:
        assert r["assigned"]["defender_id"] in ours
        assert len(r["top_three"]) == 3
        assert all(o["defender_id"] != 112 for o in r["top_three"])
        assert r["assigned"]["vs_norm_per100"] == pytest.approx(
            r["assigned"]["expected_per100"] - r["assigned"]["norm_per100"], abs=0.11)
    assigned = [r["assigned"]["defender_id"] for r in body["rows"]]
    assert len(set(assigned)) == 5


def test_matchups_validation(client_app, matchup_data):
    post = lambda payload: client_app.post("/api/matchups", json=payload)  # noqa: E731
    assert post({"us": 1}).status_code == 400
    assert post({"us": 1, "them": 1}).status_code == 400
    assert post({"us": 1, "them": 999}).status_code == 404
    res = post({"us": 1, "them": 2, "us_lineup": [110, 111, 112, 113, 114]})
    assert res.status_code == 400 and "Out" in res.get_json()["error"]
    res = post({"us": 1, "them": 2, "us_lineup": [110, 111, 113]})
    assert res.status_code == 400 and "exactly 5" in res.get_json()["error"]
    res = post({"us": 1, "them": 2, "us_lineup": [110, 111, 113, 114, 210]})
    assert res.status_code == 400 and "not on" in res.get_json()["error"]
    res = post({"us": 1, "them": 2, "us_lineup": [110, 111, 113, 114, 115]})
    assert res.status_code == 200 and res.get_json()["us_default"] is False
    assert client_app.post("/api/matchups", data="nope", content_type="text/plain").status_code == 400


def test_defender_effect_is_relative_to_position():
    # Two centers allow 40 per 100 and two guards 20, against the same
    # scorers. Without the adjustment every guard looks far better; with it,
    # each defender is measured against his own position and the average
    # defender at each position has an effect near 0.
    rows = []
    for d, rate in (("C1", 0.40), ("C2", 0.40), ("G1", 0.20), ("G2", 0.20)):
        for o in ("A", "B"):
            rows.append((o, d, 500, 500 * rate))
    bios = {"C1": {"position": "C"}, "C2": {"position": "C"}, "G1": {"position": "G"}, "G2": {"position": "G"}}
    raw = fit(pairs_for(rows), {}, "2026-27", bios, position_relative=False)
    rel = fit(pairs_for(rows), {}, "2026-27", bios, position_relative=True)
    assert raw["D"]["G1"] < -0.05 and raw["D"]["C1"] > 0.05
    for d in ("C1", "C2", "G1", "G2"):
        assert rel["D"][d] == pytest.approx(0.0, abs=1e-9)
    assert rel["position_avg"]["C"] > 0 > rel["position_avg"]["G"]


def test_k_pair_setting_is_used():
    rows = [("A", "X", 40, 20), ("A", "Y", 1000, 250), ("B", "X", 1000, 250)]
    for k in (50, 100, 200):
        m = fit(pairs_for(rows), {}, "2026-27", {}, k_pair=k)
        e = pair_estimate(m, "A", "X")
        assert e["expected"] == pytest.approx((0.5 * 40 + k * e["prior"]) / (40 + k))
