# Prompt log

The class README must list the AI tools used and the exact prompts. Claude Code appends to this file after each task (see CLAUDE.md). Add entries by hand for anything done outside Claude Code.

Format for each entry:

```
## YYYY-MM-DD: short title
Tool: Claude Code (or other)
Prompt:
> the prompt, word for word
Result: one line on what was built or changed
```

## 2026-11-16: project planning
Tool: Claude (chat)
Prompt:
> brain storm me some ideas for sports data science projects i can make, putting on my portfolio and github. ask me as many questions as necessary to come up with 3 good ideas, then i will chose one
Result: chose Opponent Scout, wrote the project spec, and produced the starter files (CLAUDE.md, SPEC.md, pull test script, kickoff prompts)

## 2026-11-16: orientation and repo setup
Tool: Claude Code
Prompt:
> Read CLAUDE.md, docs/SPEC.md and docs/DATA_SOURCES.md fully. Do not write any code yet.
> First, a correction: my class uses GitHub only, not Bitbucket. Update CLAUDE.md, docs/SPEC.md and docs/KICKOFF_PROMPTS.md so every Bitbucket mention says GitHub, and drop the second remote.
> 1. Summarize the project back to me in ten bullets or fewer so I can check you understood it.
> 2. List anything in the spec that is unclear, contradictory, or risky for the Nov 29 deadline.
> 3. Propose the folder structure and the build order, matching the timeline in the spec.
>
> After I approve, make the first commit with the starter files, and show me the exact git commands to connect this folder to my GitHub repo and push. Explain what each command does.
Result: replaced every Bitbucket mention with GitHub in three docs, then reviewed the spec and proposed the folder structure and build order

## 2026-11-16: plan approved, decisions recorded, first commit
Tool: Claude Code
Prompt:
> Approved, with these answers and changes.
>
> Decisions:
> 1. Yes. R only pulls and trims. Python in app/model/ computes ratings, badges and tags. Make the load step skip recomputing when the seed data has not changed, so startup stays fast.
> 2. Yes. NBA stats ids everywhere, and the NBA stats schedule for the calendar. Before building any ESPN crosswalk, check whether headshots can come from the NBA image CDN using the NBA player id. If a test URL loads, use that and keep ESPN only for injuries, matched by name.
> 3. Yes. Boil play-by-play and game lineups down in R to small tables. Keep the R simple and explain it. Check one player's steal total against his game logs so we know the aggregation is right.
> 4. Yes. Lineup CRUD and reports CRUD (notes only) by Nov 24, AI text on Nov 27.
>
> Other calls:
> - The cut list is the real rule. Order: rotation counters, badges past the first four, the four extra attributes, then the NBA Cup and playoff icon.
> - Badge names: keep every badge name in one config file so renaming is one edit. For now use "Deep Range" in place of Limitless Range and "Poster Maker" in place of Posterizer.
> - Do not wait for Nov 17. After the first commit, write a small R script that prints the columns for every table marked "not printed yet" in docs/DATA_SOURCES.md. It should also print the distinct season_type and per_mode values in the play type and hustle files, and whether the play type file has team rows. I will run it and paste the output, then you update DATA_SOURCES.md.
> - Add a placeholder image for missing headshots.
> - Record these decisions in docs/SPEC.md.
>
> My GitHub repo URL: <paste it here>
Result: recorded the decisions in docs/SPEC.md, confirmed headshots load from the NBA image CDN, made the first commit, and wrote pulls/print_columns.R

## 2026-11-16: per-game matchup file added as a data source
Tool: Claude Code
Prompt:
> New verified data source. Add it to docs/DATA_SOURCES.md and docs/SPEC.md, and add a test for it to pulls/test_pulls.R.
>
> This season's matchups ARE available on campus Wi-Fi, in a per-game file:
> - Call: load_nba_stats_game_matchups(seasons = 2026). Last season: seasons = 2025, about 260,000 rows.
> - Checked Nov 16: 37,954 rows covering 187 games, 50 columns.
> - One row per offensive player, defensive player and game.
> - Key columns: game_id, off_team_id, def_team_id, off_person_id, def_person_id, matchup_minutes_sort, partial_possessions, switches_on, player_points, team_points, matchup_assists, matchup_turnovers, matchup_blocks, matchup_field_goals_made, matchup_field_goals_attempted, matchup_three_pointers_made, matchup_three_pointers_attempted, matchup_free_throws_attempted, help_blocks, help_field_goals_attempted, shooting_fouls, season, season_type_id.
> - The season-totals loader (load_nba_stats_matchups) still has no 2026-27 file, so build this season's pair totals by summing the per-game file.
>
> What this changes:
> - The matchup model no longer needs a live pull. Sum the per-game rows into pair totals for both seasons, and blend so this season gains weight with more possessions.
> - The model check gets easier: the per-game file shows who actually guarded whom in each game.
> - Move "Matchups, this season" out of the live-only list.
Result: added the per-game matchup file to docs/DATA_SOURCES.md and docs/SPEC.md, moved this season's matchups out of the live-only list, and added two tests for it to pulls/test_pulls.R

## 2026-11-17: injuries, steals and assists sources
Tool: Claude Code
Prompt:
> Three updates for docs/DATA_SOURCES.md and docs/SPEC.md. Add tests for the first two to pulls/test_pulls.R.
>
> 1. Injuries: use load_nba_stats_injury_report(seasons = 2026) in place of ESPN. Checked Nov 17: 54,695 rows, reports through today. Columns: season, report_datetime, game_date, game_time, report_matchup, away_team_abbr, home_team_abbr, team, report_player_name, current_status, reason, category, previous_status, game_id, team_id, person_id, match_method. It uses NBA ids, so no name matching. Use the latest report per player, and skip rows where reason is "NOT YET SUBMITTED".
>
> 2. Steals: the NBA stats play-by-play file has no steal rows and does not name the stealer, so On-Ball Pest cannot come from it. Test whether ESPN play-by-play (load_nba_pbp(seasons = 2027)) names the stealer on lost-ball turnovers. If it does, use it and match ESPN players to NBA ids by name and team. If not, base On-Ball Pest on steals and deflections per minute, and note that it cannot separate on-ball steals.
>
> 3. Assists: about 65% of made shots name the passer in the description, for example "(Robinson 1 AST)". Match that name to the four teammates on the floor (off_player_1 to off_player_5) to get assist pairs.
>
> Matchups: keep regular season and playoffs from last season, drop preseason, keep the Cup final.
>
> Then commit everything that is not committed yet.
>
> github url: https://github.com/rubenoramas/NBA_scout_proj
Result: confirmed ESPN play-by-play names the stealer (1,299 of 1,327 lost-ball turnovers), recorded injuries, steals, assist pairs and matchup season types in the docs, added injury report and ESPN play-by-play tests, reran the pull test, and committed

