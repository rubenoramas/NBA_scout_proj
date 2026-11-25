# Opponent Scout: Project Spec

Version 1.3, Nov 16, 2026. Owner: Ruben.

## Overview

Opponent Scout is a web app that builds a pregame scouting report on an NBA opponent: how the team plays, where each player scores from, and who should guard whom. It is built for a coach, a video coordinator, or a serious fan.

It has two jobs. It is the CS class project "Build something cool with AI" (due Nov 29, 2026 at 8pm), and it is a standalone portfolio piece on GitHub.

Any team can be scouted against any team. The user picks "us", then picks "them" from a calendar of upcoming games or a search box.

## Class requirements

| Requirement | How Opponent Scout meets it |
| --- | --- |
| Docker | One `docker-compose.yml` runs the Flask app and MongoDB |
| Flask | Backend API server |
| JavaScript and AJAX | Vanilla JS. Changing a lineup recomputes matchups without a page reload |
| MongoDB | Stores teams, players, shots, lineups and saved reports |
| REST with CRUD | Lineups and scouting reports can be created, read, updated and deleted |
| UX | Loading state while a report generates, lineup validation (five players), clear error messages |
| AI | A matchup model plus an LLM-written report inside the app. Claude Code for the build, with prompts logged for the README |
| Submission | GitHub repo, README with the four required answers, a 2 to 3 minute video on Canvas, no real credentials in the repo |

## Features

All eight are in the first version.

1. **Team scouting profile.** How the opponent plays: play type mix and efficiency, pace, shot profile, and the four factors. The page opens with a game context header (see below).
2. **Player cards.** Headshot, height, weight, wingspan, role, key stats, and a link to the player's shot profile.
3. **Shot profiles.** A shot chart per player with tendencies by location and shot type.
4. **Suggested matchups.** Which of our defenders should guard which of their scorers, with a reason for each pairing.
5. **Lineup editor with injury tags.** Set both fives by hand. Injury tags prefill from the injury feed and can be overridden.
6. **AI team report.** A written report for the coach, built from the numbers above. It can be saved, edited and deleted.
7. **Player one-pager.** A one-page sheet on each opponent player, written for a player on our team.
8. **Rotation scouting.** The opponent's likely lineups with tags, and counter lineups from our roster.

Added Nov 18: **box scores** for every played game this season and last, with Basic and Advanced views (TS%, eFG%, USG%, Game Score, AST/TOV, team four factors). Reached from the schedule (Box score links, the mini calendar, and a Last game tab) and from Recent results on the scouting page.

Added Nov 18: **player cards** at `/player/<id>` (headshot, height, weight, wingspan, season line, last five games, shot chart, zone table against league average, favorite shot types), reached from the Players tab on the scouting page and from player names in box scores.

## Game context header

The top of the scouting page sets the scene before any analysis.

| Item | Shows |
| --- | --- |
| Records and seeds | Each team's win-loss record and conference seed |
| Streak | Current win or loss streak, and the last ten games |
| Last game, both teams | Opponent, score, result and date |
| Last game standout | The player whose last game beat his own average by the most. Rule: at least 5 earlier games averaging at least 15 minutes, at least 20 minutes in the last game, and in the last game at least 10 more points, 6 more rebounds or 5 more assists than his average, and at least 1.5 times it. The biggest jump relative to the average wins |
| Last meeting | The most recent game between the two teams, with date and score. Falls back to last season, labeled with the season and marked when it was a playoff or play-in game |
| Next meeting | The next scheduled game between the two teams this season |
| Game type icon | A marker when the game is an NBA Cup game or a playoff game |
| Data freshness | Both facts in the top bar: "Games through Tue, Nov 17 · pulled Nov 18, 9:02 AM". Green dot, amber when the pull is more than 2 days old |

Everything here changes daily. Because the app runs from seed data, the top bar always shows the latest game in the data and when it was pulled, and `./refresh.sh` is rerun right before the demo video and before submitting.

## Shot profile detail

Public NBA data gives the exact location and the shot type of every shot, but not the direction a player was moving.

