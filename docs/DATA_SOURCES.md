# Data sources, verified

Results of `pulls/test_pulls.R`, run on Nov 16, 2026 from campus Wi-Fi with R 4.6.2, hoopR 3.2.0 and the arrow package. This file is the source of truth for what data exists and what the columns are called. Update it whenever the pull test is rerun.

## Three routes, in order of preference

1. **Pre-pulled NBA stats files** (`load_nba_stats_*`). hoopR publishes ready-made copies of NBA stats tables as files on GitHub. One file holds a whole season, each loads in about a second, and they work on any network. This is the main route.
2. **ESPN feeds** (`load_nba_*`, `espn_nba_*`). Work on any network.
3. **The live NBA stats site** (`nba_*`). Gives no answer from campus Wi-Fi (timeout, 0 bytes). Only reachable from a phone hotspot or home internet. Used only for the short list at the bottom, and the app must work without it.

## Rules that are easy to get wrong

- `load_nba_stats_*(seasons = ...)` takes the season's START year. 2026 means 2026-27. Use `most_recent_nba_stats_season()`.
- `load_nba_*(seasons = ...)` (ESPN) takes the END year. 2027 means 2026-27. Use `most_recent_nba_season()`.
- Live `nba_*()` functions take a string such as "2026-27" and default to LAST season. Always pass `season`.
- Most `load_nba_stats_*` files are Parquet. They return an empty table with a warning unless the arrow package is installed.

## Route 1: pre-pulled files (all passed unless noted)

| Data | Call | Rows, this season | Key columns |
| --- | --- | --- | --- |
| Shots | `load_nba_stats_shots(seasons = 2026)` | 34,685 (last season: 234,876) | game_id, period, clock, team_id, person_id, player_name, action_type, sub_type, shot_result, shot_value, shot_distance, x_legacy, y_legacy, description |
| Play types | `load_nba_stats_synergy(seasons = 2026)` | 4,689 | player_id, team_id, play_type, type_grouping, percentile, poss_pct, ppp, poss, pts, fga, efg_pct, tov_poss_pct, season_type, per_mode |
| Matchups per game | `load_nba_stats_game_matchups(seasons = 2026)` | 37,954 covering 187 games, 50 columns (last season: 257,854 covering 1,322 games) | game_id, off_team_id, def_team_id, off_person_id, def_person_id, matchup_minutes_sort, partial_possessions, switches_on, player_points, team_points, matchup_assists, matchup_turnovers, matchup_blocks, matchup_field_goals_made, matchup_field_goals_attempted, matchup_three_pointers_made, matchup_three_pointers_attempted, matchup_free_throws_attempted, help_blocks, help_field_goals_attempted, shooting_fouls, season, season_type_id |
| Matchup season totals, last season | `load_nba_stats_matchups(seasons = 2025)` | 294,606 | not printed yet. Not needed by the app, only a cross-check for the summed per-game rows |
| Matchup season totals, this season | `load_nba_stats_matchups(seasons = 2026)` | EMPTY: not published | Not needed. Sum the per-game file |
| Player bio | `load_nba_stats_leaguedash(seasons = 2026, table = "player_bio")` | 471 | player_id, player_name, team_id, age, player_height_inches, player_weight, gp, pts, reb, ast, usg_pct, ts_pct, ast_pct |
| Player stats | tables `player_stats_base`, `player_stats_advanced` | 471 each | not printed yet |
| Team stats | table `team_stats_advanced` | 30 | team_id, team_name, w, l, off_rating, def_rating, net_rating, pace, efg_pct, ts_pct, tm_tov_pct, oreb_pct, dreb_pct, ast_pct |
| Four factors | table `team_stats_fourfactors` | 30 | not printed yet |
| Tracking defense | table `player_tracking_defense` | 469 | player_id, stl, blk, dreb, def_rim_fgm, def_rim_fga, def_rim_fg_pct |
| Other tracking | tables `player_tracking_drives`, `_passing`, `_rebounding`, `_catchshoot`, `_pullupshot`, `_posttouch`, `_speeddistance` | 450 to 471 each | not printed yet |
| Lineups | table `lineups_base` | 8,000 | group_set, group_id, group_name, team_id, gp, min, plus_minus, pts |
| Standings | table `standings` | 30 | team_id, conference, playoff_rank, wins, losses, record, home, road, l10, str_current_streak, current_streak |
| Hustle | `load_nba_stats_hustle_player(seasons = 2026)` | 918 | player_id, deflections, charges_drawn, contested_shots, contested_shots_3_pt, loose_balls_recovered, per_mode |
| Player game logs | `load_nba_stats_player_game_logs(seasons = 2026)` | 4,432 | player_id, team_id, game_id, game_date, matchup, wl, min, pts, reb, ast, stl, blk, tov, plus_minus |
| NBA schedule | `load_nba_stats_schedule(seasons = 2026)` | 1,274 | game_id, season_type, game_date, home_team_id, away_team_id, home_pts, away_pts, home_wl, away_wl |
| Game lineups | `load_nba_stats_game_lineups(seasons = 2026)` | 102,796 | game_id, action_number, period, home_player_1 to 5, away_player_1 to 5 |
| Play-by-play | `load_nba_stats_pbp(seasons = 2026)` | 102,796 | game_id, action_number, period, clock, team_id, person_id, description, action_type, sub_type, is_turnover, possession_number, off_player_1 onward (49 columns) |
| Combine measurements | `load_nba_stats_draft_combine_anthro(seasons = 2025)` | 79 per draft class | player_id, player_name, height_wo_shoes, weight, wingspan, standing_reach |
| Combine drills | `load_nba_stats_draft_combine_drills(seasons = 2025)` | 79 per draft class | player_id, standing_vertical_leap, max_vertical_leap, lane_agility_time |