## 2026-11-17: name matching answers and Docker skeleton
Tool: Claude Code
Prompt:
> Two quick answers first: keep last season's play-in games. For the ESPN to NBA name match, strip suffixes like Jr., Sr., II and III before matching, and add a small manual override table for any names that still miss, starting with Bobby Portis. Log any unmatched stealer names when the pull runs.
>
> ran the git commands
>
> Plan, then build the smallest working version of the stack:
>
> - docker-compose.yml with two services: the Flask app and MongoDB, with a named volume for the database
> - A Dockerfile for the Flask app with pinned versions in requirements.txt
> - GET /api/health that returns JSON saying whether Flask can reach MongoDB
> - One static page with vanilla JS that calls /api/health with fetch and shows the result, including a loading state and an error state
> - .env loaded for configuration, with the app still starting when ANTHROPIC_API_KEY is missing
> - app/static/img/ with a simple placeholder headshot image for players without a photo
>
> Then walk me through docker-compose.yml line by line. I need to be able to explain it in my demo video. Also tell me the command to check that the containers are running.

Prompt (approval):
> Approved, with three additions:
>
> 1. Keep gunicorn. For development, mount ./app into the container and run gunicorn with --reload so code changes show up without a rebuild. A fresh clone must still start with one command.
> 2. Check whether "docker-compose up --build" (hyphen) works on this Mac, since that is the exact command in the assignment. If only "docker compose" works, tell me, and make sure the README gives a command that works.
> 3. If any pinned version does not exist when you build, switch to the nearest real release and tell me which.
>
> Port 8000 and keeping MongoDB off the host are fine. Go ahead and build it, run your five checks, then do the docker-compose.yml walkthrough. After it all works, commit and push.
Result: built the Docker skeleton (Flask 3.1.3 on gunicorn 27.0.1 with reload, pymongo 4.20.0, mongo:8.0.38, Python 3.13.18), GET /api/health, a status page with loading, success and error states, and a placeholder headshot; recorded the play-in and name matching answers in the docs

## 2026-11-17: first seed pull and the loader
Tool: Claude Code
Prompt:
> Plan, then build the first slice of the data pipeline. Use only sources verified in docs/DATA_SOURCES.md, and follow the season rules in CLAUDE.md.
>
> 1. pulls/pull_core.R writes these to data/seed/ and prints the row count of each:
>    - teams: id, city, name, abbreviation, conference and division, from the standings file
>    - players: bio with height and weight, plus the headshot URL built from the NBA player id
>    - standings: record, seed, current streak and last ten
>    - schedule: the NBA stats schedule, with results for games already played
>    - player game logs for the current season
>    - injuries: the latest official report per player, skipping "NOT YET SUBMITTED" rows
>    - a meta file with the "data as of" date
> 2. A loader that runs when the stack starts and fills MongoDB from data/seed/. Running it twice must not create duplicates, and it skips reloading when the seed files have not changed.
> 3. Indexes that match how the app will look things up, such as players by team and games by date.
> 4. Pick a seed file format and tell me why. Check the total size of data/seed/.
>
> I am new to R and MongoDB. Explain the R script section by section. Explain collections, documents and indexes using our own data, and show me how to look at the loaded data with mongosh inside the container. Then commit and push.

Prompt (approval):
> Approved, with two additions:
>
> 1. Players who are on the injury report but missing from player_bio should still appear. Create a basic player document for each from the injury report (id, name, team), marked as having no stats yet, so they show on the roster with their injury tag. Tell me how many there are.
>
> 2. I added docs/VIDEO_NOTES.md, my study guide for the demo video and README. Commit it. Add this rule to CLAUDE.md under "Working agreements": "After each feature, add a short section to docs/VIDEO_NOTES.md: what it does, how it works in plain words, one design decision worth mentioning, and two or three self-check questions. Keep the existing format." Then add a section for this step, the loader and pull_core.R.
>
> Go ahead and build, then commit and push.
Result: built pulls/pull_core.R (six JSON Lines seed files plus meta.json, 2.07 MB, 51 injured players without stats added), a loader service that swaps in changed collections and skips unchanged files by SHA-256 fingerprint, and indexes; added the VIDEO_NOTES rule to CLAUDE.md and a section for this step

## 2026-11-17: first screen, game context header and tests
Tool: Claude Code
Prompt:
> Plan, then build the first real screen from the spec (step 1 of "Screens and user flow" plus the game context header).
>
> API:
> - GET /api/teams
> - GET /api/teams/<id>/schedule
> - GET /api/games/context?us=<team id>&them=<team id> returning both teams' records and seeds, current streaks and last ten, each team's last game (opponent, score, result, date), the last meeting between the two (date and score, if they have played), and the "data as of" date
>
> Screens:
> - Landing page: pick my team, then see its schedule as a month calendar. Played games show the score and result. Upcoming games are clickable and choose that opponent. Remember my team in the browser so I do not pick it every visit.
> - A search box that scouts any other team instead.
> - A scouting page whose URL includes both teams (for example /scout?us=BOS&them=NYK), so it can be bookmarked or shared. For now it shows only the game context header.
> - Last game standout: propose a rule for a player whose last game was well above his season average, show me the rule, and include it in the header.
>
> Design: aim for a clean, modern sports-analytics look that holds up in a demo video. Use team abbreviations in styled badges, not team logos, since logos are trademarks and this repo will be public. Loading, empty and error states everywhere.
>
> Tests: add pytest now, with tests for the three endpoints, and tell me the command to run them.
>
> Vanilla JS and fetch only. Then commit and push, and add the VIDEO_NOTES section.