| Detail | Available? | Level |
| --- | --- | --- |
| Exact court location (x, y) | Yes | Every shot |
| Shot type: pull-up, step back, driving layup, floater, fadeaway, and dozens more | Yes | Every shot |
| Court zone and side (left, center, right) | Yes | Every shot |
| Dribbles before the shot (0, 1, 2, 3 to 6, 7 or more) | Yes | Season totals per player, not per shot |
| Closest defender distance, touch time, shot clock | Yes | Season totals per player |
| Drives: volume, shooting, passes, turnovers | Yes | Season totals per player |
| Direction of the dribble or drive (going left or right) | No | Only in paid or team-only data such as Synergy and Cleaning the Glass Pro |

What this means for the app:

- It can say "pull-up midrange from the left elbow is X% of his shots, and he makes Y% of them".
- It cannot say "he prefers driving left". The honest substitute is side of the floor, labeled as where the shot was taken, not which way he was going.
- Per-shot fields (location, type) and season-total fields (dribbles, defender distance) cannot be joined shot by shot. They appear as separate panels.

## Player one-pager

A one-page sheet on a single opponent player, written for a player on our team. It has to be readable in a minute, so skills appear as ratings and badges.

| Part | What it shows | Built from |
| --- | --- | --- |
| Size | Height, weight and wingspan | Player bio data. Wingspan only where a combine measurement exists |
| Attributes | A 0 to 99 rating for each skill | Percentile rank against the league on the stats behind that skill |
| Badges | Traits that are hard to see in the ratings | A rule per badge, listed below |
| Best three defenders | Our top three options to guard him, ranked | Matchup model, plus height and weight |
| Favorite shots by level | His most common shot types at the rim, in the midrange and from three | Location and shot type on every shot |
| How he gets his shots | Share and efficiency by play type, and which teammates feed him | Play type data and passing data |
| How to guard him | Two or three plain sentences | LLM, written only from the parts above |

The twelve attributes and the data behind each:

| Attribute | Main inputs |
| --- | --- |
| Finishing | Rim shots from shot data, drives |
| Post scoring | Post-up play type |
| Midrange | Midrange shots from shot data |
| Three-point shooting | Three-point shots from shot data |
| Catch-and-shoot | Tracking shots with 0 dribbles |
| Pull-up shooting | Tracking pull-up shots |
| Free throws and drawing fouls | Free throw rate and percentage |
| Playmaking | Assists and tracking passing |
| Rebounding | Rebound rates and tracking rebounding |
| Perimeter defense | Steals, deflections, contested threes, matchup data |
| Interior defense | Opponent shooting at the rim when he defends, blocks |
| Speed | Tracking speed and distance |

### How ratings are computed (final, Nov 18)

R pulls and trims; Python in `app/model/ratings.py` computes. Only regular-season numbers are used.

1. **Blend first.** Every component is a rate over a sample (makes over attempts, a count over minutes). With w = MIN_this / (MIN_this + 600): blended rate = w x rate_this + (1 - w) x rate_last; blended sample = w x sample_this + (1 - w) x sample_last; blended league = w x league_this + (1 - w) x league_last. A season with no data for the component is left out and the weights renormalized. With no minutes this season, w = 0 and the rating is tagged "Last season only". (Changed Nov 18: shrinkage used to run on each season before blending.)
2. **Then shrink once.** value = (blended rate x blended sample + k x blended league) / (blended sample + k). Shooting percentages: shrunk% = (makes + k x league%) / (attempts + k), with k = 50 for field goal types, 30 for free throws, and 25 possessions for post-up PPP. Every per-36 rate is shrunk the same way by minutes (added Nov 18): shrunk per 36 = (his count + league rate per minute x 400) / (his minutes + 400) x 36, where the league rate per minute is the season's total count divided by total minutes. The badge rates per 36 (lost-ball steals, deflections, dunks) use the same formula over both seasons pooled.
3. **Qualified players.** At least 200 minutes this season, or at least 500 last season. Others show "Not enough minutes".
4. **Component percentile.** Each component is ranked among qualified players as a share from 0 to 1 (flipped where lower is better).
5. **Rating.** composite = weighted average of component percentiles; rating = round(99 x percentile rank of the composite among qualified players). 50 is a typical qualified player.
6. **Tooltips.** Players are ranked on the adjusted (shrunk) values, but rating tooltips show each player's real blended rate with the adjusted value beside it, such as "13.0 per 36 (adjusted 10.9)".
7. **Small sample.** Tagged when the attribute's key sample (this season plus last) is below the threshold in the table.

