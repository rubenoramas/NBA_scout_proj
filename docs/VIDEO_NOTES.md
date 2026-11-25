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

## Shots and player cards

What it does: the scouting page's Players tab lists the opponent's roster as a sortable table with position, minutes, points, rebounds, assists, shooting and an injury tag. Clicking a name, there or in any box score, opens the player card: headshot, height, weight, wingspan, his season line, his last five games with links to their box scores, and his shot profile. The shot profile is a half court drawn in the browser with every shot he took this season, filters for shot type and zone, a zone table comparing his FG% with the league in each zone, and his top three shot types at the rim, in the midrange and from three.

How it works, in plain words:
- A new R script, `pull_shots.R`, takes all 36,829 shots of this season one by one, and squeezes last season's 234,876 shots into per-player totals by zone and shot type.
- The shots file has no zones, so the script works them out from each shot's position: the restricted area is within 4 feet of the basket, the paint is the rest of the lane, a corner three is a three taken below the point where the line starts to curve, and so on. It checks itself every run: the distance it computes matches the distance written in the play description for every shot that has one.
- Makes are filled blue dots and misses are hollow gray rings, so the chart works without color.
- League averages per zone are computed from every shot in the database when the card loads, so they are always current.
- Wingspan comes from the NBA draft combine, back to 2000. Positions come from the NBA matchup files, with ESPN filling the gaps through a name-matching helper.
- The two biggest seed files are now gzip-compressed, which cut the seed folder from 13 MB to 5 MB.

Design decision worth mentioning: the app does not say which side of the floor a shot came from yet. The data does not say whether positive x means the shooter's left or right, and guessing wrong would flip every scouting note. A small script checks it against the live NBA site, which is blocked on campus, so sides stay hidden until it is run from home.

Questions:
- How does the app decide a shot's zone, and how do you know the rule is right?
- Why are makes and misses drawn as different shapes, not only different colors?
- What share of players have a wingspan, and why not all of them?
- Why is "which side of the floor" left out for now?

## Lineups, saved lineups and saved reports (CRUD and MongoDB)

What it does: the Lineups tab lets you pick exactly five players for each team, starting from each team's most common healthy starters. Every player's status comes from the official injury report and can be changed for this game. Every change recomputes the matchups right away, without a page reload, and the Matchups and Report tabs use the same lineups. You can save a lineup with a name, load it later, rename it and delete it. The Report tab saves a report with a title and your notes, and the "Saved reports" page lists them newest first, opens one, edits its title and notes, and deletes it.

How it works, in plain words:
- **REST create, read, update and delete.** Lineups and reports each have the same five endpoints: POST to create (answers 201), GET a list, GET one by id, PUT to update, DELETE to remove (answers 204). Bad input answers 400 with a plain message, and an unknown id answers 404. The code is in `app/routes/saved.py` and `app/services/saved.py`.
- **MongoDB persistence.** Lineups and reports live in two MongoDB collections, `lineups` and `reports`. `insert_one` creates a document, `find` and `find_one` read, `update_one` with `$set` changes only the fields sent, and `delete_one` removes one. The data is stored in the database's Docker volume, so it survives restarts, and the loader never touches these two collections when it reloads the NBA data.
- **Ids.** MongoDB gives every new document a unique ObjectId. The API sends it as 24 characters of text and turns it back into an ObjectId to look the document up.
- **Indexes.** Saved lineups are found by team, newest first, so `lineups` has an index on (team_id, updated_at). Reports are listed newest first, so `reports` has an index on created_at.
- **Status overrides.** Only Out keeps a player out of a lineup. Default lineups also skip Doubtful players, but you can still pick one by hand, and he gets a warning tag.

Design decision worth mentioning: a saved report keeps a snapshot of the matchups instead of recomputing them when opened. The data changes every day, so recomputing would quietly change a report you wrote last week, and your notes would no longer match the numbers beside them. The server reruns the model on the lineups when you save, so the snapshot always matches them, and after that only the title and notes can change. There are no user accounts, so everyone using a copy of the app shares its saved lineups and reports.

Questions:
- Which HTTP method creates a report, which reads one, which updates it, and which deletes it?
- How does MongoDB give each saved report its id?
- Why does a report store a snapshot instead of recomputing the matchups?
- What happens when you mark a player Out in the Lineups tab?