Prompt (approval):
> Approved, with two changes:
>
> 1. Standout: keep the points rule, and add the same rule for rebounds (at least 6 more than his average and 1.5 times it) and assists (at least 5 more and 1.5 times). Show whichever stat triggered, with its numbers. If several players or stats qualify, show the biggest jump relative to the average. Show me how many teams have a standout on today's data after the change.
>
> 2. Last meeting: also load last season's schedule (regular season and playoffs, no preseason) so the last meeting can come from last season when the teams have not met this season. Label it with the season, and say when it was a playoff game.
>
> The next meeting, pytest in requirements.txt, and everything else are approved as planned. Build it, run your checks, then commit and push and add the VIDEO_NOTES section.
Result: built the three endpoints, the landing page (team picker, month calendar, search) and the scouting page with the game context header (standout on points, rebounds or assists; last meeting from this season or last; next meeting), added last season's schedule to the pull, and added pytest with 14 passing tests

## 2026-11-17: minutes floor for the standout rule
Tool: Claude Code
Prompt:
> Add a minimum to the standout rule: the player must average at least 15 minutes a game over the earlier games, and play at least 20 minutes in the last game. Show me the new count of teams with a standout and a few examples.
Result: added the minutes floor to the standout rule, the card text and the tests (15 passing); 18 of 30 teams now have a standout

## 2026-11-17: front office console restyle
Tool: Claude Code
Prompt:
> Restyle the whole app to match the new design. Read docs/DESIGN.md first, then the three mockups in docs/design/ (TeamSelect.html, Schedule.html, Scout.html) for exact styles, spacing and structure.
>
> 1. Put the colors from DESIGN.md in :root in style.css as variables, and rebuild the stylesheet around them.
> 2. Rebuild the three existing screens to match the mockups:
>    - First visit: the team selection screen, with teams grouped by conference and division and a filter box.
>    - Landing: the schedule as a table with margin and running record, plus the sidebar with Next game, team snapshot and the mini month view. Upcoming games stay clickable to scout.
>    - Scouting page: the top bar, matchup band and section tabs, then Head to head, Recent results and Last game standouts.
> 3. Keep all existing behavior, API calls and tests working. Only the look and layout change.
> 4. Tabs and buttons for features that are not built yet are disabled and marked "Soon". Do not ship the dashed placeholder panels from the mockup.
> 5. Add a rule to CLAUDE.md under "Working agreements": "All UI follows docs/DESIGN.md. New screens reuse its components and colors."
>
> Show me the plan first. After building, check every screen in the browser, including the loading, empty and error states, then commit and push, and add the VIDEO_NOTES section.

Prompt (approval):
> Approved. Answers:
> 1. Use "Data as of Mon, Nov 16" on the divider, not "Today".
> 2. Self-host Inter: download the font files into app/static/fonts/ and include Inter's license file (OFL.txt) next to them. Only the weights we use: 400, 500, 600, 700.
>
> One check: compute the running record over the whole season from the first game, not only the visible month, so November starts from the record before Nov 1. Verify LAC shows 1-5 after Nov 1 and 4-8 after Nov 15.
>
> Go ahead and build, then run your checks, commit and push.
Result: rebuilt the stylesheet on the DESIGN.md color tokens with self-hosted Inter 4.1; rebuilt team selection, the schedule table with running record and sidebar, and the scouting page with matchup band, tabs and three panels; unfinished features marked "Soon"; added the DESIGN.md rule to CLAUDE.md

## 2026-11-18: box scores
Tool: Claude Code
Prompt:
> Plan, then build box scores. Follow docs/DESIGN.md and use only data in docs/DATA_SOURCES.md.
>
> Data:
> - Box scores come from the player game logs already in MongoDB.
> - Also pull last season's player game logs (regular season, play-in and playoffs) so last meetings from 2025-26 have box scores. Check the seed size afterward.
>
> API:
> - GET /api/games/<game_id>/boxscore: game info and final score, then for each team its player lines, team totals, and four factors for that game.
>
> Box score page (/game/<game_id>):
> - A band with both teams, the final score, the date and the venue.
> - One table per team, sorted by points by default, with sortable column headers and a team totals row.
> - A segmented control switches Basic and Advanced.
>   - Basic: MIN, PTS, FGM-FGA, FG%, 3PM-3PA, 3P%, FTM-FTA, FT%, OREB, DREB, REB, AST, STL, BLK, TOV, PF, +/-.
>   - Advanced: TS%, eFG%, USG%, Game Score, AST/TOV, plus the team four factors (eFG%, TOV%, OREB%, FT rate). Put each formula in a code comment and in a small "How these are calculated" note on the page.
> - Mark starters if the game lineups data can tell us who was on the floor at the start. If not, leave it out and tell me.
>
> Ways in:
> - A "Last game" tab on the schedule panel that shows our team's most recent box score inline, beside the Schedule tab.
> - Played rows in the schedule table get a "Box score" link in the empty last column, and played days on the mini calendar link there too.
> - On the scouting page, every row in Recent results, including the last meeting, links to its box score.
>
> Check one box score by hand: pick a game, and confirm the team totals equal the final score and that one player's TS% and Game Score match the formulas. Add API tests, check every state in the browser, then commit and push and add the VIDEO_NOTES section.

Prompt (approval):
> Approved. Keep all of last season's game logs (about 10 MB).
>
> Two notes:
> 1. Tell me where the 6 play-in games end up, since there is no play-in label. If you can identify them by date or game id, label them Play-in on the box score band.
> 2. When player cards exist in the next step, player names in the box score should link to them. Note that in the spec so it is not forgotten.
>
> Go ahead and build, run the checks and tests, then commit and push.
Result: added last season's game logs and starters to the pull (seed now 13.4 MB), GET /api/games/<game_id>/boxscore with advanced stats and four factors, the /game page with sortable Basic and Advanced tables, a Last game tab, box score links from the schedule, mini calendar and Recent results, and 9 new tests (24 total)

## 2026-11-18: data freshness label and refresh script
Tool: Claude Code
Prompt:
> Two small changes before the shots step.
>
> 1. The "Data as of" label confuses people into expecting today's date. Change it everywhere to show both facts, for example "Games through Tue, Nov 17 · pulled Nov 18, 9:02 AM". Use the latest game date and the pull time already stored in meta. Keep the green dot, and make it amber if the pull is more than 2 days old.
>
> 2. Add one refresh script at the repo root, refresh.sh, that runs every R pull script in order, stops with a plain message if any fails, then reloads MongoDB with the loader. Print what changed (row counts per file). Document it in the README notes and in VIDEO_NOTES.
>
> Then commit and push.
Result: the top bar and schedule divider now read "Games through ... · pulled ...", with an amber dot after 2 days; added refresh.sh (runs the pulls, stops on failure, reloads MongoDB, prints row count changes) and documented it

