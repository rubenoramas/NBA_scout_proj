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