## The matchup model

What it does: the Matchups tab suggests which of our five should guard each of their five, sorted by their usage. Each row leads with how our defender changes the scorer's output against his norm, such as "holds him 3.4 below his norm" in green, then the expected points per 100 partial possessions, how much head-to-head history sits behind it, a one-line reason, and our top three options from the whole roster.

How it works, in plain words:
- Each scorer has a norm: what he scores against everyone, pulled toward the league average until he has enough possessions.
- Each defender has an effect: how many points he allows compared with what his opponents usually score, pulled toward zero until he has enough possessions.
- The pair's own history only nudges the estimate. Ten possessions of history count about a sixth.
- The app tries all 120 ways to match our five to their five and picks the one with the fewest expected points, weighting each scorer by his usage, so the best defender goes where it matters most. A guard is not put on a center, or the other way round, without real history between them.

Design decision worth mentioning: the model was tested honestly, and the test changed it. Trained on games before Nov 1 and tested on games after, it showed that the defender effect was partly measuring position: centers are matched to scorers near the rim, where scoring is easy, so every guard looked like a better defender (centers +5.3 per 100, guards -1.5). Now each defender is measured against the average defender at his own position, and those averages are close to zero. The same test also showed pair history was trusted too early, so it now takes 200 possessions, not 50, before a pair's own record counts half. The predictions line up with what happened a little better than knowing each scorer's norm (0.18 against 0.16), and the picks match the real top defender 36% of the time, below a same-position guess at 43%. The tab says plainly that the data is noisy.

Questions:
- What is a scorer's "norm", and why do the numbers lead with the effect against it?
- Why does the app weight each scorer by usage rate?
- How was the model tested, and what did the test show?
- Why is each defender compared with the average defender at his own position?

## Team pages

What it does: every team has a page at `/team/<abbreviation>`, such as `/team/BOS`. The band shows the record, seed, streak, last ten, home and road records. The Roster tab is the same sortable table as the scouting Players tab, with USG%, badges, injury tags and links to player cards. The Team stats tab shows offensive, defensive and net rating, pace and the four factors on both ends, each with its league rank. "My team" in the top bar goes to your own team's page, and every team chip in the app (schedule, box scores, scouting band, recent results, player cards) links to that team's page.

How it works, in plain words: the team stats come from the NBA's team stats files, pulled by the same R script as the standings. The API ranks each stat across the 30 teams, knowing which direction is better: a low defensive rating ranks 1st, a high one last, and pace ranks fastest first because neither is better. The roster table is one shared piece of code used by both the team page and the scouting page.

Design decision worth mentioning: rating tooltips now show a player's real rate with the adjusted one beside it, such as "13.0 per 36 (adjusted 10.9)". Players are ranked on the adjusted numbers so small samples cannot top the lists, but the card never hides what actually happened on the court.

Questions:
- Why does a low defensive rating rank 1st while a low offensive rating ranks last?
- Why does a rating tooltip show two numbers for some stats?

## Usage rate

What it does: usage rate (USG%) is the share of his team's plays a player uses while he is on the floor, counting shots, free throw trips and turnovers. It shows on the player card with his league rank and last season's value, as a sortable column on the Players tab (which now lists the main options first), and in a "Who runs the offense" panel on the scouting overview with each team's top three.

How it works, in plain words: the season value comes straight from the NBA's files. The box score already worked out the same idea for one game from the box score numbers. Summed over the season, the two agree almost exactly (correlation 0.999); the box score version runs about 0.7 points higher because it estimates who was on the floor from minutes.

Design decision worth mentioning: USG% is shown as a number with a rank, not a 0 to 99 rating, because a high usage is a role, not a skill. A bad shooter can have a high usage. It will matter in the matchup model: the defenders it assigns should matter most against the players who use the most plays.

Questions:
- What does a USG% of 35 mean?
- Why is USG% a stat with a rank instead of a 0 to 99 rating?

## Ratings and trait badges

What it does: every player with enough minutes gets twelve ratings from 0 to 99, such as Finishing, Three-point shooting and Interior defense, shown as bars on his card. Hovering or focusing a bar shows what feeds it and where he ranks on each part. Badges mark traits the ratings hide: Deep Range, Streaky Shooter, On-Ball Pest and Poster Maker (driving, running and cutting dunks only, so a big who catches lobs does not earn it). Each badge explains its rule and his numbers on hover, and the Players tab shows every player's badges.