Freshness: the player game logs ran through Nov 15, 2026 when pulled on Nov 16, so the files update about daily.

### What the labels look like

- **Matchups** come one row per offensive player, defensive player and game. There is no season-totals file for 2026-27, so pair totals for both seasons are built by summing the per-game rows by `off_person_id` and `def_person_id`. Every 2026-27 row has `season_type_id` 2. Check the values in last season's file before summing, because 1,322 games is more than a regular season.
- **Shot types** are in `sub_type` of the shots file. Most common: Jump Shot, Pullup Jump shot, Driving Layup Shot, Driving Floating Jump Shot, Step Back Jump shot, Running Layup Shot, Running Jump Shot, Driving Finger Roll Layup Shot, Cutting Layup Shot, Tip Layup Shot, Fadeaway Jump Shot, Putback Layup Shot, Layup Shot, Driving Floating Bank Jump Shot, Turnaround Fadeaway shot, Floating Jump shot, Running Pull-Up Jump Shot, Turnaround Jump Shot, Running Dunk Shot, Cutting Dunk Shot.
- **Shot zones are not in the file.** Derive rim, paint, midrange, corner three and above-the-break three, plus left, center and right, from `x_legacy`, `y_legacy` and `shot_distance`.
- **Shots have no date.** Join `game_id` to the schedule file for dates.
- **Turnover types** are in `sub_type` of play-by-play rows where `action_type` is Turnover: Bad Pass (2,019), Lost Ball (1,277), Offensive Foul Turnover, Out of Bounds - Bad Pass Turnover, Out of Bounds Lost Ball Turnover, Shot Clock Turnover, Traveling. On-ball steals are steals on Lost Ball turnovers.
- **Game types** are in `season_type` of the schedule file: regular-season (1,206), preseason (67), nba-cup (1). Only one game carries the nba-cup label, so NBA Cup group games are not marked here.
- **Play-by-play action types:** Rebound, Missed Shot, Made Shot, Substitution, Free Throw, Foul, Turnover, Timeout, period, Instant Replay, Jump Ball, Violation, Heave, Ejection.

## Headshots: NBA image CDN

Checked Nov 16, 2026 from campus Wi-Fi. `https://cdn.nba.com/headshots/nba/latest/260x190/<NBA player id>.png` returned an image for a real player id (17 KB, and 198 KB at `1040x760`). The browser loads these links directly, so no ESPN id is needed for headshots. An unknown id still returns a small generic image and not an error, so the app's own placeholder is for when the link cannot be reached at all.

## Route 2: ESPN (all passed)

| Data | Call | Rows | Notes |
| --- | --- | --- | --- |
| Schedule | `load_nba_schedule(seasons = 2027)` | 1,206 | 1,009 games still upcoming on Nov 16 |
| Player box scores | `load_nba_player_box(seasons = 2027)` | 5,266 | includes athlete_id, athlete_display_name, athlete_headshot_href |
| Teams | `espn_nba_teams()` | 30 | for the team picker and search |
| Injuries | `espn_nba_injuries()` | 28 | for injury tags |

ESPN ids and NBA stats ids are different numbering systems. The app uses NBA stats ids everywhere. ESPN is needed only for injuries, which are matched to NBA stats players by name.

## Route 3: live only, blocked on campus

These are not in the files. Each needs a run from a phone hotspot or home internet. The app must still work when they are missing.

| Data | Live function | Used for | Without it |
| --- | --- | --- | --- |
| Shots by dribbles and by defender distance | `nba_leaguedashplayerptshot` | Tough Shot Maker badge, shot profile panel | Skip the badge and the panel |
| Overall defended field goal percentage | `nba_leaguedashptdefend` | Perimeter defense rating | Use steals, deflections, contested threes and matchup data |
| Passes between teammates | `nba_playerdashptpass` | "Who feeds him" on the one-pager | Use assist pairs from play-by-play |
| Dunk score | `nba_dunkscoreleaders` | Poster Maker badge | Use dunk counts by type from the shots file |
| Clutch stats | `nba_leaguedashplayerclutch` | Closer badge | Compute from play-by-play, or skip |
| NBA Cup standings and game labels | `nba_iststandings`, `nba_schedule` | NBA Cup icon | Check the ESPN schedule for a Cup note |

## Still unknown

- Whether the play types file has team-level rows or only player rows.
- How NBA Cup group games can be flagged without the live site.
- How many draft classes of combine data are needed to cover current players.