## 2026-11-18: shots and player cards
Tool: Claude Code
Prompt:
> Plan, then build shots and player cards. Follow docs/DESIGN.md for every screen, and use only data verified in docs/DATA_SOURCES.md.
>
> Data:
> 1. pulls/pull_shots.R: this season shot by shot for all 30 teams, and last season as per-player totals by zone and shot type. Add it to the list in refresh.sh.
> 2. The shots file has no zone columns. Write the rule that turns x_legacy, y_legacy and shot_distance into a zone (restricted area, paint, midrange, corner three, above-the-break three) and a side (left, center, right). Show me the rule and check it against a few shots whose description states the distance.
> 3. Add wingspan from the draft combine files. Pull enough draft classes to cover current players, and tell me what share of players end up with a wingspan.
> 4. Load everything with the seed loader, and check the size of data/seed/. Tell me if it is too big to commit, with options.
>
> API:
> - GET /api/teams/<id>/roster: players with key stats and injury status
> - GET /api/players/<id>: the player card data, including height, weight and wingspan
> - GET /api/players/<id>/shots with filters for shot type and zone
>
> Screens:
> - Turn on the Players tab of the scouting page: the opponent's roster as a table (player, position, minutes, points, rebounds, assists, shooting, injury tag), sortable by column.
> - Clicking a player opens his card: headshot (with the placeholder image when missing), height, weight, wingspan, season line, his last five games linking to their box scores, and his shot profile.
> - Shot profile: a half court drawn in SVG in the design's colors. Makes are filled accent-blue dots and misses are hollow muted rings, so it works for color-blind viewers. Next to it, a zone table with attempts, FG% and the gap to league average in each zone, plus his top three shot types at the rim, in the midrange and from three.
> - Player names in box scores now link to their cards, as noted in the spec.
>
> Add API tests, check every state in the browser, then commit and push and add the VIDEO_NOTES section.

Prompt (approval):
> Approved, with these choices:
>
> 1. Seed size: option A plus B. Gzip game_logs and shots as .jsonl.gz, and only commit refreshed seed data at milestones (before the video and before submitting), not on every refresh. Make refresh.sh say this at the end.
> 2. Zone rule in R is fine.
> 3. Positions: fill the players with no matchup position from ESPN box score positions, using the ESPN-to-NBA name matching already built for steals. Report the coverage after.
> 4. Left and right: instead of a video check, add a small optional script, pulls/check_sides.R, that calls the live nba_shotchartdetail for one player and compares the sign of LOC_X with its SHOT_ZONE_AREA (Left Side, Right Side). I will run it from home internet, since the live site is blocked on campus. Keep sides out of the UI until it confirms.
>
> Go ahead and build, then run the checks and tests, then commit and push.
Result: added pulls/pull_shots.R (zone rule with checks), pulls/espn_match.R, pulls/check_sides.R, season lines, positions (97%) and wingspans (60%) to the core pull; gzipped the big seed files (seed now 5.4 MB); built the roster, player card and shot endpoints, the Players tab, the player card with an SVG shot chart and zone table, and box score name links; 9 new tests (33 total)

## 2026-11-18: ratings and trait badges
Tool: Claude Code
Prompt:
> Plan, then build the twelve attributes and the trait badges. Follow docs/DESIGN.md, and use only data verified in docs/DATA_SOURCES.md. R pulls and trims, and Python in app/model/ computes.
>
> Data (pulls/pull_stats.R, added to refresh.sh), both seasons where available:
> - Play types (one per_mode only), player advanced stats, the tracking tables (drives, passing, rebounding, catch-and-shoot, pull-up, post touches, speed and distance, defense), hustle stats, and combine drills for max vertical.
> - Steals from ESPN play-by-play, split into lost-ball steals and other steals, matched to NBA ids with pulls/espn_match.R. Check one player's steal total against his game logs.
>
> Ratings:
> - Propose which columns feed each of the twelve attributes in docs/SPEC.md, and how they combine into a 0 to 99 rating: a percentile among qualified players, with a minimum-minutes rule.
> - Blend this season with last season, so last season fades as this season's volume grows. Show me the blend formula.
> - Show me every formula before building.
>
> Badges (names from one config file):
> - Build the first four: Deep Range, Streaky Shooter, On-Ball Pest and Poster Maker. Each needs a minimum sample.
> - Streaky Shooter must pass a real statistical test, comparing his make rate after a make with after a miss within games, at a strict threshold. Show the sample size and the test result on the badge.
> - Skip anything that needs live-only data, and list what you skipped.
>
> Screens:
> - Player card: a Ratings panel with all twelve as labeled bars with the number, small-sample tags where they apply, and a Badges row where each badge explains its rule and his numbers on hover and focus.
> - Players tab: add a column with each player's badges.
>
> Before finishing, show me the top ten players for each attribute and each badge, so I can sanity-check them against what I know about the league. Add tests, check the screens in the browser, then commit and push and add the VIDEO_NOTES section.

Prompt (approval):
> Approved, with two changes:
>
> 1. Shooting weights: for three-point shooting, catch-and-shoot and pull-up shooting, use accuracy 0.65 and volume 0.35 in place of 0.5/0.5 and 0.6/0.4. Show me the top ten for each under both weightings so I can compare.
>
> 2. Streaky Shooter: keep the test as planned. In the "how it works" text, add that comparing make rates after makes and misses within games is biased slightly against finding streakiness (Miller and Sanjurjo, 2018), so the test is conservative. If no player qualifies, say so plainly in the sanity list.
>
> Write the final formulas into docs/SPEC.md, then build, run the checks and tests, and commit and push.
Result: wrote the formulas into docs/SPEC.md; added pulls/pull_stats.R (stats, play types, hustle, ESPN steals, shot extras, matchup defense, combine drills); built app/model/ (ratings, badges, badge_config) computed by the loader; ratings panel, badge tooltips and a Players tab badges column; 14 new tests (47 total). No player passed the Streaky Shooter test.

