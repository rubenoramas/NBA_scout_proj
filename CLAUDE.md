# Opponent Scout

Opponent Scout is a web app that builds a pregame scouting report on an NBA opponent: how the team plays, where each player scores from, and who should guard whom. The full plan is in `docs/SPEC.md`. Read it before planning any feature.

This repo is a graded CS class project ("Build something cool with AI", due Nov 29, 2026 at 8pm) and a public portfolio piece. The class rules below are requirements, not preferences.

## Required stack (class rule)

- Docker: the whole app starts with `docker-compose up --build` from a fresh clone, with no other setup steps.
- Flask: the backend is a Flask API server.
- Frontend: vanilla JavaScript calling the API with `fetch`. No React, Vue, or other frontend framework. A small charting or court-drawing library is acceptable if the README lists it.
- MongoDB: all application data lives in MongoDB.
- REST: clear REST endpoints. Lineups and reports support create, read, update and delete.
- UX: every async action shows a loading state, validates input, and reports errors in plain words.

Changing any item in this list breaks the assignment. If a task seems to need a different tool, stop and say so instead of switching.

## Secrets (class rule)

- No real credentials are ever committed. This includes API keys in code, config, tests, logs and example output.
- The Claude API key is read from the `ANTHROPIC_API_KEY` environment variable, supplied through a local `.env` file that is git-ignored.
- `.env.sample` holds placeholder values only and is the file the README points to.
- The app still starts and every non-AI page still works when the key is missing. AI features then show a clear "add an API key" message.

## How data gets in

`docs/DATA_SOURCES.md` lists every verified data source with its call, row count and column names. Read it before writing any pull script, and do not guess column names.

- Pull scripts are written in R with the hoopR package and live in `pulls/`. They run on the developer's laptop, never inside Docker.
- The main route is hoopR's pre-pulled files (`load_nba_stats_*`), then ESPN (`load_nba_*`, `espn_nba_*`). Both work on any network.
- The live NBA stats site (`nba_*` functions) gives no answer from the developer's campus Wi-Fi. Live pulls go in a separate script, `pulls/pull_live.R`, that the developer runs from a phone hotspot. Everything it produces is optional, and the app works without it.
- Season arguments differ by function family. `load_nba_stats_*` takes the START year (2026 for 2026-27). ESPN `load_nba_*` takes the END year (2027). Live `nba_*` functions take "2026-27" and default to last season, so `season` is always passed.
- The arrow package is required. Without it most `load_nba_stats_*` calls return an empty table.
- Pull scripts write seed files to `data/seed/`. Seed files are committed to the repo.
- A loader inside Docker fills MongoDB from the seed files at startup. Loading twice does not create duplicates.
- The running app never calls hoopR, ESPN or the NBA stats site. It reads only from MongoDB.
- The data changes daily. The app shows a "data as of" date, and the pulls are rerun before the demo video and before submitting.
- `pulls/test_pulls.R` tests every data source. Its latest output is `pulls/test_pulls_results.csv`.

## Repo layout

- `app/`: Flask app (API routes, matchup model, report builder)
- `app/static/` and `app/templates/`: vanilla JS, CSS, HTML
- `pulls/`: R pull scripts
- `data/seed/`: seed files loaded into MongoDB
- `tests/`: API tests
- `docs/SPEC.md`: the plan
- `docs/DATA_SOURCES.md`: verified data sources and column names
- `docs/PROMPTS.md`: prompt log for the README
- `docs/NOTES.md`: problems hit and how they were solved
- `docker-compose.yml`, `Dockerfile`, `.env.sample`, `README.md`

## Working agreements

- The developer is learning MongoDB and R on this project, and has to explain the app in a demo video. When a task introduces a new MongoDB or R concept, explain it in a few plain sentences before or after the change.
- For any feature, propose a short plan first and wait for approval before writing code.
- Build one feature at a time, in the order of the timeline in `docs/SPEC.md`. Finish and verify a feature before starting the next.
- After finishing a task, append the developer's prompt, word for word, plus a one-line summary of what was built, to `docs/PROMPTS.md`. The README must quote exact prompts.
- When a bug or design problem takes real effort to solve, add two or three lines about it to `docs/NOTES.md`.
- Pin exact versions of Flask, the MongoDB image and every Python package. The README must state them.
- Ask before adding a new dependency.
- Verify changes by running the app with `docker-compose up --build`, not only by reading the code.
- Written text in the README and the UI uses plain sentences with no em dashes.
- After each feature, add a short section to docs/VIDEO_NOTES.md: what it does, how it works in plain words, one design decision worth mentioning, and two or three self-check questions. Keep the existing format.

## Honesty rules for the product

- The LLM writes only from numbers the app computed and passed to it. It never supplies stats from its own knowledge.
- Public data has no dribble or drive direction. The app describes where a shot was taken (side of the floor), never which way the player was going.
- Public data has no named set plays. The app describes play types (isolation, pick and roll, spot up), not called plays.
- Any rating or matchup based on a small sample shows that it is a small sample.
- Badge names and art are original, not copied from NBA 2K.

## README requirements (class rule)

The README must include, in this order: the GitHub URL at the top, project title and one-sentence summary, tech stack with explicit versions, exact commands to run locally and the ports used, how to run tests, the Canvas video link, and plain-text answers to four questions:

1. What is cool about your project?
2. What AI tools did you use, and for what specific tasks? Include exact prompts or model endpoints.
3. What did you learn by building the project?
4. What were the main technical challenges, and how did you solve them?

Answers 3 and 4 are written by the developer in his own words. Draft notes for them live in `docs/NOTES.md`.
