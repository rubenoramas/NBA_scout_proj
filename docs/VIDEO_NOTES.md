# Video and README study notes

Everything you need to explain Opponent Scout in the demo video and to write the four README answers. Each section ends with a few questions. If you can answer them out loud without looking, you know that part.

Claude Code adds a section here after each feature it builds (see CLAUDE.md).

## The 30-second version

Opponent Scout builds a pregame scouting report on an NBA opponent. You pick your team, click an upcoming game on its calendar, and get how the opponent plays, where each player scores from, ratings and trait badges for every player, and a suggested defensive matchup for each of their scorers. An AI writes a coach-style report from the numbers, and you can save, edit and delete reports and lineups.

Under the hood: R scripts pull NBA data onto my laptop and save it as seed files. When the app starts, a loader puts those files into MongoDB. A Flask API reads MongoDB, and a vanilla JavaScript page calls the API with fetch. Docker Compose runs it all with one command.

Questions:
- Who is the app for, and what decision does it help them make?
- Trace one click (choosing an opponent) from the browser to the database and back.

## Suggested video plan (2 to 3 minutes)

| Time | Show | Say |
| --- | --- | --- |
| 0:00 | The landing page | What the app is, in one sentence |
| 0:15 | Pick a team, click a game on the calendar | Any team against any team |
| 0:35 | Game context header, team profile | Records, streaks, how the opponent plays |
| 1:00 | A player one-pager: ratings, badges, shot chart | Ratings are league percentiles. Badges catch traits numbers hide |
| 1:30 | Matchups, then change a lineup | Matchups recompute without a page reload (AJAX). Lineups are saved in MongoDB |
| 2:00 | Generate the AI report, then edit and delete it | Loading state, CRUD, and the AI only uses our numbers |
| 2:30 | Terminal: `docker-compose up --build` | The stack: Docker, Flask, MongoDB, vanilla JS |
| 2:50 | Close | One thing that makes it different |

Before recording:
- Run `./refresh.sh` so the data is current, and check that the top bar shows a green dot and "Games through" last night's games.
- Put a real API key in `.env` so the AI report works.
- Pick a matchup that tells a good story (a star scorer, a badge that stands out).
- Zoom the browser so text is readable in the recording.

## Docker and Docker Compose

Docker packages each part of the app with everything it needs, so it runs the same on any computer. Docker Compose starts several containers together from one file, `docker-compose.yml`.

The app has three services:
- **web**: the Flask app, run by gunicorn. Built from our Dockerfile.
- **mongo**: the database, from the official MongoDB image at a pinned version (8.0.38).
- **loader**: starts, fills MongoDB from the seed files, and exits. `docker compose ps -a` shows it as "Exited (0)", which means it finished normally.

Key lines in `docker-compose.yml`:
- `ports: "8000:8000"` connects port 8000 on the laptop to port 8000 in the container. The app is at http://localhost:8000. Not 5000, because macOS uses 5000 for AirPlay.
- `env_file` with `required: false` loads the API key from `.env` if it exists. A fresh clone with no `.env` still starts.
- `MONGO_URI: mongodb://mongo:27017/opponent_scout` tells Flask where the database is. `mongo` works as a hostname because Compose puts the services on a private network where each service name is an address.
- `depends_on` with `condition: service_healthy` makes web wait until MongoDB actually answers, not just until its container starts.
- The **healthcheck** pings MongoDB every 5 seconds. That ping is what "healthy" means.
- `mongo-data:/data/db` keeps the database files in a **named volume**. Containers are meant to be thrown away and rebuilt, so the data lives outside them and survives `docker-compose down`. Only `docker-compose down -v` deletes it.
- `./app:/code/app` is a **bind mount** for development. With gunicorn's `--reload`, saving a Python file restarts the app in a few seconds.
- MongoDB has no `ports` entry, so it is not reachable from the laptop, only from inside the Docker network. To look inside: `docker compose exec mongo mongosh`.

Why gunicorn: Flask's built-in server is meant for development only. Gunicorn is a real web server.

Versions: Python 3.13.18, Flask 3.1.3, pymongo 4.20.0, gunicorn 27.0.1, MongoDB 8.0.38.

Useful commands:
- `docker-compose up --build`: build and start everything
- `docker compose ps`: check what is running
- `docker-compose down`: stop everything (data kept)

Questions:
- Why does web wait for mongo, and what would go wrong without it?
- Why does the database live in a volume and not inside the container?
- What is the difference between a named volume and a bind mount?
- Why can the app find the database at the hostname `mongo`?

## Flask and the health check