| Attribute | Components (weight) | Small sample below |
| --- | --- | --- |
| Finishing | Restricted-area FG%, shrunk (0.4); restricted-area FGA/36 (0.3); drive points/36 (0.3) | 40 restricted-area FGA |
| Post scoring | Post-up PPP, shrunk (0.5); post-up possessions/36 (0.2); post-touch points/36 (0.3) | 25 post-up possessions |
| Midrange | FG% in paint (non-RA) plus midrange, shrunk (0.6); those FGA/36 (0.4) | 40 FGA |
| Three-point shooting | 3P%, shrunk (0.65); 3PA/36 (0.35) | 50 3PA |
| Catch-and-shoot | Catch-and-shoot eFG%, shrunk (0.65); catch-and-shoot FGA/36 (0.35) | 40 FGA |
| Pull-up shooting | Pull-up eFG%, shrunk (0.65); pull-up FGA/36 (0.35) | 40 FGA |
| Free throws and drawing fouls | FT%, shrunk (0.5); FTA per FGA (0.5) | 30 FTA |
| Playmaking | Skill: AST%, shrunk by minutes with k = 400 (0.3); AST/TOV, shrunk by minutes with k = 400 (0.3). Volume: potential assists per game (0.4) | 300 minutes |
| Rebounding | OREB% (0.3); DREB% (0.4); rebound chance % (0.3) | 300 minutes |
| Perimeter defense | Steals/36 (0.3); deflections/36 (0.3); contested threes/36 (0.2); points allowed per partial possession as primary defender, lower is better (0.2) | 300 minutes |
| Interior defense | Opponent FG% at the rim, shrunk, lower is better (0.4); rim FGA defended/36 (0.2); blocks/36 (0.4) | 40 rim FGA defended |
| Speed | Average speed (0.7); miles/36 (0.3) | 300 minutes |

**Usage rate (USG%).** The share of his team's plays (FGA + 0.44 x FTA + TOV) a player uses while on the floor. It describes role, not skill, so it is shown as a stat with a league rank (among players with 200+ minutes this season), not as a 0 to 99 rating, beside last season's value. The season value is the NBA's `usg_pct` from the verified player files. The box score computes the same idea per game with 100 x (FGA + 0.44 x FTA + TOV) x (team MIN / 5) / (MIN x (team FGA + 0.44 x team FTA + team TOV)); summed over this season's games for 249 players with 200+ minutes it correlates 0.999 with the NBA's value and runs about 0.7 points higher, because it estimates team plays on the floor from minutes. Under 100 minutes, USG% is marked as a small sample and sorts last. **The matchup model will use USG% to weight scorers**, so the defenders it assigns matter most against the players who use the most plays.

Badges (first four) pool both seasons' raw counts and need at least 500 minutes over the two seasons. Names live in `app/model/badge_config.py`.

- **Deep Range:** at least 40 three-point attempts from 28 to 39 ft (heaves of 40 ft or more excluded); at least 20% of his threes from 28+ ft; deep 3P% at or above the league's overall 3P%.
- **Streaky Shooter:** at least 300 field goal attempts that followed another attempt in the same game. One-sided two-proportion z-test that his make rate after a make is higher than after a miss, with p below 0.05 divided by the number of players tested (Bonferroni). Comparing rates after makes and misses within games is biased slightly against finding streakiness (Miller and Sanjurjo, 2018), so the test is conservative.
- **On-Ball Pest:** at least 15 lost-ball steals (ESPN play-by-play); top 10% of qualified players in lost-ball steals/36, and deflections/36 above the qualified median.
- **Poster Maker:** counts driving, running and cutting dunks only; alley-oops and putbacks are left out (they fit a future Lob Threat badge). At least 25 of those dunks and top 10% of qualified players in those dunks/36. Shows the mix, the number of alley-oops and putbacks left out, and max vertical where a combine measurement exists (changed Nov 18).

Skipped because they need live-only data: Tough Shot Maker, defended FG% for perimeter defense, dunk score, clutch stats (Closer).

### Trait badges

Ratings carry the numbers. Badges carry the traits that numbers hide. Each badge is a rule on data we already pull, and each needs a minimum sample before it can be earned.

