https://github.com/rubenoramas/NBA_scout_proj

# Opponent Scout

Opponent Scout builds a pregame scouting report on any NBA opponent: how the team plays, where each player scores from, who should guard whom, and a written report from Claude that uses only numbers the app computed.

## Tech stack

| Part | Version |
| --- | --- |
| Docker | Docker 29.8.2, Docker Compose v5.6.0 (the versions the app was built and tested with) |
| Python | 3.13.18 (`python:3.13.18-slim-bookworm` image) |
| Flask | 3.1.3 |
| gunicorn | 27.0.1 |
| pymongo | 4.20.0 |
| MongoDB | 8.0.38 (`mongo:8.0.38` image) |
| anthropic (Python package) | 2.12.0 |
| pytest | 9.2.0 |
| R | 4.6.2, for the data pulls only (on the laptop, or in the optional refresher container) |
| hoopR | 3.2.0, with arrow 26.0.1, dplyr 1.2.1 and jsonlite 2.0.0 |
| Font | Inter 4.1, self-hosted in `app/static/fonts/` (SIL Open Font License) |
| JavaScript | No JS libraries. The frontend is vanilla JavaScript calling the API with `fetch`; shot charts are hand-drawn SVG. |

Python package versions are pinned in `requirements.txt`. The refresher container uses `rocker/r2u:24.04`, pinned by digest in `refresher/Dockerfile`.

## How to run locally

From a fresh clone, with Docker running:

```
git clone https://github.com/rubenoramas/NBA_scout_proj.git
cd NBA_scout_proj
docker-compose up --build
```

Open http://localhost:8000. The app listens on port 8000. MongoDB runs inside Docker and has no port on the host. On first start the loader fills MongoDB from the seed files in `data/seed/`, which ship with the repo, so no other setup is needed.

**Optional: AI features.** The app starts and every non-AI page works without a key. To turn on the AI report and the one-pager's "How to guard him" text:

```
cp .env.sample .env
```

Then replace `your-key-here` in `.env` with an Anthropic API key and restart (`docker-compose up --build`). `.env` is git-ignored. To use Claude Haiku 5.5 instead of Sonnet 5.5, add `REPORT_MODEL=claude-haiku-5-5` to `.env`.

**Optional: refresh the data.** The data changes daily. Two ways to update it:

- From the app: start with the refresher container, then use the Refresh data button in the top bar.

  ```
  docker compose --profile refresh up --build
  ```

- From the laptop, with R 4.6 and hoopR 3.2.0, arrow, dplyr and jsonlite installed, and Docker running:

  ```
  ./refresh.sh
  ```

  It runs every pull script in `pulls/`, reloads MongoDB and prints how many rows each seed file gained.

## How to run tests

With the app's containers available (the command starts MongoDB if needed):

```
docker compose run --rm web pytest
```

The tests use a separate database, `opponent_scout_test`, and never call the real Claude API.

## Video

Canvas video link: [ADD CANVAS VIDEO LINK]

## What is cool about your project?

- It scouts any team against any team from free public data: shot charts, twelve 0 to 99 ratings, original trait badges, play types, and who feeds each player, parsed from play-by-play text.
- A matchup model suggests who should guard whom, in points per 100 partial possessions. It was validated on games it had not seen, and the validation exposed a position bias (centers looked worse, guards better) that was then fixed.
- The AI report is written only from a facts object the app builds. Every number in the text is checked against those facts, and the facts are shown beside the text so any claim can be traced.
- A printable one-pager per opposing player, with "How to guard him" from Claude, cached in MongoDB so a page is written once per data date.
- On/off impact from every stretch of play in two seasons, with free throws credited to the players on the floor at the foul. Summed points match every final score.
- A game preview with a projected margin and win probability, validated against simple baselines, with a test that fails if a projection uses the game itself or a later game. Each data pull saves projections, so the app keeps an honest running record.
- Rotation scouting tags the opponent's most-used lineups and suggests a counter five from our healthy roster, which loads into the lineup editor in one click.
- The whole app starts with `docker-compose up --build`, runs from seed data in MongoDB, and never calls the NBA site while running.

