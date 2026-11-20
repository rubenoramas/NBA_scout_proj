# Build notes

Short notes on problems hit and how they were solved. These become the README answers to "What did you learn?" and "What were the main technical challenges?", written in your own words at the end.

Format for each entry:

```
## YYYY-MM-DD: what went wrong or what was hard
What happened:
What fixed it:
What I learned:
```

## Known going in

- The NBA stats site blocks cloud servers, so data pulls run on a laptop and the app ships with seed data.
- hoopR's NBA functions default to last season, so every call has to pass the season.
- Public data has shot location and shot type for every shot, but not the direction a player was moving and not named set plays.
- The season is about a month old, so ratings blend this season with last season.

## 2026-11-16: the NBA stats site would not answer from campus Wi-Fi
What happened: the first data pull hung with no output. A direct request to stats.nba.com timed out after 20 seconds with 0 bytes received, while ESPN answered in 0.2 seconds on the same connection.
What fixed it: switched the main data route to hoopR's pre-pulled files (`load_nba_stats_*`), which download from GitHub and are not blocked. The live site is now only needed for a short optional list.
What I learned: (yours to fill in)

## 2026-11-16: a time limit crashed the test script
What happened: the test used R's `setTimeLimit` to cap a slow request. When the limit fired during a download, the script halted with "reached elapsed time limit" where it should have recorded a failure.
What fixed it: put the timeout on the request itself (a curl timeout), which fails as a normal error that `tryCatch` can handle.
What I learned: (yours to fill in)

## 2026-11-16: most data files came back empty
What happened: 21 of the file pulls returned 0 rows with a warning.
What fixed it: the files are in Parquet format and R needs the arrow package to read them. After `install.packages("arrow")`, 20 of the 21 passed. The last one, this season's matchups, is simply not published yet.
What I learned: (yours to fill in)

## 2026-11-17: the NBA play-by-play does not say who made a steal
What happened: the On-Ball Pest badge needs steals on lost-ball turnovers, but the NBA stats play-by-play file has no steal rows and never names the stealer.
What fixed it: ESPN's play-by-play names the stealer on each turnover ("(Anthony Black steals)"). ESPN names were matched to NBA ids by name, which worked for 404 of 405 players. A check on one player gave 19 steals in both ESPN play-by-play and the NBA game logs.
What I learned: (yours to fill in)

## 2026-11-17: the latest injury row was the wrong answer
What happened: the plan was to take each player's latest row in the injury report. But a player who recovers just stops appearing on the report, so his latest row would say Out forever. Also, 51 injured players had not played yet and were missing from the player bio file, so they would not show on rosters at all.
What fixed it: use each team's most recent report, and treat players not on it as available. Players on the report but missing from the bio file get a basic player document marked has_stats false.
What I learned: (yours to fill in)

## 2026-11-17: HTML changes did not show up after saving
What happened: after editing a template, the browser still showed the old page, even though gunicorn's --reload was on.
What fixed it: --reload only watches Python files, and Flask keeps templates in memory. Setting TEMPLATES_AUTO_RELOAD makes Flask re-read a template when it changes.
What I learned: (yours to fill in)

## 2026-11-17: table rows rendered as "[object HTMLDivElement]"
What happened: after the redesign, the Recent results panel showed the text "[object HTMLDivElement]" instead of its rows.
What fixed it: the helper that builds page elements flattened nested lists only one level deep, so a list of rows inside a list was turned into text. Flattening all the way down (flat(Infinity)) fixed it.
What I learned: (yours to fill in)

## 2026-11-18: last season's data could leak into this season's numbers
What happened: box scores needed last season's player game logs in the same collection. The standout rule averages each player's earlier games, and without a filter those averages would have quietly included last season.
What fixed it: every game log line now carries a season, the standout query filters on it, and a test adds a 50 point game from last season to prove it is ignored. Also found: the play-in games are missing from the NBA game log file, so they show a score with a plain note instead of a box score.
What I learned: (yours to fill in)

## For the README: refreshing the data

Run this from the repo root on your laptop, with Docker running:

```
./refresh.sh
```

It runs every R pull script in `pulls/` in order (today only `pull_core.R`), stops with a plain message if one fails, reloads MongoDB with the loader, and prints the row count of each seed file before and after. It needs R with hoopR, arrow, dplyr and jsonlite. The optional live pull (`pulls/pull_live.R`, hotspot only) is not part of it. The top bar then shows "Games through <latest game> · pulled <time>", with an amber dot if the pull is more than 2 days old.

