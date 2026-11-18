# Data sources, verified

Results of `pulls/test_pulls.R`, run on Nov 16, 2026 from campus Wi-Fi with R 4.6.2, hoopR 3.2.0 and the arrow package. This file is the source of truth for what data exists and what the columns are called. Update it whenever the pull test is rerun. Column names marked as printed on Nov 16 come from `pulls/print_columns.R`.

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
| Matchup season totals, last season | `load_nba_stats_matchups(seasons = 2025)` | 294,606, 30 columns | off_player_id, def_player_id, gp, matchup_min, partial_poss, player_pts, team_pts, matchup_ast, matchup_tov, matchup_blk, matchup_fgm, matchup_fga, matchup_fg3_m, matchup_fg3_a, help_blk, help_fga, matchup_fta, sfl, per_mode. Not needed by the app, only a cross-check for the summed per-game rows. Its column names differ from the per-game file |
| Matchup season totals, this season | `load_nba_stats_matchups(seasons = 2026)` | EMPTY: not published | Not needed. Sum the per-game file |
| Player bio | `load_nba_stats_leaguedash(seasons = 2026, table = "player_bio")` | 471 | player_id, player_name, team_id, age, player_height_inches, player_weight, gp, pts, reb, ast, usg_pct, ts_pct, ast_pct |
| Player stats, base | table `player_stats_base` | 471, 73 columns | player_id, player_name, team_id, team_abbreviation, age, gp, min, fgm, fga, fg_pct, fg3_m, fg3_a, fg3_pct, ftm, fta, ft_pct, oreb, dreb, reb, ast, tov, stl, blk, pf, pfd, pts, plus_minus |
| Player stats, advanced | table `player_stats_advanced` | 471, 83 columns | player_id, gp, min, off_rating, def_rating, net_rating, ast_pct, ast_to, oreb_pct, dreb_pct, reb_pct, tm_tov_pct, efg_pct, ts_pct, usg_pct, pace, pie, poss |
| Team stats | table `team_stats_advanced` | 30 | team_id, team_name, w, l, off_rating, def_rating, net_rating, pace, efg_pct, ts_pct, tm_tov_pct, oreb_pct, dreb_pct, ast_pct |
| Four factors | table `team_stats_fourfactors` | 30, 32 columns | team_id, team_name, gp, w, l, efg_pct, fta_rate, tm_tov_pct, oreb_pct, opp_efg_pct, opp_fta_rate, opp_tov_pct, opp_oreb_pct |
| Tracking defense | table `player_tracking_defense` | 469 | player_id, stl, blk, dreb, def_rim_fgm, def_rim_fga, def_rim_fg_pct |
| Tracking drives | table `player_tracking_drives` | 469 | player_id, gp, min, drives, drive_fgm, drive_fga, drive_fg_pct, drive_ftm, drive_fta, drive_pts, drive_passes, drive_ast, drive_tov, drive_pf |
| Tracking passing | table `player_tracking_passing` | 469 | player_id, gp, min, passes_made, passes_received, ast, ft_ast, secondary_ast, potential_ast, ast_pts_created, ast_adj, ast_to_pass_pct |
| Tracking rebounding | table `player_tracking_rebounding` | 450 | player_id, gp, min, oreb, oreb_contest, oreb_chances, oreb_chance_pct, dreb, dreb_contest, dreb_chances, dreb_chance_pct, reb, reb_contest, reb_contest_pct, reb_chances, reb_chance_pct, avg_reb_dist |
| Tracking catch-and-shoot | table `player_tracking_catchshoot` | 471 | player_id, gp, min, catch_shoot_fgm, catch_shoot_fga, catch_shoot_fg_pct, catch_shoot_pts, catch_shoot_fg3_m, catch_shoot_fg3_a, catch_shoot_fg3_pct, catch_shoot_efg_pct |
| Tracking pull-up | table `player_tracking_pullupshot` | 471 | player_id, gp, min, pull_up_fgm, pull_up_fga, pull_up_fg_pct, pull_up_pts, pull_up_fg3_m, pull_up_fg3_a, pull_up_fg3_pct, pull_up_efg_pct |
| Tracking post touches | table `player_tracking_posttouch` | 469 | player_id, gp, min, touches, post_touches, post_touch_fgm, post_touch_fga, post_touch_fg_pct, post_touch_fta, post_touch_pts, post_touch_passes, post_touch_ast, post_touch_tov, post_touch_fouls |
| Tracking speed and distance | table `player_tracking_speeddistance` | 469 | player_id, gp, min, dist_feet, dist_miles, dist_miles_off, dist_miles_def, avg_speed, avg_speed_off, avg_speed_def |
| Lineups | table `lineups_base` | 8,000 | group_set, group_id, group_name, team_id, gp, min, plus_minus, pts |
| Standings | table `standings` | 30 | team_id, conference, playoff_rank, wins, losses, record, home, road, l10, str_current_streak, current_streak |
| Hustle | `load_nba_stats_hustle_player(seasons = 2026)` | 918 | player_id, deflections, charges_drawn, contested_shots, contested_shots_3_pt, loose_balls_recovered, per_mode |
| Player game logs | `load_nba_stats_player_game_logs(seasons = 2026)` | 4,432 | player_id, team_id, game_id, game_date, matchup, wl, min, pts, reb, ast, stl, blk, tov, plus_minus |
| NBA schedule | `load_nba_stats_schedule(seasons = 2026)` | 1,274 | game_id, season_type, game_date, home_team_id, away_team_id, home_pts, away_pts, home_wl, away_wl |
| Game lineups | `load_nba_stats_game_lineups(seasons = 2026)` | 102,796 | game_id, action_number, period, home_player_1 to 5, away_player_1 to 5 |
| Injury report | `load_nba_stats_injury_report(seasons = 2026)` | 54,695 (checked Nov 17, reports from Oct 18 through Nov 16 at 4pm Pacific) | season, report_datetime, game_date, game_time, report_matchup, away_team_abbr, home_team_abbr, team, report_player_name, current_status, reason, category, previous_status, game_id, team_id, person_id, match_method |
| Play-by-play | `load_nba_stats_pbp(seasons = 2026)` | 102,796 (106,459 on Nov 17) | game_id, action_number, period, clock, team_id, person_id, description, action_type, sub_type, is_turnover, possession_number, off_player_1 onward (49 columns) |
| Combine measurements | `load_nba_stats_draft_combine_anthro(seasons = 2025)` | 79 per draft class; classes back to 2000 load | player_id, player_name, height_wo_shoes, weight, wingspan, wingspan_ft_in, standing_reach, season |
| Combine drills | `load_nba_stats_draft_combine_drills(seasons = 2025)` | 79 per draft class | player_id, standing_vertical_leap, max_vertical_leap, lane_agility_time |