Flask is the backend: it receives HTTP requests and returns JSON. The first endpoint, `GET /api/health`, reports whether the API is up, whether MongoDB answered, and whether an AI key is set. It returns HTTP 200 when everything works and 503 when the database cannot be reached. The page shows a loading state, then green or red, with a "Try again" button on failure.

Questions:
- What does HTTP 503 mean, and why is it the right code when the database is down?
- What are the three states the health page can show?

## MongoDB

- A **database** (ours is `opponent_scout`) holds **collections**.
- A **collection** is a group of similar records, like `players` or `schedule`. It is roughly a table, but documents in it do not all need the same fields.
- A **document** is one record, stored like a JSON object. One player is one document.
- Every document has an **`_id`** that must be unique. We use the NBA's own ids (player id, team id, game id), so loading the same data twice can never create duplicates.
- An **index** lets MongoDB find documents without scanning the whole collection. We index the fields the app searches by, such as players by team and games by date. `_id` is indexed automatically.
- The database does not need to be created ahead of time. MongoDB creates it the first time something is written.

How the loader works:
- Each collection loads into a temporary collection, which is then renamed over the old one in one step. Rows that disappeared from the data, such as a cleared injury, are removed.
- It computes a fingerprint (a SHA-256 hash) of each seed file and stores it. If a file has not changed, it skips that file, so restarts stay fast.
- A bad or missing file is reported in plain words and skipped. The rest still loads.

Collections: teams, players, standings, schedule, game_logs, injuries, meta, plus shots, matchups, attributes, opponent_lineups, and the two the user edits, lineups and reports.

Questions:
- Why does using the NBA's ids as `_id` prevent duplicates?
- What does an index speed up, and what does it cost?
- How does the loader avoid reloading data that has not changed?

## Where the data comes from

The running app never calls an outside data source. It reads only MongoDB, which is filled from seed files committed to the repo. That way grading never depends on a website being up.

R scripts in `pulls/` use the hoopR package, part of the SportsDataverse project. There are three routes:

1. **Pre-pulled NBA stats files** (the main route). hoopR publishes copies of NBA stats tables as files, one per season, updated daily. Each loads in about a second.
2. **ESPN play-by-play**, used for one thing: who made each steal.
3. **The live NBA stats site**, optional. It gave no answer from campus Wi-Fi, so the app does not depend on it.

Other decisions:
- NBA ids everywhere. Headshots come from the NBA's image site by player id.
- Injuries come from the NBA's official injury report. A player who dropped off his team's latest report counts as available, because taking each player's latest row would leave long-recovered players marked Out.
- The top bar shows two facts: the latest game in the data and when it was pulled, such as "Games through Tue, Nov 17 · pulled Nov 18, 9:02 AM".
- Seed files are JSON Lines: one JSON document per line. Each line is already a MongoDB document, types are kept, and git diffs stay readable.
- This season is blended with last season, because a month into a season the samples are small.

Gotchas worth mentioning:
- Season numbers differ by function: the NBA stats files use the start year (2026 for 2026-27), ESPN uses the end year (2027), and the live functions default to last season.
- Most files are Parquet and need R's arrow package. Without it they load as empty tables.

What public data cannot tell us:
- Which way a player drives or dribbles. The app shows where shots come from, not which way he was moving.
- Named set plays. The app shows play types, such as isolation and pick and roll.

Questions:
- Why does the app read from MongoDB instead of calling the data sources directly?
- Why did the campus network push the project toward pre-pulled files?
- Why can't the app say "he likes to drive left"?

## The first data slice: pull_core.R and the loader

What it does: `pulls/pull_core.R` downloads this season's teams, players, standings, schedule, player game logs and injury report, and writes one seed file per collection into `data/seed/`. When the stack starts, the loader puts those files into MongoDB. On Nov 17 that was 30 teams, 522 players, 30 standings rows, 1,207 games, 4,618 game log lines and 154 injury entries, about 2 MB in all.

How it works, in plain words:
- The R script loads each season-long file with one hoopR call, keeps only the columns the app needs, renames them to plain names, and writes them as JSON Lines. It prints the row count of each file and the total size.
- Every row gets an `_id` from the NBA's own ids: team id, player id, game id, and game id plus player id for a game log line.
- The loader is a third container. It waits for MongoDB to be healthy, loads every seed file that changed, and exits. The web app waits for it to finish.
- To skip unchanged files, the loader stores a fingerprint (SHA-256 hash) of each file. Same fingerprint next time means nothing to do.
- Each changed collection loads into a temporary collection, gets its indexes, and is renamed over the old one in one step.

Design decision worth mentioning: injuries. The official report comes out many times a day, and a player who recovers just stops appearing on it. Taking each player's latest row would leave him marked Out forever. So the script finds each team's most recent report and uses only the players on it. A second decision: 51 injured players had not played yet, so they were missing from the player list. They get a basic player document marked "no stats yet", so they still show on the roster with their injury tag.