## What AI tools did you use, and for what specific tasks?

- **Claude chat** for planning, data research and writing the build prompts.
- **Claude Code** for building: it wrote most of the code from my prompts. Every prompt is logged word for word, with a one-line result, in [`docs/PROMPTS.md`](docs/PROMPTS.md).
- **Claude inside the app:**
  - Model: `claude-sonnet-5-5` through the Anthropic Messages API (`POST /v1/messages`), using the `anthropic` Python package 2.12.0, effort medium, JSON schema output, and the server-side refusal fallback. `claude-haiku-5-5` is the configured alternative.
  - The team report's system prompt is [`app/report/system_prompt.md`](app/report/system_prompt.md) (version `report-v2`). The one-pager's is [`app/report/onepager_prompt.md`](app/report/onepager_prompt.md) (version `onepager-v1`).
  - The user message is the word "Facts:" followed by the facts object as JSON. The prompt says to use only those numbers, add no outside knowledge, call out small samples, and never describe drive direction or named set plays.
  - A team report costs about 3.3 cents and takes about 10 seconds (about 9,000 input and 1,450 output tokens).
  - The number check fired 0 times in 20 real reports. It is a safety net, not proof: about two in three made-up whole numbers would still pass, because most whole numbers from 0 to 99 appear somewhere in the facts.
- **Our own models, not LLMs:** the matchup model, ratings, badges, on/off and the game preview are written in Python and validated with dated results on the How it works page.

## What did you learn by building the project?

Ruben: rewrite in your own words. Reminders from `docs/NOTES.md`:

- Check the data before trusting it: most files came back empty until the arrow package was installed, and guessed column names broke a pull.
- The latest injury row is not always the right answer.
- Last season's data can leak into this season's numbers unless every query filters by season.
- How MongoDB unique indexes, partial indexes, upserts and caches keyed by data date work in practice.
- A fair test for a "streaky shooter" needs a stricter threshold when you test hundreds of players.
- Validating a model on unseen games shows problems that reading the code does not (the matchup position bias).
- An AI writer needs guardrails you can measure: a facts object, a number check, and knowing what the check misses.
- Leakage is easy to introduce in a game preview; a test that changes later games is the way to prove it is gone.

## What were the main technical challenges, and how did you solve them?

Ruben: rewrite in your own words. Reminders from `docs/NOTES.md`:

- The NBA stats site would not answer from campus Wi-Fi, so the data plan moved to hoopR's pre-pulled files, pulled on the laptop and shipped as seed data.
- The NBA play-by-play does not name who made a steal, so steals come from ESPN, matched to NBA players by name.
- The matchup model made every guard look like a better defender than every center; measuring each defender against his own position fixed it.
- Keeping saved reports stable while the data changes daily (a snapshot of the matchups at save time).
- One refresh at a time across two web workers, and a refresh that hung when the laptop slept.
- Free throws and substitutions are listed differently by season in the play-by-play, so on/off credits free throws to the players on the floor at the foul.
- Counted possessions run a little under the NBA's pace, and box-score team stats miss team turnovers and team rebounds.
- Building the game preview without leakage, and tag rules that at first tagged almost everything.

## Known limits

- No user accounts: saved lineups and reports are shared by everyone using one copy of the app.
- Some data exists only on the live NBA site (shots by dribbles and defender distance, defended FG%, passes between teammates, dunk score, clutch stats, NBA Cup standings). The app works without it.
- Left and right on the shot chart are not confirmed, so the app does not show side of the floor.
- Public data has no drive direction and no named set plays; the app describes where shots were taken and how possessions end.
- Early in a season many numbers are small samples; the app tags them.
- Wingspan exists only for combine-measured players, and play-in games and the NBA Cup final have no box score in the files.
- The schedule does not flag neutral-site games, so the game preview gives home court to the listed home team.
- The data is a snapshot from the last pull; the top bar shows the latest game and the pull time.

Every method, formula and validation result is explained on the app's **How it works** page: http://localhost:8000/how-it-works (source: [`app/templates/how_it_works.html`](app/templates/how_it_works.html)).