## 2026-11-18: per-36 shrinkage and Poster Maker dunk types
Tool: Claude Code
Prompt:
> Good work. Two changes, then show me the affected top-ten lists again before and after:
>
> 1. Per-36 components inflate low-minute players (see Playmaking, Speed, Interior defense). Shrink every per-36 rate toward the league average by minutes, the same way shooting percentages are shrunk: shrunk rate = (his count + league rate per minute × K) / (his minutes + K), scaled to 36, with K = 400 minutes. Record the formula in docs/SPEC.md.
>
> 2. Poster Maker: count only driving, running and cutting dunks. Leave out alley-oops and putbacks (those fit the future Lob Threat badge). Update the badge text.
>
> Then commit and push.
Result: every per-36 rating component and badge rate is shrunk toward the league by 400 minutes; Poster Maker counts driving, running and cutting dunks only; formula in docs/SPEC.md; 48 tests pass

## 2026-11-18: playmaking, order of operations, usage rate
Tool: Claude Code
Prompt:
> Three follow-ups, then we move on:
>
> 1. Playmaking still favors low-minute backup guards, because AST% is a rate that the per-36 shrinkage does not touch. Rework it as skill plus volume, like the shooting attributes: AST% and AST/TO shrunk toward the league by minutes (0.6), plus potential assists per game (0.4). Show me the top ten before and after.
>
> 2. Show me Stephen Curry's three-point components this season, last season and blended. Check the order of operations: shrinkage should run once, on the blended two-season numbers, not on this season alone before blending. If it runs before blending, fix that and show the three-point top ten again.
>
> 3. Add usage rate (USG%) as a key metric, from usg_pct in the verified player files. It describes role, not skill, so it is a stat with a league rank, not a 0-99 rating.
>    - Player card: USG% in the season line with its league rank, plus last season's value beside it.
>    - Players tab and the team page roster: a USG% column, sortable. Sort the scouting Players tab by USG% by default, so the main options are at the top.
>    - Scouting overview: a small "Who runs the offense" panel with each team's top three players by USG%, alongside their points per game and TS%.
>    - Use the same USG% formula as the box score, and make sure the season value and the box score agree on what it means. Note in docs/SPEC.md that the matchup model will use it to weight scorers.
>
> Show me the top ten by USG% as a sanity check. Then commit and push.
Result: Playmaking reworked as skill (AST%, AST/TOV shrunk by minutes) plus volume (potential assists per game); ratings now blend the seasons first and shrink once; USG% added to the card, the Players tab (default sort) and a "Who runs the offense" panel, checked against the box score formula; 52 tests pass

## 2026-11-18: real rates in tooltips and team pages
Tool: Claude Code
Prompt:
> Two small changes:
>
> 1. Tooltips: rank players on the shrunk values, but show each player's real rate in rating tooltips, with the adjusted value beside it, for example "13.0 per 36 (adjusted 10.9)". Keep K = 400.
>
> 2. Add a team page that works for any team, at /team/<abbreviation>. Follow docs/DESIGN.md and reuse existing components.
>    - Band: record, seed, streak and last ten, like the scouting band.
>    - Tabs: Roster and Team stats.
>      - Roster: the same sortable table as the scouting Players tab, with USG%, badges, injury tags and links to player cards.
>      - Team stats: offensive, defensive and net rating, pace, and the four factors, each with its league rank, from the verified team stats files.
>    - Top bar: add "My team" between Schedule and Scouting, linking to the chosen team's page. Disabled when no team is chosen.
>    - Team chips across the app (schedule, box scores, scouting band, recent results) link to that team's page.
>
> Add tests where new endpoints are needed, check it in the browser, then commit and push and add the VIDEO_NOTES section.
Result: rating tooltips show the real rate with the adjusted value beside it; added team_stats to the core pull, GET /api/teams/<id> with league ranks, the /team/<abbreviation> page (Roster and Team stats tabs, shared roster table), a My team nav item and team chip links across the app; 54 tests pass

## 2026-11-18: matchup model
Tool: Claude Code
Prompt:
> Plan, then build the matchup model. Follow docs/DESIGN.md and docs/SPEC.md, and use only verified data. Python in app/model/ computes. Show me every formula before building.
>
> Data: pair totals for every defender and scorer pair, summed from the per-game matchup files for both seasons, with partial possessions, points, FGA, FGM, 3PA, 3PM, turnovers and switches. Add to the seed and to refresh.sh if a pull changes.
>
> Model, kept interpretable, in points per 100 partial possessions:
> - Scorer baseline: his points per partial possession against all defenders, shrunk toward the league.
> - Defender effect: how many points he allows compared with what his opponents usually score, shrunk toward zero.
> - Pair history: this pair's own result, shrunk toward baseline plus defender effect by its possessions, so thin history barely moves it.
> - Size fit: height, weight and wingspan gaps, where we have them. Show how much it matters.
> - Blend seasons the same way the ratings do.
>
> Assignment:
> - Weight each opposing scorer by his USG%, then pick the five-by-five assignment with the lowest weighted expected points. With five players, checking all 120 orderings is enough, so no new package.
> - Players marked Out are excluded.
> - Until the lineup editor exists, default both lineups to each team's most common starters from the lineup data.
> - For every opposing player, also rank our top three defenders from our whole roster.
> - Each pairing gets a one-line reason built from its components, and a note on how many possessions of history sit behind it.
>
> API: POST /api/matchups with both lineups, returning the assignment, each pairing's expected points and reason, the top three per opposing player, and the history sizes.
>
> Screen: turn on the Matchups tab of the scouting page. A table of their five (sorted by USG%) with our assigned defender, expected points per 100, history size, and the reason, plus each player's top three options. Include a short note that public matchup data is noisy because of switches and help defense.
>
> Validation, and tell me the results:
> - Train on games before Nov 1 and test on games since. Does the model's expected points line up with what scorers actually scored?
> - For this season's games, how often does the model's pick match the defender who actually guarded each scorer most, compared with a simple same-position guess?
>
> Add tests (the assignment picks the true best of 120, Out players excluded, shrinkage at the edges). Check it in the browser, then commit and push and add the VIDEO_NOTES section.