R ideas used: `filter()` keeps rows that match a condition, `transmute()` picks and renames columns, `group_by()` plus `summarise()` makes one row per group (the latest report per team), `left_join()` adds columns from another table by a shared key, and `bind_rows()` stacks two tables.

Look at the data yourself:
- `docker compose exec mongo mongosh opponent_scout` opens the MongoDB shell
- `show collections` lists the collections
- `db.players.countDocuments()` counts documents
- `db.teams.findOne({abbreviation: "BOS"})` shows one document
- `db.players.find({team_id: 1610612738}, {player_name: 1, height: 1})` lists one roster with two fields

Questions:
- Why does the injury rule look at each team's latest report instead of each player's latest row?
- What happens on the second `docker-compose up` if no seed file has changed, and how does the loader know?
- Why load into a temporary collection and rename it, instead of inserting into the real one?

## First screen: team picker, calendar and game context

What it does: the landing page lets you pick your team (remembered in the browser), shows its season as a month calendar with scores for played games, and turns every upcoming game into a "Scout" link. A search box scouts any other team. The scouting page, at an address like `/scout?us=BOS&them=NYK`, shows the game context header: both teams' records, seeds, streaks, last ten and last game, a last game standout for each side, the next meeting, and the last meeting.

How it works, in plain words:
- Three REST endpoints feed the pages: `GET /api/teams`, `GET /api/teams/<id>/schedule` and `GET /api/games/context?us=<id>&them=<id>`. They use NBA team ids and answer bad requests with 400 or 404 and a plain message.
- The JavaScript fetches JSON from those endpoints and builds the page. Every fetch shows a loading skeleton first, then the content, an empty message, or an error with a "Try again" button.
- The scouting page reads the two abbreviations from the address, looks up their ids, and asks for the context. That is why the link can be bookmarked or shared.
- The last meeting searches this season and last season, so it can say "2025-26 season, Playoffs" when the teams have not met yet this year.
- Your team is stored in the browser's localStorage, so the calendar opens straight away on the next visit.

Design decision worth mentioning: the last game standout rule. A player stands out when, in his team's last game, he beat his own average by at least 10 points, 6 rebounds or 5 assists, and by at least 1.5 times, with at least 5 earlier games behind the average. He also has to be a real rotation player: at least 15 minutes a game before, and at least 20 minutes in the last game. When several qualify, the biggest jump relative to the average wins. The card shows the numbers and the rule, so nobody has to trust it blindly, and it says "Small sample" when the average rests on fewer than 10 games. On Nov 17 it found a standout for 18 of 30 teams. A second decision: team abbreviations in styled badges instead of logos, because logos are trademarks and the repo is public.

Tests: `docker compose run --rm web pytest` runs 14 tests against a separate test database filled with three made-up teams, so the results never depend on the day's real data.

Questions:
- Why do the API endpoints take team ids, but the scouting page address uses abbreviations?
- What does the standout rule require, and why does it need at least 5 earlier games?
- Why do the tests use their own database and made-up teams instead of the real data?

## The front office console design

What it does: every screen now follows one design guide, `docs/DESIGN.md`, built from three mockups in `docs/design/`. The look is a dense analytics tool, like software a team's staff would use: a dark top bar on every page, tables instead of cards, small uppercase labels, numbers that line up, and one blue accent color. First visit shows a team selection screen grouped by conference and division, with a filter box. After that, the landing page is the season schedule as a table with the margin and running record of every game, beside a sidebar with the next game, a team snapshot and a mini month view. The scouting page has a matchup band with both teams and the game date, section tabs, and three panels: Head to head, Recent results and Last game standouts.

How it works, in plain words:
- All 21 colors live as variables at the top of `style.css`, so a color change is one edit and no screen can drift off the palette.
- The top bar is shared code (`topbar.js`): the team switcher, the main navigation, the team search (press `/` to jump to it) and the data freshness label.
- The running record is counted over the whole season in date order, so November starts from the record before Nov 1. LAC reads 1-5 after Nov 1 and 4-8 after Nov 15, which matches the official standings. The NBA Cup final is skipped because it does not count in the standings.
- Tabs and buttons for features that are not built yet are disabled and marked "Soon". Nothing on screen pretends to work.
- The Inter font is stored in the app itself, with its open font license, so the app looks the same with no internet.
- No API or test changed. Only the look and layout did.

Design decision worth mentioning: the divider between played and upcoming games says "Games through Mon, Nov 16" instead of "Today". The data is pulled the morning after games, so calling that line "today" would be wrong on most days.