How it works, in plain words:
- A rating is a percentile. Each attribute combines two to four stats (for example 3P% and threes per 36 minutes), each stat is ranked against every qualified player, and the weighted result is ranked again. 50 means typical, 99 means best in the league.
- This season is blended with last season: w = minutes this season / (minutes + 600). At 300 minutes this season counts a third, at 1,800 minutes three quarters. So early in the season, last season carries the rating, and it fades as games pile up. The blend happens first, and the shrinkage below runs once on the blended numbers.
- Shooting percentages are pulled toward the league average until the sample is large: (makes + 50 x league rate) / (attempts + 50). A player who is 4 of 5 does not top the list. Per-36 rates get the same treatment by minutes, (count + league rate per minute x 400) / (minutes + 400) x 36, so a player who blocked 3 shots in 40 minutes does not look like the league's best rim protector.
- Badges use both seasons' counts and need 500 minutes. On-Ball Pest uses steals from ESPN's play-by-play, because the NBA's play-by-play never says who made a steal, and only counts steals where the ball handler lost the ball.
- The ratings are computed in Python when the loader runs, and only when their data changed.

Design decision worth mentioning: Streaky Shooter has to pass a real statistical test. For each player, the app compares his make rate after a make with his make rate after a miss in the same game, with a one-sided z-test, and the result has to beat 0.05 divided by the 270 players tested. On Nov 18, nobody passed: the closest was Rudy Gobert at p = 0.001, against a threshold of 0.00019. That matches the research, which finds the hot hand small, and the comparison itself is slightly biased against finding streaks (Miller and Sanjurjo, 2018). The card still shows the test result, so "not streaky" is information too.

Questions:
- What does a rating of 50 mean, and how is it worked out?
- How does the blend decide how much last season counts?
- Why does nobody have the Streaky Shooter badge, and why is that the right answer?
- Why do steals come from ESPN instead of the NBA's own play-by-play?

## The AI scouting report

What it does: "Generate report" in the scouting band, or on the Report tab, asks Claude to write a pregame report in four sections: who the opponent is, three keys to the game, players to watch, and one note per matchup. It takes about 10 seconds and shows a loading state. Every section can be edited before saving, Regenerate writes a new draft, and the "Facts used" panel beside the text shows every number Claude was given. Saving stores the text with the model name, the prompt version and the facts.