| Badge (working name) | What it means | How it is measured | Confidence |
| --- | --- | --- | --- |
| Deep Range | Takes and makes threes from well behind the line | Share of his threes from 28 feet or more, and accuracy on them | Solid |
| Streaky Shooter | Runs hot and cold | Make rate after a make against after a miss within games, plus game-to-game swings | Low. Needs a large sample, and research finds the hot hand effect small |
| On-Ball Pest | Takes the ball off the dribbler | Steals on lost-ball turnovers (not bad passes) from ESPN play-by-play, plus deflections | Medium. ESPN names the stealer, matched to NBA ids by name |
| Poster Maker | Dunks on people | Dunk volume by type (driving, cutting, running, putback, alley-oop) from shot data, plus combine max vertical where a player has one | Solid for dunk volume. Vertical covers few players |
| Tough Shot Maker | Hits contested shots | Accuracy on tightly guarded shots against league average | Needs live data. Skipped unless a hotspot pull is run |
| Corner Specialist | Lives in the corners | Share and accuracy of corner threes | Solid |
| Foul Magnet | Gets to the line | Free throw attempts per shot attempt | Solid |
| Lob Threat | Finishes above the rim off passes | Alley-oop dunks and layups from shot type | Solid |
| Transition Threat | Scores on the run | Transition play type share and efficiency | Solid |
| Rim Deterrent | Opponents shoot worse near him at the rim | Rim defense from the tracking file | Medium |
| Closer | Produces late in close games | Clutch stats, or late close-game plays from play-by-play | Low early in a season |