Questions:
- Why keep every color in one set of variables instead of writing colors where they are used?
- How is the running record worked out, and why does it start from the first game of the season instead of the first game of the month?
- Why are unfinished features shown as disabled "Soon" items instead of placeholder panels?

## Box scores

What it does: every played game, this season and last, has a box score page at `/game/<game id>`. A band shows both teams, the final score, the date and the venue (with a Playoffs or Play-in tag when it applies). Each team gets a table sorted by points, with sortable columns, an S tag on starters and a team totals row. A Basic and Advanced switch changes the columns. Advanced adds TS%, eFG%, USG%, Game Score and assists per turnover, plus each team's four factors and a note that shows every formula. You reach it from the Box score links on the schedule, the mini calendar, a Last game tab on the schedule panel, and every row in Recent results on the scouting page.

How it works, in plain words:
- The box score is built from the player game log lines already in MongoDB. The pull now also brings in last season's lines, so a last meeting from 2025-26 has a box score too.
- Starters come from the game lineups file: whoever was on the floor for the first play of the game.
- All advanced stats are computed once, in Python, and sent with the box score. The tests check them against numbers worked out by hand.
- Checked by hand on UTA at LAC, Nov 17: both teams' player points add up to the final score (132 and 107), and Keyonte George's TS% (30 / (2 x (17 + 0.44 x 6)) = 76.4) and Game Score (29.0) match the page.

Design decision worth mentioning: the play-in games and the NBA Cup final are not in the NBA's game log file at all. Instead of hiding those games or showing empty tables, the page shows the final score and says plainly that player lines are not in the data. A second decision: adding last season's games meant the standout rule could quietly average in last season's games, so it now filters by season, with a test to prove it.

Questions:
- Where does the box score data come from, and how do you know the numbers are right?
- What is True Shooting percentage, and why is it a better measure than field goal percentage?
- Why did adding last season's game logs risk breaking the standout rule, and how was it fixed?

## Data freshness and refreshing the data

What it does: the top bar shows two facts about the data: the latest game it includes and when it was pulled, for example "Games through Tue, Nov 17 · pulled Nov 18, 9:02 AM". The dot beside it is green, or amber when the pull is more than 2 days old. One command, `./refresh.sh`, brings everything up to date.

How it works, in plain words:
- The R pull writes both facts into `meta.json`: the date of the latest game in the game logs, and the time of the pull. The API passes them to the page, which shows the pull time in the viewer's own time zone.
- `./refresh.sh` runs every R pull script in order. If one fails, it stops and says which one, so a half-finished pull is never loaded silently. Then it runs the loader to reload MongoDB and prints a table of row counts per seed file, before and after.
- The loader only reloads files that changed, so a refresh on a day with no games finishes fast.

Design decision worth mentioning: the old label said "Data as of Nov 17" and people read it as "today is Nov 17". Showing the last game date and the pull time separately removes the guess, and the amber dot warns when someone forgot to refresh before a demo.

Questions:
- What two facts does the top bar show about the data, and why both?
- What does `./refresh.sh` do, step by step, and what happens if one pull fails?

## AI in the project

AI shows up in three places:
- **Our own matchup model** picks which defender should guard which scorer.
- **The Claude API** writes the team report and the "how to guard him" lines. It receives only numbers the app computed and is told to use nothing else. The page shows the same numbers beside the text, so every claim can be checked.
- **Claude Code** wrote most of the code from my prompts, logged word for word in `docs/PROMPTS.md`. I used Claude chat for planning, data research and writing those prompts.

Questions:
- How do we stop the AI from inventing stats?
- What does the app do when no API key is set?

## Challenges so far (for the README)

Full notes are in `docs/NOTES.md`. Write the README answers in your own words.

- The NBA stats site would not answer from campus Wi-Fi, so the data plan switched to pre-pulled files.
- A timeout in the test script crashed it instead of failing cleanly. The fix was to put the timeout on the request itself.
- Most data files loaded empty until the arrow package was installed.
- The NBA play-by-play file does not record who made a steal, so steals come from ESPN, matched to NBA players by name.
- Taking each player's latest injury row would have marked recovered players as Out.
- 51 injured players had not played yet, so they were missing from the player bio file and from rosters.
- The first standout rule favored bench players: a small average makes any good night look huge. A minutes floor (15 a game before, 20 in the last game) fixed it, and the card shows the sample size and the rule so the reader can judge it.
- The play-in games are not in the NBA's game log file, so they have a score but no box score.

## Still to come

Sections for these get added as they are built: shot charts and zones, ratings, trait badges, the matchup model, the lineup editor, the player one-pager, rotation scouting, the AI report, and tests.