## 2026-11-18: which way is left on the shot chart?
What happened: the shots file gives x and y for every shot, but nothing in the pre-pulled files says whether positive x is the shooter's left or right. Every zone could be checked against the written distance, but the side could not.
What fixed it: the app keeps sides out of the UI, and pulls/check_sides.R compares the sign of x with the live shot chart's "Left Side" and "Right Side" labels. The live site is blocked on campus, so it has to be run from home internet.
What I learned: (yours to fill in)

## 2026-11-18: the seed folder was getting too big
What happened: adding shot-by-shot data would have pushed data/seed/ to about 20 MB, and every committed refresh would add that much to the repo history again.
What fixed it: the two biggest files are gzip-compressed (13 MB down to about 3 MB) and the loader reads them directly. Refreshed seed data is committed only at milestones, and refresh.sh says so when it finishes.
What I learned: (yours to fill in)

## 2026-11-18: a fair test for the Streaky Shooter badge
What happened: testing 270 players at the usual 5% level would give about 13 "streaky" players by pure luck.
What fixed it: a one-sided two-proportion z-test with a Bonferroni threshold (0.05 / 270 = 0.00019). Nobody passes yet; the closest is p = 0.001. The card shows the test result either way.
What I learned: (yours to fill in)

## 2026-11-18: guessed column names broke the stats pull
What happened: the first run of pull_stats.R stopped on "object 'catch_shoot_fg3m' not found". The real columns are catch_shoot_fg3_m and pull_up_fg3_m, as DATA_SOURCES.md lists.
What fixed it: using the names from DATA_SOURCES.md. CLAUDE.md already says not to guess column names.
What I learned: (yours to fill in)

## 2026-11-18: the ratings shrank this season before blending
What happened: each season's shooting rate was pulled toward the league on its own small sample, then the two were blended. Stephen Curry's 45.7% on 94 threes was cut to 42.1% before last season was even mixed in, so this season was shrunk twice.
What fixed it: blend the two seasons first (rate, sample and league rate, each weighted by w), then shrink once on the blended numbers. Curry's blended 3P% went from 39.9% to 40.6%.
What I learned: (yours to fill in)

## 2026-11-18: testing the matchup model, and what the test exposed
What happened: the matchup model looked sensible on one game but ranked Damian Lillard as the best option against every scorer, and said a top rim protector allowed 15 points per 100 above expected. Averaging the defender effect by position showed why: centers average +5.3 and guards -1.5, because bigs are matched to scorers near the rim.
What fixed it: not fixed yet. The validation (train before Nov 1, test after) is reported honestly: the model's picks match the real top defender 37% of the time, below a same-position guess at 43%. A position-relative defender effect is the proposed fix. A unit test also caught a bug where a player with no minutes on record lost all his data in the blend.
What I learned: (yours to fill in)

## 2026-11-19: the position problem in the matchup model, fixed
What happened: the matchup model rated Damian Lillard as the best option against every scorer and a top rim protector as one of the worst. The defender effect compared every defender with the whole league, but bigs are matched to scorers in high-scoring moments near the rim, so centers averaged +5.3 points per 100 above expected and guards -1.5.
What fixed it: each defender is now measured against the average defender at his own position (that average is taken out before the shrinkage and before the size fit). The averages by position went from C +5.3, F -1.0, G -1.5 to C -0.2, F -0.0, G -0.1. The same validation showed pair history was trusted too early, so its k went from 50 to 200 (picked on the test window itself, so slightly optimistic). Raw prediction dropped slightly (0.181 to 0.178), which is the honest cost of removing an offset that is real in the data but is not defense.
What I learned: (yours to fill in)

## For the README: no user accounts
The app has no user accounts or logins. All saved lineups and reports live in one MongoDB database, so everyone using a given copy of the app (one `docker-compose up`) sees and can edit the same saved lineups and reports. That is fine for a single coaching staff on one machine; accounts would be the next step for a shared deployment.

## 2026-11-20: keeping saved reports stable while the data changes daily
What happened: a saved report would read differently every day if it recomputed its matchups from the latest data, so notes written last week could stop matching the numbers beside them.
What fixed it: the report stores a snapshot of the full matchup result when it is saved, computed by the server from the saved lineups. Only the title and notes can change afterwards; a test changes the data and checks the snapshot stays the same.
What I learned: (yours to fill in)


