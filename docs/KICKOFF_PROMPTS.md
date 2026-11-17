# Kickoff prompts for Claude Code

Use these in order. Read each plan before saying yes. After each prompt works, commit.

## Already done (Nov 16)

- R 4.6.2, hoopR 3.2.0 and the arrow package are installed.
- The project lives in `~/Projects/NBA_scout_proj`, outside iCloud.
- `pulls/test_pulls.R` ran: 30 of 31 file and ESPN pulls passed. The results are in `pulls/test_pulls_results.csv`, and the verified sources and column names are in `docs/DATA_SOURCES.md`.

## Before the first prompt (you, not Claude Code)

1. In Terminal, from the project folder, run `git init`.
2. Create an empty repo on GitHub. Prompt 1 connects this folder to it.
3. Open the folder in VS Code and start Claude Code.

## Prompt 1: orient, then set up the repo

```
Read CLAUDE.md, docs/SPEC.md and docs/DATA_SOURCES.md fully. Do not write any code yet.

1. Summarize the project back to me in ten bullets or fewer so I can check you understood it.
2. List anything in the spec that is unclear, contradictory, or risky for the Nov 29 deadline.
3. Propose the folder structure and the build order, matching the timeline in the spec.

After I approve, make the first commit with the starter files, and show me the exact git commands to connect this folder to my GitHub repo and push. Explain what each command does.
```

## Prompt 2: Docker skeleton

```
Plan, then build the smallest working version of the stack:

- docker-compose.yml with two services: the Flask app and MongoDB, with a named volume for the database
- A Dockerfile for the Flask app with pinned versions in requirements.txt
- GET /api/health that returns JSON saying whether Flask can reach MongoDB
- One static page with vanilla JS that calls /api/health with fetch and shows the result, including a loading state and an error state
- .env loaded for configuration, with the app still starting when ANTHROPIC_API_KEY is missing

Then walk me through docker-compose.yml line by line. I need to be able to explain it in my demo video.
```

## Prompt 3: first seed pull and the loader

```
Plan, then build the first slice of the data pipeline, using only the sources verified in docs/DATA_SOURCES.md:

1. pulls/pull_core.R: pulls teams, players (bio with height and weight), standings, the schedule and player game logs for the current season, and writes them to data/seed/ as JSON files. Follow the season rules in CLAUDE.md. Print the row count of every table it writes.
2. Use NBA stats ids everywhere. Headshots load from the NBA image CDN by player id. Injuries come from ESPN and are matched to players by name. Tell me the matching approach before building it.
3. A loader that runs when the stack starts and fills MongoDB from data/seed/. Running it twice must not create duplicates. Store the "data as of" date.
4. Sensible indexes for how the app will look things up.

I am new to R and MongoDB. Explain the R script section by section, explain collections, documents and indexes using our own data as the example, and show me how to look at the data with mongosh inside the container.
```

## Prompt 4: first screen

```
Plan, then build the first real screen from the spec (step 1 of "Screens and user flow"):

- GET /api/teams and GET /api/teams/<id>/schedule
- A landing page where I pick my team, see its schedule as a calendar, and click an upcoming game to choose that opponent
- A search box that lets me pick any other team to scout instead
- Picking an opponent goes to a scouting page that shows the game context header from the spec: both records and seeds, streaks, each team's last game with date, and the last meeting

Vanilla JS and fetch only. Include loading and error states. Add API tests for the endpoints and tell me the command to run them.
```

## Prompt 5: shots and the shot chart

```
Plan, then build shot data end to end, using the shots file described in docs/DATA_SOURCES.md:

1. pulls/pull_shots.R: this season shot by shot for all 30 teams, and last season as per-player totals by zone and shot type.
2. The shots file has no zone columns. Write the rule that turns x_legacy, y_legacy and shot_distance into a zone (rim, paint, midrange, corner three, above-the-break three) and a side (left, center, right). Show me the rule and check it against a few shots whose description states the distance.
3. Load both into MongoDB with the seed loader.
4. GET /api/players/<id>/shots with filters for shot type and zone.
5. A shot chart on the player card: a half court drawn in the browser with makes and misses, plus his top shot types at the rim, in the midrange, and from three.

Check the size of the seed files and tell me if they are too big to commit comfortably, with options if they are.
```

## Prompt 6: ratings and trait badges

```
Plan, then build the twelve attributes and the trait badges from the spec, using only data verified in docs/DATA_SOURCES.md:

1. For each attribute, propose which columns feed it and how they combine into a 0 to 99 rating. Blend this season with last season so that last season fades as this season's volume grows. Show me the formula before building.
2. Build the first four badges: Deep Range, Streaky Shooter, On-Ball Pest and Poster Maker. Each needs a minimum sample, and Streaky Shooter must show its sample size.
3. Skip any badge or input that needs live-only data, and list what you skipped.
4. Show me the top ten players for each attribute and each badge so I can sanity-check them against what I know about the league.
```

## After prompt 6

Keep following the timeline in `docs/SPEC.md`: the matchup model with the top three defenders, the lineup editor, the player one-pager, rotation scouting, AI reports, then the README and video. Write each prompt the same way: say what to build, point at the section of the spec, ask for a plan first, and ask for an explanation of anything new.

## Optional: live pulls from a hotspot

The live NBA stats site does not answer from campus Wi-Fi. If you want the live-only extras listed at the bottom of `docs/DATA_SOURCES.md`, connect to a phone hotspot, run `Rscript pulls/test_pulls.R` to confirm the live tests pass, then ask Claude Code to write `pulls/pull_live.R` for the items you want.