How it works, in plain words:
- **Facts first.** `app/report/facts.py` gathers numbers the app already computed (records, streaks, last meeting, usage leaders, standouts, injuries with your overrides, the matchup assignment with each history size, and the key opposing players' ratings and badges) into one object. Every number is rounded once, there.
- **Then text.** `app/report/writer.py` sends the facts and the system prompt (`app/report/system_prompt.md`) to `claude-sonnet-5-5`. The prompt says to use only the facts, add no outside knowledge, call out small samples, and never describe drive direction or set plays. The reply must match a JSON schema with the four sections, so it can be read reliably.
- **Number check.** `app/report/check.py` finds every number in the text and looks for it in the facts. Dates and seasons from the facts, small counts from 1 to 5, and "per 100" are allowed. Anything else is flagged in gold on the page.
- **Errors in plain words.** No key, a rejected key, a rate limit, a timeout, a network problem, or a cut-off reply each give a clear message. Without a key the rest of the app still works.

Design decision worth mentioning: the model never sees raw data or the internet, only a facts object the app built, and the page shows that same object beside the text. That makes the AI a writer, not a source: any claim can be traced to a number on the page. The number check fired 0 times in 20 real reports, but it is a safety net, not proof. Most whole numbers from 0 to 99 appear somewhere in the facts, so a wrong rating could still pass, which is why the facts stay visible.

Questions:
- What exactly does Claude receive when you click Generate report?
- How does the app catch a number the AI made up, and what can that check miss?
- What happens if the API key is missing or the AI service is slow?
- Why does a saved report store the model name and prompt version?

## Refreshing from the app (optional refresher service)

What it does: the "Refresh data" button in the top bar updates the data without leaving the app. It shows each step ("Pulling games...", "Pulling shots...", "Pulling player stats...", "Reloading database..."), then updates the "Games through" line and shows a table of how many rows each collection gained. If a pull fails, it says which one and why. If the refresher is not running, the button is disabled and its tooltip says to run `docker compose --profile refresh up` or `./refresh.sh`.

How it works, in plain words:
- **An optional container for R.** The pulls are R scripts and the web container has no R, so a separate "refresher" service has R, hoopR, arrow, dplyr and jsonlite. It sits behind a Compose profile: plain `docker-compose up --build` skips it, and `docker compose --profile refresh up --build` adds it. It has no port on the host, so only the web app can talk to it over Docker's internal network.
- **Prebuilt packages.** The image is rocker/r2u, which installs R packages as ready-made binaries, so arrow is not compiled. hoopR comes from the SportsDataverse r-universe because r2u's copy is older, and the build fails with a clear message if hoopR is below 3.2.0 or arrow is missing.
- **Jobs in MongoDB.** POST /api/refresh creates a job document and asks the refresher to start. GET /api/refresh/<id> asks the refresher how far it got. When the pulls finish, the web app reloads MongoDB with the same loader used at startup and stores what changed. The page polls every 2 seconds with fetch.
- **One at a time.** A partial unique index lets only one job be marked active, so a second click gets "A refresh is already running" instead of a second set of pulls.

Design decision worth mentioning: R stays out of the main image and out of the default build. The grader's `docker-compose up --build` is exactly as fast as before, and the refresh feature is there for whoever wants it. Refreshed seed files are still committed only at milestones, never automatically.

Questions:
- Why does the refresher run in its own container, and why is it behind a profile?
- How does the app make sure only one refresh runs at a time, even with two web workers?
- What does the button show when the refresher is not running?

## The player one-pager

What it does: one printable page on an opposing player, written for the player on our team who will guard him. The top has his headshot, size, injury status and season line with USG% and its league rank. Below that: "How to guard him" in two or three sentences from Claude, the twelve ratings as bars with small-sample tags, his badges with their numbers, our best three defenders on him, his favorite shots at each level with a small shot chart, how his possessions end (play types with points per possession against the league), and which teammates assist him most. "Print one-pagers" on the scouting page prints one page for each of their five plus anyone with a USG% of 25 or higher.

How it works, in plain words:
- **Two new data files.** The pull script now saves every offensive play type per player (isolation, pick and roll, spot up and so on) and who assisted whom. The NBA play-by-play writes the passer inside the shot text, like "(Robinson 1 AST)", so the script reads that last name and matches it to the scorer's four teammates on the floor. 97.4% of named passers match exactly one teammate.
- **Reused parts.** The defenders come from the same matchup model as the Matchups tab, the ratings and badges from the player card, and the favorite shots from the same MongoDB query.
- **AI text with a cache.** The page sends Claude only the numbers printed on the page, through the same writer, honesty rules and number check as the team report. The answer is stored in MongoDB under four values: the player, our team, the data date and the prompt version. A unique index makes that four-part key a rule the database enforces. Opening the page again reads the stored text in about 10 ms and never calls the API. New data or a new prompt version writes fresh text.
- **Who can guard him.** Opened from the scouting page, the one-pager gets the statuses set in the lineup editor, so a player marked Out there is left out of the best three defenders, just like on the Matchups tab. Opened anywhere else, it uses the official injury report. A small tag on the panel says which one was used. Which of our players are Out is also part of the cache key, so the text never names a defender who is out.
- **Play types in words.** Each play type says "above league", "near league" or "below league" for his points per possession, with green and red meaning the same as on the player card. The words carry the meaning, so it reads the same in black and white.
- **Printing.** A print stylesheet swaps the dark colors for light paper and dark ink, hides the top bar and buttons, and shrinks the type so each player fits on one US letter page.

Design decision worth mentioning: the cache key includes the data date. The text can never describe yesterday's numbers next to today's, and a refresh makes the next page view write new text automatically, with no cache clearing step.

Questions:
- Why is the cache keyed by the data date and the prompt version, and not just by player?
- How does the app find who passed the ball when the play-by-play only gives a last name?
- What does the page show when there is no API key, and what if the text was already cached?
- If you mark our best defender Out in the lineup editor, what changes on the one-pager, and why does the text change too?

## Series history, schedule spots and where they give up shots

What it does:
- **Series history** on the scouting Overview lists every meeting this season and last, playoffs and play-in included, with the venue, result, score, a game type tag and a box score link where the data has one, plus a record for each season. "Who guarded whom" picks any meeting and shows, for each scorer on both teams, the defender who guarded him most and what that defender allowed. The Matchups tab adds the same fact from the last meeting beside the model's pick.
- **Schedule spots** tag both teams in the scouting band and on the schedule's upcoming games: days of rest, back-to-back, 3 games in 4 nights, 4 in 6, and "Road trip 2 of 5" or "Home stand 3 of 7".
- **Where they give up shots** shows a team's opponents' shots this season by zone, how often opponents shoot from each zone and how well, both against the league average, with a shot chart. It is on the team page's Team stats tab and, for the opponent, on the scouting Overview.

How it works, in plain words:
- **One small new file.** The per-game matchup file has one row for every defender who ever guarded a scorer in a game, about 310,000 rows for two seasons. The page only needs the top defender per scorer per game, so the R pull keeps just that row, with the scorer's totals beside it: 34,440 rows, 1.5 MB. It includes playoff, play-in and Cup final games, which the matchup model leaves out on purpose.
- **Spots come from the schedule.** For each team the app sorts its games by date and counts back: days since the last game, games in the last 4 and 6 nights, and how many games in a row are at home or on the road. No new data.
- **Defense shots reuse the shot table.** Every shot knows its game and the shooting team, so a team's opponents' shots are the shots in its games taken by the other team. The same MongoDB zone count used on player cards runs on that filter.

Design decision worth mentioning: schedule spots are facts, not predictions. The app says "Back-to-back" or "3 in 4 nights" and stops there, because the public research on rest effects is mixed and the data cannot show what rest does to one team on one night.

Questions:
- Why keep only each scorer's top defender per game instead of every matchup row?
- How does the app know which shots were taken against a team, when each shot only names the team that took it?
- What exactly does "3 in 4 nights" count, and why are the tags shown without any color for good or bad?

## On/off impact

What it does: for every player, how his team scores and allows per 100 possessions with him on the floor and with him off it, and the difference in net rating ("on-off net"), with the possessions behind each. This season and last season sit side by side. It shows as a sortable column in the roster table, a panel on the player card and one line on the one-pager, always with the note that on/off is noisy and depends on who a player shares the floor with.

How it works, in plain words:
- **Ten players on every play.** The NBA's play-by-play and its game lineups file line up row for row, so every play has the ten players on the floor, the running score and a possession number.
- **Points.** The score only appears when it changes, so the R pull carries it forward and gives each change to the ten players on the floor. Free throws go to the ten players on the floor at the foul, not when the shots are taken, because teams substitute between free throws.
- **Possessions are counted, not estimated.** The file numbers every possession, and an offensive rebound keeps the number, so a possession lasts until the ball changes hands. Each one is credited to the players on the floor when it ends.
- **Checks.** Summed points equal the final score in every regular-season game of both seasons (1,491 games). Counted possessions per 48 minutes correlate 0.998 with each team's pace in the team stats, and run about 0.9 lower, because the NBA's pace uses an estimate formula and counted possessions come in a little lower.
- **"Off" means games he played.** A long injury does not count as time off the floor.

Design decision worth mentioning: the free throw rule mattered more than expected. Last season's play-by-play lists most substitutions made during free throws before or between the shots, and this season's lists them after, so crediting free throws "when shot" treated the two seasons differently. Crediting them at the foul moved 11,412 of last season's 45,220 free throw points (394 of 9,852 this season) and makes the seasons comparable.

Questions:
- Why count possessions instead of using the usual estimate, and how did you check the count?
- Why are free throws credited to the players on the floor at the foul?
- Why does nearly every player this season carry a small-sample tag, and what does "off" include?

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
- Assist data names the passer by last name only, and without accents ("Jokic" for Jokić). Matching it to the four teammates on the floor, ignoring accents and allowing "Jal. Williams" style first initials, matched 97.4%.
- Making a fair test for streaky shooting: with 270 players tested, a normal 5% threshold would hand out about 13 badges by luck alone, so the threshold is split across all of them.

## Still to come

Sections for these get added as they are built: rotation scouting, and tests.
