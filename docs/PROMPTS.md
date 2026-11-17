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
