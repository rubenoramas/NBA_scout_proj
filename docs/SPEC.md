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

**To do with player cards:** player names in the box score link to that player's card once player cards exist.

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
| Data as of | The date of the last data pull |

Everything here changes daily. Because the app runs from seed data, the header always shows the "data as of" date, and the pulls are rerun right before the demo video and before submitting.

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

The model assigns our five defenders to their five scorers so that the opponent's expected points are as low as possible.

Inputs:

- Matchup history: possessions and points allowed for each defender and scorer pair, for this season and last. Both come from the per-game matchup file, summed into pair totals. The two seasons are blended so this season gains weight as its possessions grow
- Each defender's overall numbers, such as how much worse opponents shoot when he is the closest defender
- Each scorer's volume and efficiency
- Height and weight for everyone, wingspan where combine measurements exist

Steps:

1. Estimate expected points for every defender and scorer pair. Pair history is thin, so it is blended with each player's overall numbers.
2. Weight each pair by how much of the offense the scorer carries.
3. Solve the five-by-five assignment for the lowest total.
4. Show the assignment with a one-line reason for each pairing.

The assignment recomputes whenever a lineup changes. The same scores rank the best three defenders for each opponent player, which feeds the player one-pager.

Known limit: public matchup data is noisy because of switches and help defense. The output is a suggestion, shown with a note on how much data sits behind it.

Check: compare the model's picks with the matchups teams actually used in past games. The per-game matchup file shows who guarded whom in each game.

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
| `shots` | One document per shot: location, shot type, zone, result | Seed loader |
| `matchups` | Totals for each defender and scorer pair | Seed loader |
| `injuries` | Latest status per player | Seed loader |
| `attributes` | Ratings and badges per player | Seed loader, computed in Python at load time |
| `standings` | Record, seed, streak and last ten per team | Seed loader |
| `meta` | The "data as of" date | Seed loader |
| `opponent_lineups` | Most-used fives with tags | Seed loader, tags computed in Python at load time |
| `lineups` | User-set fives with injury tags | User (CRUD) |
| `reports` | Saved scouting reports: inputs, model output, AI text, user notes | User (CRUD) |

## REST API

| Method | Path | Does |
| --- | --- | --- |
| GET | `/api/health` | Says whether the API can reach MongoDB |
| GET | `/api/teams` | List teams |
| GET | `/api/teams/<id>/schedule` | Games for the calendar |
| GET | `/api/teams/<id>/profile` | Team style fingerprint and roster |
| GET | `/api/games/context?us=<team id>&them=<team id>` | Records, seeds, streaks, last games, last meeting, game type |
| GET | `/api/games/<game_id>/boxscore` | Box score: game info, each team's player lines with advanced stats, team totals and four factors |
| GET | `/api/teams/<id>/lineups` | Most-used lineups with tags |
| GET | `/api/players/<id>` | Player card data |
| GET | `/api/players/<id>/shots` | Shots for the shot chart, with filters |
| GET | `/api/players/<id>/onepager?vs=<team id>` | Player one-pager against a chosen team |
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
- **"Data as of" is the date of the latest game in the game logs.** The time of the pull is stored separately.
- **Box scores come from player game logs.** Last season's logs are kept in full (about 10 MB). Starters are the five players on the floor at the first play, from the game lineups file. Advanced stats are computed in Python in one place, and the page shows every formula.
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