## 2026-11-20: checking that the AI report uses only our numbers
What happened: the AI report must not invent stats, but reading every draft by hand does not scale. The number check compares every number in the text with every number in the facts. In 20 real reports (10 matchups on each prompt version, about 710 numbers per 10 reports) it fired 0 times. A test with made-up numbers showed why that is not the whole story: the facts hold about 66 of the 100 whole numbers from 0 to 99 (mostly ratings), so a random wrong whole number slips through about two times in three. A random wrong decimal like 38.2% is caught about 8 times in 10.
What fixed it: the check flags anything not in the facts and shows the flag on the page, and the Facts used panel sits beside the text so a reader can check the rest. A stronger check would tie each number to the player named in the same sentence.
What I learned: (yours to fill in)

## 2026-11-20: the AI almost featured an injured player
What happened: the key opposing players in the facts include anyone with a 25% usage rate, and Austin Reaves qualified even though he is Out. Nothing in his entry said so, so the model could list him as a player to watch.
What fixed it: each key player now carries status_for_this_game, and the system prompt says an Out player is mentioned only as missing (prompt version report-v2). In the 10-report rerun, the one Out player named under players to watch was described as missing.
What I learned: (yours to fill in)

## For the README: the AI model and prompts
The AI report uses `claude-sonnet-5-5` through the Anthropic Messages API with the official `anthropic` Python package 2.12.0, effort medium, max_tokens 4000 and JSON schema output. Set `REPORT_MODEL=claude-haiku-5-5` in .env to use Claude Haiku 5.5 instead. The system prompt is in `app/report/system_prompt.md` (version report-v2) and is quoted in `docs/PROMPTS.md`. A report costs about 3.3 cents with Sonnet 5.5 (about 9,000 input and 1,450 output tokens) and takes about 10 seconds. Without ANTHROPIC_API_KEY the app starts normally and the report screens say to add a key.


## For the README: refreshing from the app (optional)
The "Refresh data" button in the top bar runs the same R pulls as `./refresh.sh` inside an optional container, so R does not have to be installed on the laptop. It is off by default, and the normal `docker-compose up --build` does not build it. To use it:

```
docker compose --profile refresh up --build
```

The first build downloads an R image and takes a few minutes. The button then shows each step and a table of what changed. A full refresh takes several minutes. Keep the laptop awake and plugged in: a sleeping laptop freezes Docker and the pulls stall. Without the profile, the button is disabled and its tooltip says how to start it. The refresher has no port on the host; only the web container can reach it.

Refreshed seed files are not committed automatically. Commit `data/seed/` only at milestones (before the demo video and before submitting).

Refresher image and package versions (recorded 2026-11-20):
- Image: `rocker/r2u:24.04@sha256:cf1c8151046db092ec3d4c45bdc67488f0221263f9e857390f367a41b20c953c`, R 4.6.2
- hoopR 3.2.0 (from https://sportsdataverse.r-universe.dev, because r2u has 3.1.0), arrow 26.0.1, dplyr 1.2.1, jsonlite 2.0.0 (prebuilt binaries from r2u)
- The build stops with "BUILD CHECK FAILED" if hoopR is older than 3.2.0 or arrow is missing. The versions are printed in the build log.

## 2026-11-20: one refresh at a time across two web workers
What happened: gunicorn runs two worker processes, so a job kept in memory by the worker that started it is invisible to the other worker that answers the next status poll.
What fixed it: jobs live in a MongoDB collection, refresh_jobs. A partial unique index on "active" (only documents with active: true) makes the database reject a second running job, even if two clicks land at once. When the pulls finish, one request claims the reload with find_one_and_update, so the loader never runs twice.
What I learned: (yours to fill in)

## 2026-11-20: a refresh that never finished
What happened: the first real refresh sat on "Steals from ESPN play-by-play" for 20 minutes. The same download takes about 3 seconds when tested alone. The laptop was asleep on battery for much of that time, which freezes the Docker VM and can leave a download hanging forever, and hoopR's downloads have no timeout of their own. The time limit in the job server was only checked when R printed a line, so a silent hang was never stopped.
What fixed it: a watchdog timer kills a pull script after 20 minutes even if it prints nothing, and the page then says which pull failed. Run refreshes with the laptop awake and plugged in; the second run finished and loaded 368 new box score lines.
What I learned: (yours to fill in)