Prompt (approval):
> Approved, keeping k = 200, 300 and 50. Two additions:
>
> 1. Position guard: in the five-on-five assignment and the top three lists, do not allow a guard to guard a center or a center to guard a guard unless that pair has at least 20 partial possessions of history. Positions come from the existing position field. Before applying it, report how often the unconstrained model chose such a pairing in the validation games.
>
> 2. Display: lead with the effect relative to the scorer's norm, E minus B, as "holds him 3.4 below his norm" or "allows 1.2 above his norm", with the sign and color (better in green, worse in red, per DESIGN.md). Show the raw expected points per 100 in the details and the reason line, and explain the unit once in a short note on the tab.
>
> Build it, run the validation and report the numbers, add the tests, check it in the browser, then commit and push and add the VIDEO_NOTES section.
Result: matchup pair and game seed files; app/model/matchups.py (norm, defender effect, size fit, pair history, 120-ordering assignment with a position guard); POST /api/matchups; the Matchups tab; app/model/validate_matchups.py; 7 new tests (61 total). Validation: picks match the real top defender 36.7% vs 43.3% for a same-position guess; the defender effect is confounded with position (centers +5.3, guards -1.5 per 100)

## 2026-11-19: position-relative defender effect and pair history k
Tool: Claude Code
Prompt:
> Yes, make the position-relative change, and tune one more thing while you are in there:
>
> 1. Defender effect: measure each defender against the average defender at his own position, as you recommended.
> 2. Pair history slightly hurts, so it is trusted too early. Try k = 50, 100 and 200 for the pair estimate and keep the best on the test games. Report all three, and note in docs/SPEC.md that k was picked on the same test window, so the result is slightly optimistic.
> 3. Rerun the full validation and show both tables again, before and after. Also show the new defender effect averages by position, and what the model now says about Lillard and Clingan.
> 4. Run the fresh-clone test, since it was skipped for the last two commits.
>
> Record the position problem and its fix in docs/NOTES.md. It is a good README challenge. Then commit and push.
Result: defender effect measured against the average defender at his position (position averages now near 0); pair history k = 200 picked from 50, 100 and 200; validation rerun and recorded in docs/SPEC.md; 2 new tests (63 total); fresh clone checked

## 2026-11-20: lineup editor, saved lineups and saved reports
Tool: Claude Code
Prompt:
> Plan, then build the lineup editor and saved reports. Follow docs/DESIGN.md. This step covers the class requirements for REST create, read, update and delete and MongoDB persistence, so make both clear in the code and the VIDEO_NOTES section.
>
> Lineup editor (turn on the Lineups tab of the scouting page):
> - Two panels, us and them. Each starts from the default lineup (most common healthy starters) and lets me pick exactly five from that team's roster.
> - Injury tags prefill from the official report. I can override any player's status (Out, Doubtful, Questionable, Probable, Available) for this game. An Out player cannot be in a lineup unless I override him.
> - Every change re-runs POST /api/matchups with fetch, and the Matchups tab updates without a page reload. Show a loading state on the matchup table while it recomputes.
> - Validation in the browser and the API: exactly five, no duplicates, nobody Out. Plain error messages.
>
> Saved lineups:
> - POST /api/lineups, GET /api/lineups?team=<id>, GET /api/lineups/<id>, PUT /api/lineups/<id>, DELETE /api/lineups/<id>.
> - A lineup stores its team, a name I give it, the five player ids, the injury overrides, and created and updated times.
> - In the editor: save the current lineup, load a saved one from a dropdown, rename it, and delete it.
>
> Saved reports (notes only for now, AI text comes later):
> - POST /api/reports, GET /api/reports, GET /api/reports/<id>, PUT /api/reports/<id>, DELETE /api/reports/<id>.
> - A report stores both teams, the game if there is one, a title, my notes, both lineups and a snapshot of the matchup assignment at the moment I saved it, created and updated times, and an empty field for the AI text.
> - Report tab on the scouting page: write notes and save the report.
> - Turn on "Saved reports" in the top bar: a page listing reports newest first, with open, edit notes and title, and delete. Delete asks for confirmation inline, not with a browser pop-up.
> - Opening a saved report shows its snapshot as saved, even if the data has changed since.
>
> Explain the MongoDB parts I need to know: how the ids work, why the report keeps a snapshot instead of recomputing, and which indexes you added.
>
> Add tests for every endpoint: create, read one, list, update, delete, validation errors, 404s, and that an injury override changes the matchup result. Check every screen and state in the browser, then commit and push and add the VIDEO_NOTES section.

Prompt (approval):
> Approved. Answers:
> - Keep report lineups and snapshots locked after saving.
> - Only Out excludes a player, but default lineups also skip Doubtful players. I can still pick a Doubtful player by hand, and he gets a warning tag.
> - The 300 ms wait is good.
>
> Also note in docs/NOTES.md, for the README, that the app has no user accounts, so all saved lineups and reports are shared by everyone using that copy of the app.
>
> Go ahead and build, check every screen and state, then commit and push and add the VIDEO_NOTES section.
Result: status overrides in POST /api/matchups; lineups and reports CRUD endpoints over two MongoDB collections with indexes; Lineups tab (editor, overrides, saved lineups), live matchup recompute, Report tab, Saved reports list and report pages; scouting tabs switch without a reload; 8 new tests (71 total)


## 2026-11-20: AI scouting report

Prompt:
> Plan, then build the AI scouting report. Follow docs/DESIGN.md and the honesty rules in CLAUDE.md. The API key is in .env as ANTHROPIC_API_KEY.
>
> Setup:
> - Use the official anthropic Python package, pinned. Pin the model in config: claude-sonnet-5-5 by default, so it is easy to switch to claude-haiku-5-5 if cost matters. Cap max_tokens.
>
> Facts, then text:
> - app/report/facts.py builds one structured facts object from data the app already computes: game context, head to head, who runs the offense, last game standouts, injuries with overrides, the matchup assignment with each effect and its history size, and the key opposing players' ratings and badges.
> - app/report/writer.py sends the facts to Claude with a system prompt that says: use only the numbers in the facts, add no outside knowledge, write in plain coach-style sentences, and say when a sample is small. Ask for JSON with four sections: opponent identity, three keys to the game, players to watch, and matchup notes.
> - After the reply, check that every number in the text appears in the facts. Flag any number that does not, and show the flag on the page. Show me how often it fires on ten test reports.
>
> Screens:
> - Turn on "Generate report" in the scouting band and the Report tab. Clicking it shows a loading state, then the four sections, with the facts used shown beside them in a collapsible panel so every claim can be checked.
> - I can edit the generated text before saving. Saving stores the text, the model name, and a prompt version in the report's AI field. A Regenerate button makes a new draft.
> - Plain errors for no API key (the rest of the app keeps working), an API failure, a timeout, and a rate limit.
>
> Docs: the README must state the exact model and the prompts. Put the system prompt in its own file under app/report/ and log it in docs/PROMPTS.md.
>
> Tests must not call the real API: mock it. Test the facts builder, the number check, the no-key path and the error paths. Then generate one real report for POR vs LAL, check the screens in the browser, commit and push, and add the VIDEO_NOTES section.

