"""Where a team gives up shots: its opponents' shots this season, by zone,
against the league average, plus the shots for a chart.

The shots collection names the shooting team, so a team's opponents' shots
are the shots in its games taken by the other team.
"""

from app.db import db
from app.services.context import current_season, involves
from app.services.players import SMALL_SAMPLE_FGA, ZONE_LABELS, ZONES, safe_div, zone_counts


def defense_shot_profile(team_id):
    season = current_season()
    game_ids = db.schedule.distinct("game_id", {**involves(team_id), "season": season, "played": True})
    match = {"game_id": {"$in": game_ids}, "team_id": {"$ne": team_id}}
    allowed = zone_counts(match)
    league = zone_counts({})
    total = sum(z["fga"] for z in allowed.values())
    league_total = sum(z["fga"] for z in league.values())
    games_with_shots = len(db.shots.distinct("game_id", match))
    zones = []
    for zone in ZONES:
        a = allowed.get(zone, {"fga": 0, "fgm": 0})
        lg = league.get(zone, {"fga": 0, "fgm": 0})
        fg, lg_fg = safe_div(a["fgm"], a["fga"]), safe_div(lg["fgm"], lg["fga"])
        share, lg_share = safe_div(a["fga"], total), safe_div(lg["fga"], league_total)
        zones.append({
            "zone": zone, "label": ZONE_LABELS[zone], "fga": a["fga"], "fgm": a["fgm"],
            "fga_per_game": a["fga"] / games_with_shots if games_with_shots else None,
            "share": share, "league_share": lg_share,
            "share_vs_league": share - lg_share if share is not None and lg_share is not None else None,
            "fg_pct": fg, "league_fg_pct": lg_fg,
            "fg_vs_league": fg - lg_fg if fg is not None and lg_fg is not None else None,
            "small_sample": a["fga"] < SMALL_SAMPLE_FGA,
        })
    shots = list(db.shots.find(match, {"_id": 0, "x": 1, "y": 1, "made": 1}))
    return {"season": season, "games": games_with_shots, "total_fga": total,
            "fg_pct": safe_div(sum(z["fgm"] for z in allowed.values()), total),
            "league_fg_pct": safe_div(sum(z["fgm"] for z in league.values()), league_total),
            "zones": zones, "shots": shots, "small_sample_fga": SMALL_SAMPLE_FGA}
