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