Build order: the first four (the owner's picks), then the ones marked Solid. Low-confidence badges show their sample size, because a wrong "streaky" label could change how a player defends someone.

Limits:

- Named set plays are not in public data. The sheet shows how his possessions end (isolation, pick and roll, spot up, and so on), not the play that was called.
- Wingspan exists only for players measured at the draft combine. Height and weight cover everyone.
- Ratings are unstable a month into a season. They need a minimum volume and a blend with last season.
- Badge names and art should be our own. Every badge name lives in one config file, so a rename is one edit. "Deep Range" and "Poster Maker" replace two earlier working names that were also NBA 2K badge names.

## Rotation scouting

This view shows the opponent's most-used lineups, tags each one, and suggests a counter lineup from our roster.

| Tag | Starting rule |
| --- | --- |
| Starters | The most common starting five |
| Small ball | No traditional center on the floor |
| 3pt | Four or more high-volume three-point shooters |
| Defensive | High average defensive ratings across the five |
| Big | Two or more bigs |

Tags come from the attributes of the five players, not from how the lineup has performed. Five-man lineups have too few minutes together this early in a season for results to mean much.

Counters start as simple rules, for example answering a small ball lineup with our best switching five. If the schedule gets tight, counters are the first thing to simplify.

## Matchup model

Built Nov 18 in `app/model/matchups.py`. Units are points per 100 partial possessions (the time a defender spends guarding a scorer). The league averages about 24, because a scorer finishes only a small share of the possessions he is on the floor.

Data: totals for every defender and scorer pair per season, summed from the per-game matchup files for both seasons (`matchup_pairs.jsonl.gz`), plus this season pair by pair and game by game for validation (`matchup_games.jsonl.gz`).

Formulas (seasons blended like the ratings: rate and sample each weighted by w = MIN_this / (MIN_this + 600); the scorer's minutes for his baseline and pair history, the defender's minutes for his effect):

1. League rate L = total points / total partial possessions.
2. **Scorer baseline (his norm)** B = (pts + 200 x L) / (poss + 200).
3. **Defender effect, relative to his position** D = (actual points allowed - expected - his poss x P) / (his poss + 300), where expected = sum over his pairs of poss x B of that scorer, and P is the average (actual - expected) per possession of all defenders at his position (G, F or C). Shrinks toward 0. (Changed Nov 19: without P, centers averaged +5.3 per 100 and guards -1.5, because bigs are matched to scorers near the rim, so every guard looked like a better defender. P on Nov 19: C +6.4, F -1.2, G -1.7. After the change the averages by position are C -0.2, F -0.0, G -0.1.) The position offset is also removed before the size fit, so the size fit cannot soak it up.
4. **Size fit** S = b_h x height gap + b_w x weight gap / 10 lb + b_ws x wingspan gap (scorer minus defender; a missing measurement gives 0), fitted by weighted least squares on what is left after B + D. On Nov 18 it explains 0.1% of the leftover variance, so it barely matters.
5. **Pair estimate** E = (pair pts + 200 x mu) / (pair poss + 200), with prior mu = B + D + S. Ten possessions of history count about 5%. k was picked from 50, 100 and 200 on the same test window used to report the validation below, so the reported result for the chosen k is slightly optimistic.

Assignment: each opposing scorer is weighted by his USG% (this season with 100+ minutes, else last season). The app checks all 120 orderings of our five against their five and picks the lowest sum of USG% x E. **Position guard:** a guard may not guard a center, or a center a guard, unless the pair has 20+ partial possessions of history; the same rule applies to the top three lists. Players marked Out are excluded. Until the lineup editor exists, both lineups default to each team's most common starting five this season, with Out players replaced by the healthy players with the most minutes. The top three per opposing player come from our whole healthy roster (100+ minutes this season or 500+ last season).

Display: each pairing leads with E - B, "holds him 3.4 below his norm" (green) or "allows 1.2 above his norm" (red), with E per 100, the history size (small sample under 20 possessions) and a one-line reason built from the parts.

Validation (trained on last season plus this season before Nov 1, tested on the 21,605 pairs and 105,863 partial possessions since; run with `docker compose exec web python -m app.model.validate_matchups`). Correlation with actual points per 100, weighted by possessions:

| Model | All pairs | Pairs with 10+ poss | Pick matches top defender (with position guard) |
| --- | --- | --- | --- |
| Scorer norm only (B) | 0.162 | 0.330 | |
| Before (no position adjustment, k = 50), full model | 0.181 | 0.323 | 36.7% |
| Position-relative, k = 50 | 0.170 | 0.315 | 36.2% |
| Position-relative, k = 100 | 0.177 | 0.334 | 36.2% |
| **Position-relative, k = 200 (chosen)** | **0.178** | **0.342** | **36.4%** |

A same-position guess matches the top defender 43.3% of the time, and random 20%. Calibration of the chosen model by fifths: predicted 15.2 / 20.4 / 23.8 / 27.7 / 35.2, actual 16.1 / 20.2 / 23.1 / 25.6 / 36.5. The position adjustment costs a little raw prediction (0.181 to 0.178), because the center offset is real in the data, but it reflects when bigs are matched, not how well they defend, and it was distorting every comparison between positions.

Known limits: public matchup data is noisy because of switches and help defense. A rim protector may still rate poorly within his position if he is logged as the matched defender when he rotates over to help and the scorer finishes anyway (Donovan Clingan is +9.5 per 100 against other centers on Nov 19). Matching "who guarded him most" also measures coaches' choices, not what is best.

## Data window

This season is blended with last season. Last season is the starting point and fades as this season's volume grows. This applies to ratings, shot tendencies and the matchup model.

## Data sources and pipeline

```
hoopR pre-pulled files, ESPN  ->  R pull scripts (laptop)  ->  seed files in data/seed/
seed files  ->  loader (Docker)  ->  MongoDB  <->  Flask API  <->  browser (vanilla JS)
Flask API  <->  Claude API (numbers in, text back)
```

The verified list of sources, calls and column names is in `docs/DATA_SOURCES.md`. This section is the summary.

There are three routes:

1. **Pre-pulled NBA stats files** (`load_nba_stats_*`). The main route. One file holds a season, each loads in about a second, and they were current to the previous day when tested.
2. **ESPN play-by-play.** Used only for steals, because it names the stealer and the NBA stats play-by-play does not. Headshots load from the NBA image CDN by NBA player id, injuries come from the NBA stats injury report, and the calendar uses the NBA stats schedule.
3. **The live NBA stats site.** It gives no answer from campus Wi-Fi, so it is used only for a short optional list, pulled from a phone hotspot.

| Feature | Data | Route |
| --- | --- | --- |
| Shot profiles, favorite shots | Shots with x, y, shot type and distance, this season and last | Files |
| Team profile | Team advanced stats, four factors, play types summed from player rows (the file has no team rows) | Files |
| Player cards | Player bio (height, weight), base and advanced stats | Files |
| Headshots | NBA image CDN link built from the NBA player id, with a placeholder image when it fails | CDN |
| Calendar | NBA stats schedule | Files |
| Injuries | NBA stats injury report, latest report per player | Files |
| Ratings | Tracking tables: drives, passing, rebounding, catch-and-shoot, pull-up, post touches, speed, rim defense | Files |
| Game context header | Standings (record, seed, streak, last ten), player game logs, schedule results | Files |
| Rotation scouting | Lineups, and the five players on the floor for every play | Files |
| Trait badges | Shots, ESPN play-by-play (lost-ball steals), hustle stats (deflections), combine drills (vertical) | Files, plus ESPN |
| How he gets his shots | Assist pairs from the passer named in NBA stats play-by-play shot descriptions | Files |
| Wingspan | Combine measurements | Files |
| Matchup model | Per-game matchups for this season and last, summed into pair totals | Files |

Live only, and optional: shots by dribbles and by defender distance, overall defended field goal percentage, passes between teammates, dunk score, clutch stats, NBA Cup standings and labels. The app must work without them.

Things the files do not give directly:

- Shot zones. They are derived from the shot's x, y and distance.
- NBA Cup group games. The schedule file labels only one game as NBA Cup, so the Cup icon needs another source.
- A shared id system with ESPN. The app uses NBA stats ids everywhere, and ESPN stealers are matched to NBA players by name, with team as a tie-breaker.
- Who made a steal. The NBA stats play-by-play has no steal rows, so steals come from ESPN play-by-play.
- Assist pairs. They are parsed from the passer's name in made-shot descriptions (about 65% of made shots) and matched to the teammates on the floor.
- Matchup season totals for this season. They are built by summing the per-game matchup file.

Seed data covers all 30 teams. This season is stored shot by shot (about 35,000 shots in mid-November). Last season is stored as per-player totals by zone and shot type, which keeps the repo small.

## Data model

| Collection | Holds | Written by |
| --- | --- | --- |
| `teams` | Team info and the style fingerprint | Seed loader |
| `players` | Bio, headshot link, role, play type and tracking stats. Injured players who have not played yet get a basic document with `has_stats` false | Seed loader |
| `schedule` | Games for the calendar, with results. Holds this season and last season (for the last meeting), with a `season` field | Seed loader |
| `game_logs` | Per-game player lines for this season and last, with `season`, `home` and `starter`. Used for box scores, last game and form | Seed loader |
| `shots` | One document per shot this season: location, shot type, zone, side, result | Seed loader |
| `shot_zones_last`, `shot_types_last` | Last season's per-player shot totals by zone and by shot type | Seed loader |
| `matchups` | Totals for each defender and scorer pair | Seed loader |
| `injuries` | Latest status per player | Seed loader |
| `attributes` | Ratings and badges per player | Seed loader, computed in Python at load time |
| `standings` | Record, seed, streak and last ten per team | Seed loader |
| `team_stats` | Offensive, defensive and net rating, pace and the four factors per team, this season | Seed loader |
| `meta` | The latest game date (`data_as_of`) and the pull time (`pulled_at`) | Seed loader |
| `opponent_lineups` | Most-used fives with tags | Seed loader, tags computed in Python at load time |
| `lineups` | User-set fives: team, name, five player ids, status overrides, created and updated times. Index (team_id, updated_at) | User (CRUD) |
| `reports` | Saved reports: both teams, game, title, notes, both lineups with overrides, a snapshot of the matchup result at save time, "data as of", an empty AI text field, created and updated times. Indexes created_at, us_team_id, them_team_id | User (CRUD) |

## REST API

| Method | Path | Does |
| --- | --- | --- |
| GET | `/api/health` | Says whether the API can reach MongoDB |
| GET | `/api/teams` | List teams |
| GET | `/api/teams/<id>` | Team page: team, standing, and team stats (ratings, pace, four factors) with league ranks |
| GET | `/api/teams/<id>/schedule` | Games for the calendar |
| GET | `/api/teams/<id>/profile` | Team style fingerprint and roster |
| GET | `/api/games/context?us=<team id>&them=<team id>` | Records, seeds, streaks, last games, last meeting, game type |
| GET | `/api/games/<game_id>/boxscore` | Box score: game info, each team's player lines with advanced stats, team totals and four factors |
| GET | `/api/teams/<id>/lineups` | Most-used lineups with tags |
| GET | `/api/teams/<id>/roster` | Roster with position, per-game line, shooting and injury status |
| GET | `/api/players/<id>` | Player card data |
| GET | `/api/players/<id>/shots` | Shots for the shot chart, with filters |
| GET | `/api/players/<id>/onepager?vs=<team id>` | Player one-pager against a chosen team |
| POST | `/api/players/<id>/onepager/note?vs=<team id>` | "How to guard him" text: from the MongoDB cache, or written by Claude and cached |
| POST | `/api/lineups` | Save a lineup with injury tags |
| GET | `/api/lineups/<id>` | Read a lineup |
| PUT | `/api/lineups/<id>` | Change players or tags |
| DELETE | `/api/lineups/<id>` | Remove a lineup |
| POST | `/api/matchups` | Compute suggested matchups for two lineups |
| POST | `/api/reports` | Generate and save a scouting report |
| GET | `/api/reports` | List saved reports |
| GET | `/api/reports/<id>` | Read one report |
| PUT | `/api/reports/<id>` | Edit notes or report text |
| DELETE | `/api/reports/<id>` | Remove a report |

## AI usage

AI shows up in three places, and the README has to describe each one.

- **Matchup model.** Our own model produces the suggested assignments.
- **LLM report.** The app calls the Claude API with a structured summary of computed stats and model output. The prompt tells it to use only those numbers. The report page shows the same numbers next to the text, so every claim can be checked.
- **Build.** Claude Code writes most of the code. Prompts are logged in `docs/PROMPTS.md`.

The API key lives in an environment variable. The repo carries `.env.sample` with placeholders only.

The team report is one page in coach-style wording: opponent identity, three keys to the game, players to watch, suggested matchups.

## Screens and user flow

1. **Pick the game.** Choose your team. Its schedule appears as a calendar, and clicking an upcoming game opens the scouting report for that opponent. NBA Cup and playoff games carry an icon. A search box scouts any other team.
2. **Opponent overview.** The game context header, then the style fingerprint and key team numbers.
3. **Player cards.** Click a player for his shot chart and tendencies. A printable one-page view opens from the card.
4. **Lineups.** Set both fives and tag injuries.
5. **Matchups.** Suggested assignments with reasons. They update when a lineup changes.
6. **Rotations.** The opponent's most-used lineups with tags, and suggested counters.
7. **Generate report.** A loading state, then the AI text. Add notes and save.
8. **Saved reports.** List, open, edit, delete.

## Stretch features

These wait until the first version runs end to end.

- Shot chart filters: quarter, last N games
- Side-of-floor tendency callouts on player cards
- Defensive scouting: where the opponent gives up shots
- Lineup results: the opponent's best and worst five-man units, once minutes are large enough
- Export a report to PDF
- Hosted demo, served from the stored seed data

## Decisions

Made on Nov 16, 2026.

- **R pulls, Python computes.** R scripts only pull and trim data into seed files. Python in `app/model/` computes ratings, badges and lineup tags when the loader runs. The loader skips recomputing when the seed data has not changed, so startup stays fast.
- **NBA stats ids everywhere.** Every team and player id in MongoDB and the API is the NBA stats id. The calendar uses the NBA stats schedule.
- **Headshots from the NBA image CDN.** The link is built from the NBA player id. A test link loaded on Nov 16. A placeholder image shows when a headshot fails to load.
- **Injuries from the NBA stats injury report.** It uses NBA ids, so no name matching. The latest report per player is used, and rows with reason "NOT YET SUBMITTED" are skipped. (Changed Nov 17. ESPN injuries are no longer used.)
- **ESPN only for steals.** ESPN play-by-play names the stealer on lost-ball turnovers. Stealers are matched to NBA ids by name, with team as a tie-breaker. Before matching, names drop accents, punctuation, case and suffixes (Jr., Sr., II, III, IV). Names that still miss go in a small manual override table in `pulls/`, starting with Bobby Portis, and the pull prints every stealer name it could not match. No full ESPN id crosswalk is built. (Changed Nov 17.)
- **Assist pairs from shot descriptions.** The passer's last name in "(Robinson 1 AST)" is matched to the four teammates on the floor.
- **Play-by-play and game lineups are boiled down in R.** The pull scripts turn them into small tables (lost-ball steals, assist pairs, most common fives). The raw rows never enter the repo or MongoDB. The R stays simple, and one player's steal total is checked against his game logs to prove the aggregation.
- **Matchups come from the per-game file.** Pair totals for both seasons are sums of per-game rows. No live pull is needed for the matchup model. Last season keeps the regular season, the play-in, the playoffs and the NBA Cup final, and drops preseason.
- **Graded CRUD lands early.** Lineup and report create, read, update and delete (reports with notes only) are done by Nov 24. The AI text is added on Nov 27.
- **Seed files are JSON Lines.** One document per line, one file per collection, so each line maps straight to a MongoDB document and git diffs stay readable.
- **The loader is its own Compose service.** It runs once after MongoDB is healthy, swaps each changed collection in whole, skips files whose SHA-256 fingerprint has not changed, and exits. `web` waits for it.
- **Injury status comes from each team's latest report.** A player who dropped off his team's latest report counts as available.
- **The app shows both the latest game date and the pull time.** "Data as of" alone made people expect today's date, so the top bar reads "Games through ... · pulled ...", and the dot turns amber when the pull is more than 2 days old (changed Nov 18).
- **One command refreshes the data.** `./refresh.sh` runs every R pull script in order, stops with a plain message if one fails, reloads MongoDB and prints the row count change per seed file.
- **Box scores come from player game logs.** Last season's logs are kept in full (about 10 MB). Starters are the five players on the floor at the first play, from the game lineups file. Advanced stats are computed in Python in one place, and the page shows every formula.
- **Big seed files are gzipped, and seed data is committed only at milestones.** `game_logs` and `shots` are `.jsonl.gz`. Refreshed seed data is committed before the demo video and before submitting, not after every refresh, to keep the repo history small.
- **The zone rule lives in R.** Last season's shots have to be grouped by zone inside R to keep the repo small, so the rule is written once there, with checks printed on every run.
- **Positions come from the matchup files, then ESPN.** ESPN players are matched to NBA ids by `pulls/espn_match.R` (name key with suffixes stripped, team tie-breaker, manual overrides, unmatched names printed).
- **Shot sides stay out of the UI** until `pulls/check_sides.R` confirms which way x points.
- **Lineups and reports are user data in MongoDB.** The loader never touches them. Ids are MongoDB ObjectIds, sent as 24-character text. Status overrides apply to one game: only Out excludes a player, default lineups also skip Doubtful players, and a Doubtful player picked by hand gets a warning tag. A report stores a snapshot of the matchup result from the moment it was saved (the server reruns the model on the given lineups, so the snapshot always matches them); its lineups and snapshot cannot be changed later, only its title and notes (and the AI text, later). The app has no user accounts, so saved lineups and reports are shared by everyone using that copy of the app.
- **Badge names live in one config file.** Renaming a badge is one edit.
- **The cut list is the real rule.** The order is in the Timeline section.

## Open items

None of these blocks the build.

- Badge rules: set each badge's cutoff and minimum sample after real data exists.
- Badge names: final names before a public demo.
- Headshot usage terms: check before any public hosted demo.
- Seed file size: check after the first full shot pull, and compress or trim if the repo gets heavy.
- NBA Cup group games: find a source for the icon, such as a note in the ESPN schedule.
- ESPN to NBA team abbreviation map for the stealer tie-breaker.

## Timeline

Due Nov 29, 2026 at 8pm.

1. **Nov 16 to 17.** Confirm every data pull works from the laptop. Done on Nov 16: 30 of 31 file and ESPN pulls passed.
2. **Nov 18 to 20.** Pull scripts, MongoDB collections, Docker skeleton, seed data.
3. **Nov 21 to 22.** API, game context header, team profile, player cards, shot charts.
4. **Nov 23 to 24.** Attributes and trait badges, matchup model with the top three defenders, lineup editor with lineup create, read, update and delete, and reports create, read, update and delete with notes only.
5. **Nov 25 to 26.** Player one-pager, rotation tags and counters. Thanksgiving is Nov 26.
6. **Nov 27.** AI text added to the existing reports, UX polish.
7. **Nov 28.** README, video, push to GitHub.
8. **Nov 29.** Buffer day. Submit before 8pm.

This schedule has no slack before the buffer day. The cut list is the real rule, ahead of "all eight are in the first version". If a step runs long, simplify in this order: rotation counters, then the badges past the first four, then the four extra attributes (catch-and-shoot, post scoring, free throws and drawing fouls, speed), then the NBA Cup and playoff icon.

## Before submitting

- [ ] A fresh clone runs with `docker-compose up --build` and nothing else
- [ ] Seed data ships with the repo, so grading never depends on the NBA stats site
- [ ] `.env.sample` has placeholders, and no real keys exist anywhere in git history
- [ ] README complete: GitHub URL at the top, title, summary, tech stack with versions, run commands and ports, how to run tests, Canvas video link, the four answers
- [ ] A 2 to 3 minute demo video uploaded to Canvas