Prompt (approval):
> The .env file is in place now with my key. Restart the stack so it picks it up.
>
> Plan approved as written: medium effort, keep the refusal fallback, keep the 1 to 5 allowance, and the ten test reports are fine.
>
> One addition to the number check: also allow dates and season labels that appear in the facts (like "Nov 17" or "2025-26") so they are not flagged.
>
> Build it, run the ten real reports and the POR vs LAL report, tell me the flag rate and which numbers were flagged, then commit and push and add the VIDEO_NOTES section.

Result: app/report/ (facts builder, system prompt file, writer using the anthropic package 2.12.0 with structured JSON output, number check); POST /api/reports/draft with plain errors for no key, rejected key, rate limit, timeout, connection and server errors, refusals and cut-off replies; Generate report in the band and the Report tab with loading, editable sections, Regenerate, number-check flags and a collapsible Facts used panel; AI text saved with model, prompt version, facts and an edited flag; 30 new tests with a mocked client (101 total); 0 flags in 10 real reports on each prompt version

### Model endpoint and system prompt used by the app

Model: `claude-sonnet-5-5` through the Anthropic Messages API (`POST /v1/messages`), effort medium, max_tokens 4000, JSON schema output, server-side refusal fallback (`server-side-fallback-2026-07-01`, fallbacks "default"). `REPORT_MODEL=claude-haiku-5-5` in .env switches to Claude Haiku 5.5. The user message is the word "Facts:" followed by the facts object as JSON.

System prompt, version report-v2 (`app/report/system_prompt.md`):
> You write pregame scouting reports for an NBA coaching staff. You are given one JSON object called the facts. It holds every number you may use.
>
> Rules:
> - Use only the facts. Every number you write must appear in the facts exactly as given (the same rounding, and percentages as given, for example 61.8%). Do not compute new numbers, averages or differences.
> - Add no outside knowledge: no player history, reputations, contracts, injuries or stats that are not in the facts. If the facts do not support a point, leave it out.
> - Say when a sample is small. Anything marked small_sample, small_history or last_season_only must be called out in plain words, for example "on a small sample" or "based on last season".
> - Describe where shots come from and how possessions end. Never describe which way a player drives or dribbles, and never name set plays.
> - "vs_his_norm_per100" below zero means our defender holds the scorer below what he usually scores. Expected points are per 100 partial possessions, the time a defender spends guarding a scorer, and the league average is about 24.
> - Write for coaches: short, plain sentences, no hype, no emoji, no em dashes.
>
> Write four sections:
> 1. opponent_identity: two to four sentences on who the opponent is and how they play, from their record, streak, who runs their offense and their key players.
> 2. keys_to_the_game: exactly three keys, each with a short title and one or two sentences.
> 3. players_to_watch: up to five opposing players who are expected to play, each with a one or two sentence note. A player whose status_for_this_game is Out does not play; mention him only as missing.
> 4. matchup_notes: one note for each pairing in the facts' matchups, naming their player and our defender.

report-v1 was the same text without the last sentence of item 3 (about players whose status is Out). It changed after a POR vs LAL draft could have listed Austin Reaves, who is Out, among the players to watch, because the facts did not say who was playing.


## 2026-11-20: Refresh data button and the optional refresher service

Prompt:
> Plan, then add a "Refresh data" button to the right side of the top bar, next to the freshness line.
>
> Constraint: the pulls are R scripts, and the web container has no R. Build it like this:
> - A separate optional Docker Compose service, "refresher", built from an R image with hoopR, arrow, dplyr and jsonlite installed. Put it behind a Compose profile so the default docker-compose up --build does not build it, and the grader's build stays fast. Prefer prebuilt binary packages so the build does not compile arrow from source.
> - The refresher runs the same pull scripts as refresh.sh, writes to data/seed/, and is reachable only on the internal Docker network.
> - POST /api/refresh starts a refresh job and returns a job id. Only one job can run at a time. GET /api/refresh/<job id> reports its status and current step. When the pulls finish, the web app reloads MongoDB with the existing loader code, then reports what changed.
> - The button: shows the current step while it runs ("Pulling games...", "Reloading database..."), polls the status with fetch, then updates the freshness line and the row-count summary in place. It shows plain errors if a pull fails.
> - If the refresher is not running, the button is disabled with a tooltip explaining how to start it (docker compose --profile refresh up) or to run ./refresh.sh.
> - Refreshed seed files are still not committed automatically. Keep the milestone rule.
>
> Document the profile command in docs/NOTES.md for the README and in VIDEO_NOTES. Add tests for the job endpoints with the refresher mocked. Check it in the browser, including the disabled state, then commit and push.

Prompt (approval):
> Approved. Answers:
> 1. Use rocker/r2u pinned by digest. But check the hoopR version r2u installs: my laptop uses hoopR 3.2.0 from the SportsDataverse r-universe, and loaders like load_nba_stats_game_matchups may be missing in older versions. If r2u's hoopR is older than 3.2.0, install hoopR from https://sportsdataverse.r-universe.dev instead. Make the build fail with a clear message if hoopR is below 3.2.0 or arrow is missing.
> 2. Pin the image digest and record the installed package versions in docs/NOTES.md. No per-package apt pins.
> 3. Keep the refreshed data locally and do not commit it. From now on, stage files by name in commits, so the changed seed files are not swept in by accident until a milestone commit.
>
> Build it, run a real refresh in the browser, then commit and push.

Result: optional "refresher" Compose service behind the refresh profile (rocker/r2u pinned by digest, R packages as binaries, hoopR 3.2.0 from the SportsDataverse r-universe, build check for hoopR and arrow) running the refresh.sh pull scripts through a small standard-library job server on the internal network; POST /api/refresh, GET /api/refresh/<id> and GET /api/refresh/status with jobs in a refresh_jobs MongoDB collection (partial unique index allows one active job) and a reload with the existing loader; Refresh data button in the top bar with steps, polling, in-place freshness and row-count summary, plain errors, and a disabled state with start instructions; 10 new tests with the refresher and loader mocked (111 total); one real refresh run from the browser, seed files kept local and not committed