Freshness: the player game logs ran through Nov 15, 2026 when pulled on Nov 16, so the files update about daily.

### What the labels look like

- **Matchup season types kept:** regular season (2), playoffs (4), play-in (5) and the NBA Cup final (6). Preseason is dropped. The file holds no preseason rows, so in practice the filter is a guard.
- **Matchups** come one row per offensive player, defensive player and game. There is no season-totals file for 2026-27, so pair totals for both seasons are built by summing the per-game rows by `off_person_id` and `def_person_id`. `season_type_id` is 2 for the regular season (1,230 games last season), 4 for the playoffs (85), 5 for the play-in (6) and 6 for the NBA Cup final (1), checked by joining to the schedule file. Every 2026-27 row so far is 2. The types kept are in the line above.
- **Every leaguedash table is season totals.** All the tables checked carry `season_type` "Regular Season" and `per_mode` "Totals", one row per player or team. Per-game numbers are totals divided by `gp`.
- **Play types and hustle hold each row twice.** Both files have `per_mode` values `pergame` and `totals`, and only `season_type` `regular-season`. Pull scripts filter to one `per_mode`. The season matchup totals file is doubled the same way.
- **Play types are player rows only.** All 4,689 rows have a `player_id`, so there are no team rows. Team play type numbers are built by summing the `totals` rows by `team_id`. `type_grouping` is Offensive (2,627 rows) or Defensive (2,062). `play_type` values: Cut, Handoff, Isolation, Misc, OffRebound, OffScreen, Postup, PRBallHandler, PRRollMan, Spotup, Transition. Other columns: fg_pct, ft_poss_pct, sf_poss_pct, score_poss_pct, fgm, gp.
- **Hustle** also has contested_shots_2_pt, screen_assists, off_boxouts, def_boxouts and box_outs. Its games column is `g`, not `gp`.
- **Game logs for box scores.** Last season's file (`load_nba_stats_player_game_logs(seasons = 2025)`) has 28,572 lines: regular season (26,651, game ids starting 002) and playoffs (1,921, ids starting 004). The 6 play-in games (ids starting 005) and the NBA Cup final are not in it, so those games have a final score but no box score. Summed player points matched the final score in all 210 games played this season by Nov 17.
- **Starters** come from the game lineups file: the five home and five away players on the first play of period 1. That marks 10 starters in 1,524 of 1,525 games across both seasons.
- **Last season's leaguedash tables also hold playoff rows** (582 regular season plus 230 playoff rows for advanced stats), and play types and hustle hold every row twice (pergame and totals). `pulls/pull_stats.R` keeps regular-season totals only.
- **Play types** only list a player for a play type once he has enough possessions, so 187 player seasons have post-up rows. Others count as 0 post-ups.
- **ESPN steals** (`load_nba_pbp`, season_type 2 is the regular season, 3 playoffs, 5 play-in): last season 22,194 steal rows. After matching (with "Grady Dick" added as an override for the NBA's "Gradey Dick"), every stealer matched in both seasons. Check on Nov 18: Dyson Daniels 40 steals in ESPN play-by-play and 40 in the NBA game logs.
- **Shot order within a game** for the streaky test: period, then the clock (text like "PT11M32.00S", parsed to seconds and counted down), then file order.
- **Combine drills** (`load_nba_stats_draft_combine_drills`) have `max_vertical_leap` for most players measured (77 of 83 in 2024).
- **Shot types** are in `sub_type` of the shots file. Most common: Jump Shot, Pullup Jump shot, Driving Layup Shot, Driving Floating Jump Shot, Step Back Jump shot, Running Layup Shot, Running Jump Shot, Driving Finger Roll Layup Shot, Cutting Layup Shot, Tip Layup Shot, Fadeaway Jump Shot, Putback Layup Shot, Layup Shot, Driving Floating Bank Jump Shot, Turnaround Fadeaway shot, Floating Jump shot, Running Pull-Up Jump Shot, Turnaround Jump Shot, Running Dunk Shot, Cutting Dunk Shot.
- **Shot zones are not in the file.** `pulls/pull_shots.R` derives them. Coordinates are tenths of a foot, basket at (0, 0), baseline at y = -47.5. 2 or 3 comes from `shot_value`. Restricted area: 2-pointer with sqrt(x^2 + y^2) <= 40. Paint: other 2-pointer with |x| <= 80 and y <= 142.5. Midrange: other 2-pointers. Corner three: 3-pointer with y <= 92.5. Above the break: other 3-pointers. Checked Nov 18 on 36,829 shots: the distance from x and y was within 1 ft of the distance stated in the description for all 33,520 shots that state one, "3PT" in the description agreed with `shot_value` on every shot, and the nearest corner three was 22.1 ft out.
- **Shot sides are not confirmed.** Nothing in the pre-pulled files says whether positive x is the shooter's left or right. `pull_shots.R` assumes negative x is the shooter's right. `pulls/check_sides.R` checks it against the live shot chart's SHOT_ZONE_AREA, and must be run from a network that reaches the NBA stats site. The app keeps sides out of the UI until then.
- **Positions** are not in player_bio. The matchup files' `off_position` (C, F or G, most common value across both seasons) covers 420 of 519 players, and ESPN box score positions (`athlete_position_abbreviation`), matched by name with `pulls/espn_match.R`, fill 83 more: 503 of 519 (97%) on Nov 18. ESPN box scores also list did-not-play players, so 13 ESPN names had no NBA player to match.
- **Wingspan** comes from `load_nba_stats_draft_combine_anthro` for draft classes 2000 to 2025 (each loads; classes have 45 to 83 players). The most recent measurement per player is kept. Coverage on Nov 18: 309 of 519 players (60%), 280 of the 471 who have played. Players who skipped the combine, including many international and undrafted players, have none.
- **Shots have no date.** Join `game_id` to the schedule file for dates.
- **Turnover types** are in `sub_type` of play-by-play rows where `action_type` is Turnover: Bad Pass (2,019), Lost Ball (1,277), Offensive Foul Turnover, Out of Bounds - Bad Pass Turnover, Out of Bounds Lost Ball Turnover, Shot Clock Turnover, Traveling.
- **The NBA stats play-by-play has no steal rows and never names the stealer.** On-ball steals come from ESPN play-by-play instead (Route 2).
- **Assists are in the shot description.** 10,768 of 16,512 made shots (65.2%, Nov 17) name the passer, as in "Tatum 4' Layup (3 PTS) (Robinson 1 AST)". The passer is a last name only, so match it to the scorer's four teammates on the floor (`off_player_1` to `off_player_5`, NBA ids) to get assist pairs.
- **Injury report rows.** 5,529 rows have reason "NOT YET SUBMITTED" and no player, so they are skipped. `current_status` is Out, Questionable, Probable, Doubtful or Available. Use the latest `report_datetime` per `person_id`. `match_method` (exact, family, roster) is how hoopR matched the report name to an NBA id.
- **Game types** are in `season_type` of the schedule file: regular-season (1,206), preseason (67), nba-cup (1). Last season's file (`seasons = 2025`) also has playoffs (85), play-in (6) and all-star (7). The pull keeps regular season, NBA Cup, play-in and playoffs. Only one game carries the nba-cup label, so NBA Cup group games are not marked here.
- **Play-by-play action types:** Rebound, Missed Shot, Made Shot, Substitution, Free Throw, Foul, Turnover, Timeout, period, Instant Replay, Jump Ball, Violation, Heave, Ejection.

## Headshots: NBA image CDN

Checked Nov 16, 2026 from campus Wi-Fi. `https://cdn.nba.com/headshots/nba/latest/260x190/<NBA player id>.png` returned an image for a real player id (17 KB, and 198 KB at `1040x760`). The browser loads these links directly, so no ESPN id is needed for headshots. An unknown id still returns a small generic image and not an error, so the app's own placeholder is for when the link cannot be reached at all.

## Route 2: ESPN (all passed)

| Data | Call | Rows | Notes |
| --- | --- | --- | --- |
| Schedule | `load_nba_schedule(seasons = 2027)` | 1,206 | 1,009 games still upcoming on Nov 16 |
| Player box scores | `load_nba_player_box(seasons = 2027)` | 5,266 | includes athlete_id, athlete_display_name, athlete_headshot_href |
| Teams | `espn_nba_teams()` | 30 | not used. The NBA stats files have the team list |
| Injuries | `espn_nba_injuries()` | 28 | not used. Replaced by the NBA stats injury report, which has NBA ids |
| Play-by-play | `load_nba_pbp(seasons = 2027)` | 102,897 covering 205 games (Nov 17) | On turnover rows, `athlete_id_2` is the stealer and `text` ends "(Name steals)". 3,389 turnovers name a stealer, 1,299 of them Lost Ball Turnover. Other columns: type_text, team_id, athlete_id_1, athlete_name_1, athlete_name_2, home_team_abbrev, away_team_abbrev, game_date |

ESPN ids and NBA stats ids are different numbering systems. The app uses NBA stats ids everywhere. ESPN is needed only for steals, from its play-by-play.

Matching ESPN stealers to NBA ids, checked Nov 17: after dropping accents, punctuation and case, 404 of 405 stealer names matched a name in the NBA player bio table, and no two bio players share a name key. The one miss was Bobby Portis. The pull also strips suffixes (Jr., Sr., II, III, IV), uses a manual override table for names that still miss, and prints any unmatched stealer names. Team is a tie-breaker, but ESPN and NBA team abbreviations differ (only 79% agreed as raw text), so team matching needs a small abbreviation map.

Aggregation check: Anthony Black has 19 steals in ESPN play-by-play and 19 in the NBA game logs over his 10 games.

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

- How NBA Cup group games can be flagged without the live site.