## 2026-11-25: Player one-pager and Print one-pagers

Prompt:
> Plan, then build the player one-pager from docs/SPEC.md: one printable page on an opposing player, written for the player on our team who will guard him. Follow docs/DESIGN.md on screen, and reuse existing components and data.
>
> Page at /onepager/<player id>?vs=<our team id>, opened from the Players tab and the player card:
> - Header: headshot, name, team, position, height, weight, wingspan, injury status, and his season line with USG% and its rank.
> - Ratings: all twelve as compact bars, with small-sample tags.
> - Badges, with their numbers.
> - Our best three defenders on him from the matchup model, with the effect against his norm and the history size.
> - Favorite shots: his top three shot types at the rim, in the midrange and from three, plus a small shot chart.
> - How he gets his shots: his play type mix with points per possession, and who feeds him most, from the assist data.
> - "How to guard him": two or three sentences from Claude, built from this page's facts only. Reuse the report writer, the honesty rules and the number check. Cache the text in MongoDB by player, opponent, data date and prompt version, so reopening a page does not call the API again. Plain errors and the no-key state, same as the report.
>
> Printing:
> - A print stylesheet: light background, dark text, fits on one US letter page, no top bar or buttons.
> - Turn on "Print one-pagers" in the scouting band: it prints one page per player for their five plus anyone with USG% of 25 or higher, each on its own page.
>
> Add tests with the API mocked (cache hit and miss, no key, the facts builder). Check the screen and print preview in the browser, then commit and push and add the VIDEO_NOTES section.

Result: two new seed files from pulls/pull_stats.R (play_type_mix: every offensive play type per player season; assist_pairs: who assisted whom this season, parsed from the play-by-play shot text, 97.4% of named passers matched to one teammate on the floor); /onepager/<id>?vs= and /onepagers print-all pages; GET /api/players/<id>/onepager and POST /api/players/<id>/onepager/note; "How to guard him" written through the shared report writer (refactored into write()) with its own prompt (onepager-v1) and the number check, cached in a new onepager_notes collection with a unique index on player, our team, data date and prompt version; best three defenders from a new best_defenders() in the matchup service; print stylesheet with print color tokens, one US letter page per player; Print one-pagers enabled in the band (their five plus USG% 25+, not Out, in a new tab); One-pager links in the Players tab and on the player card; 22 new tests with the API mocked (133 total); checked in the browser and as printed PDFs (5 players, 5 pages)

## 2026-11-25: Milestone seed commit, lineup statuses and play type colors on the one-pager

Prompt:
> Three things:
>
> 1. Milestone commit now: commit all the refreshed seed files, including play_type_mix.jsonl and assist_pairs.jsonl, so a fresh clone has complete data. Run the fresh-clone test afterward and confirm the one-pager's play type and assist boxes fill in.
>
> 2. One-pager defenders: when opened from the scouting page, use the lineup editor's current status overrides (passed along when the page opens), and fall back to the official injury report otherwise. Show a small note saying which was used.
>
> 3. Colors: make the one-pager's play type colors match the player card, where green means above league average for that player. Add the words "above league" or "below league" so the scouting meaning is clear without relying on color.
>
> Then commit and push.

Result: milestone commit of all seed files (games through Nov 24, with play_type_mix and assist_pairs); one-pager links from the Players tab and Print one-pagers carry the lineup editor's statuses for our players (us_status=<pid>:<status>,...), the best defenders leave out the same Out players as the Matchups tab, and a note says "Lineup editor" or "Official report"; the cached "How to guard him" key now includes our Out players, so a text never recommends a defender marked Out (unique index rebuilt with five fields); play types colored like the player card (green above league, red below) with a "vs League" column in words; 6 new tests (139 total); fresh clone from GitHub started with docker-compose up --build and filled the play type and assist boxes

## 2026-11-25: Series history, schedule spots and where they give up shots

Prompt:
> Plan, then build three additions. Follow docs/DESIGN.md, reuse existing data and components, and use only verified data.
>
> 1. Series history, on the scouting Overview:
>    - Every meeting between the two teams this season and last season, playoffs and play-in included, newest first: date, venue, result for us, score, game type tag, and a box score link where one exists.
>    - A series record for each season.
>    - Matchups from any meeting: pick a meeting and see who actually guarded whom, from the per-game matchup data. Show both directions, their scorers against our defenders and ours against theirs: the defender with the most partial possessions on each scorer, the possessions, and the points and shooting allowed. Default to the most recent meeting that has matchup data.
>    - On the Matchups tab, add a column beside the model's pick: who guarded that scorer most in the last meeting, with possessions.
>
> 2. Schedule spots, for both teams around this game:
>    - Days of rest before the game, back-to-back, 3 games in 4 nights, 4 in 6, and the current road trip or home stand length.
>    - Show them as small tags in the scouting band and on the schedule table's upcoming rows. Facts only, with no claims about fatigue effects.
>
> 3. Where they give up shots: a team defense shot profile from opponents' shots against that team this season, with a zone table (share of attempts and FG% allowed, compared with league average) and a shot chart. Put it on the team page's Team stats tab, and on the scouting Overview for the opponent.
>
> Add tests, check every screen in the browser, then commit and push and add the VIDEO_NOTES section.

Result: new seed file matchup_top.jsonl.gz from pulls/pull_stats.R (each scorer's top defender in every game this season and last, all game types: 34,440 rows, 1.5 MB, instead of about 310,000 pair rows); GET /api/games/series, GET /api/games/<id>/guarded and GET /api/teams/<id>/defense-shots; Series history and Who guarded whom panels on the scouting Overview (meeting picker, both directions, defaults to the newest meeting with matchup data); "Guarded most, last meeting" column on the Matchups tab (old saved reports show a dash); schedule spots (rest days, back-to-back, 3 in 4, 4 in 6, road trip or home stand N of M) as tags in the scouting band and on the schedule's upcoming rows for both teams; "Where they give up shots" zone table and opponent shot chart on the team page's Team stats tab and the scouting Overview; 18 new tests (157 total); every screen checked in the browser, including playoff, play-in and NBA Cup final meetings
