#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Opponent Scout: core seed pull
#
# What this does
#   Downloads the core tables for the current season from hoopR's pre-pulled
#   NBA stats files, trims them to the fields the app needs, and writes one
#   seed file per MongoDB collection into data/seed/:
#     teams.jsonl, players.jsonl, standings.jsonl, schedule.jsonl,
#     game_logs.jsonl, injuries.jsonl, meta.json
#
# How to run (from the repo root)
#   Rscript pulls/pull_core.R
#
# Format
#   .jsonl is JSON Lines: one JSON object per line. Each line becomes one
#   MongoDB document. The "_id" field is the document's unique id.
#
# Needs the hoopR, arrow, dplyr and jsonlite packages. Works on any network,
# because it only reads hoopR's pre-pulled files.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(hoopR)
  library(dplyr)
  library(jsonlite)
})

if (!requireNamespace("arrow", quietly = TRUE)) {
  stop("The arrow package is missing, so the files would load empty. In R, run: install.packages(\"arrow\")",
       call. = FALSE)
}

# 1. Setup ------------------------------------------------------------------
# load_nba_stats_* functions take the START year of a season, so in
# November 2026 this is 2026, which means the 2026-27 season.
season_start <- most_recent_nba_stats_season()
# Turns a start year into a label, such as 2026 -> "2026-27".
make_label <- function(start) sprintf("%d-%02d", start, (start + 1) %% 100)
season_label <- make_label(season_start)
last_season_label <- make_label(season_start - 1)

seed_dir <- "data/seed"
dir.create(seed_dir, recursive = TRUE, showWarnings = FALSE)

cat("Opponent Scout core pull, season", season_label, "\n\n")

# Writes a data frame as JSON Lines and prints how many rows it wrote.
#   na = "null" writes missing values as null, so every document has the
#   same fields. digits = NA keeps full precision on numbers.
write_jsonl <- function(df, name) {
  path <- file.path(seed_dir, paste0(name, ".jsonl"))
  con <- file(path, open = "w", encoding = "UTF-8")
  stream_out(df, con, na = "null", digits = NA, verbose = FALSE)
  close(con)
  cat(sprintf("  %-16s %6d rows\n", basename(path), nrow(df)))
  invisible(df)
}

# Turns a date-time into a plain UTC text stamp, such as
# "2026-11-16T23:00:00Z", so it means the same thing on every computer.
as_utc_text <- function(x) format(x, "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")

# 2. Download ---------------------------------------------------------------
# Each call loads one season-long file. suppressMessages hides hoopR's
# banner lines.
cat("Downloading...\n")
standings_raw <- suppressMessages(load_nba_stats_leaguedash(seasons = season_start, table = "standings"))
bio_raw       <- suppressMessages(load_nba_stats_leaguedash(seasons = season_start, table = "player_bio"))
schedule_raw  <- suppressMessages(load_nba_stats_schedule(seasons = season_start))
# Last season's schedule is only used to find the last meeting between two
# teams that have not played each other yet this season.
last_schedule_raw <- suppressMessages(load_nba_stats_schedule(seasons = season_start - 1))
logs_raw      <- suppressMessages(load_nba_stats_player_game_logs(seasons = season_start))
injury_raw    <- suppressMessages(load_nba_stats_injury_report(seasons = season_start))

if (nrow(standings_raw) == 0 || nrow(bio_raw) == 0 || nrow(schedule_raw) == 0) {
  stop("A core file came back empty. Nothing was written. Rerun pulls/test_pulls.R to see which.",
       call. = FALSE)
}

cat("\nWriting seed files to", seed_dir, "\n")

# 3. Schedule ---------------------------------------------------------------
# One document per game, for this season and last season. Only real team
# games are kept: preseason and All-Star games are dropped. Games not played
# yet have null scores. filter() keeps the rows where the condition is TRUE,
# and %in% asks "is this value one of these?". The season column tells the
# two seasons apart.
kept_game_types <- c("regular-season", "nba-cup", "play-in", "playoffs")
tidy_schedule <- function(raw, label) {
  raw %>%
  filter(season_type %in% kept_game_types) %>%
  transmute(
    `_id` = game_id,
    game_id,
    season = label,
    game_date = as.character(game_date),
    season_type,
    home_team_id = as.integer(home_team_id),
    home_abbr = home_team_abbreviation,
    away_team_id = as.integer(away_team_id),
    away_abbr = away_team_abbreviation,
    home_pts = as.integer(home_pts),
    away_pts = as.integer(away_pts),
    home_wl, away_wl,
    played = !is.na(home_pts)
  )
}

# bind_rows() stacks the two seasons into one table.
schedule <- bind_rows(
  tidy_schedule(last_schedule_raw, last_season_label),
  tidy_schedule(schedule_raw, season_label)
) %>%
  arrange(game_date, game_id)
this_season_games <- schedule %>% filter(season == season_label)

# 4. Teams ------------------------------------------------------------------
# The standings file has city, name, conference and division, but no
# abbreviation. The schedule has the abbreviation, so we look it up there.
# distinct() keeps one row per team id.
abbreviations <- schedule_raw %>%
  distinct(team_id = as.integer(home_team_id), abbreviation = home_team_abbreviation)

teams <- standings_raw %>%
  transmute(
    `_id` = as.integer(team_id),
    team_id = as.integer(team_id),
    city = team_city,
    name = team_name,
    full_name = paste(team_city, team_name),
    slug = team_slug,
    conference,
    division
  ) %>%
  left_join(abbreviations, by = "team_id") %>%
  arrange(full_name)

if (any(is.na(teams$abbreviation))) {
  warning("Some teams have no abbreviation: ", paste(teams$full_name[is.na(teams$abbreviation)], collapse = ", "))
}

# 5. Standings --------------------------------------------------------------
# playoff_rank is the conference seed. str_current_streak reads like "W 3".
standings <- standings_raw %>%
  transmute(
    `_id` = as.integer(team_id),
    team_id = as.integer(team_id),
    conference,
    seed = as.integer(playoff_rank),
    wins = as.integer(wins),
    losses = as.integer(losses),
    win_pct,
    record,
    home_record = home,
    road_record = road,
    last_ten = l10,
    streak = str_current_streak,
    streak_games = as.integer(current_streak),
    conference_games_back
  ) %>%
  arrange(conference, seed)

# 6. Game logs --------------------------------------------------------------
# One document per player per game. The id joins game and player, such as
# "0022600002_1628369", so the same line can never load twice.
game_logs <- logs_raw %>%
  filter(season_type != "preseason", !grepl("pre", season_type, ignore.case = TRUE)) %>%
  transmute(
    `_id` = paste(game_id, player_id, sep = "_"),
    game_id,
    game_date = substr(as.character(game_date), 1, 10),
    player_id = as.integer(player_id),
    player_name,
    team_id = as.integer(team_id),
    team_abbr = team_abbreviation,
    matchup, wl, min,
    pts = as.integer(pts), reb = as.integer(reb), ast = as.integer(ast),
    stl = as.integer(stl), blk = as.integer(blk), tov = as.integer(tov),
    pf = as.integer(pf),
    fgm = as.integer(fgm), fga = as.integer(fga),
    fg3m = as.integer(fg3m), fg3a = as.integer(fg3a),
    ftm = as.integer(ftm), fta = as.integer(fta),
    oreb = as.integer(oreb), dreb = as.integer(dreb),
    plus_minus = as.integer(plus_minus)
  ) %>%
  arrange(game_date, game_id, team_id, player_id)

# 7. Injuries ---------------------------------------------------------------
# The official report is issued many times a day. Rows with reason
# "NOT YET SUBMITTED" have no player and are skipped.
#
# Taking each player's latest row would be wrong: a player listed Out weeks
# ago who has since returned simply drops off later reports, so his latest
# row would still say Out. Instead, for each team we find its most recent
# report, and only the players on that report get a status. Everyone else
# counts as available.
reports <- injury_raw %>%
  filter(is.na(reason) | reason != "NOT YET SUBMITTED", !is.na(team_id))

# group_by() splits rows by team. summarise() then makes one row per team,
# here the time of that team's latest report.
latest_report <- reports %>%
  group_by(team_id) %>%
  summarise(latest = max(report_datetime), .groups = "drop")

on_latest <- reports %>%
  inner_join(latest_report, by = "team_id") %>%
  filter(report_datetime == latest)

unmatched_injuries <- on_latest %>% filter(is.na(person_id))
if (nrow(unmatched_injuries) > 0) {
  cat("  Note: injury rows with no NBA id (skipped):",
      paste(unique(unmatched_injuries$report_player_name), collapse = "; "), "\n")
}

# Report names read "Last, First". This flips them to "First Last".
flip_name <- function(x) ifelse(grepl(",", x), sub("^(.*?),\\s*(.*)$", "\\2 \\1", x), x)

injuries <- on_latest %>%
  filter(!is.na(person_id)) %>%
  distinct(person_id, .keep_all = TRUE) %>%
  transmute(
    `_id` = as.integer(person_id),
    player_id = as.integer(person_id),
    player_name = flip_name(report_player_name),
    team_id = as.integer(team_id),
    status = current_status,
    reason,
    previous_status,
    game_date = as.character(game_date),
    report_time = as_utc_text(report_datetime)
  ) %>%
  arrange(team_id, player_name)

# 8. Players ----------------------------------------------------------------
# player_bio lists only players who have played this season. Players on an
# injury report who have not played yet get a basic document, marked
# has_stats = FALSE, so they still show on the roster with their injury tag.
headshot_url <- function(id) sprintf("https://cdn.nba.com/headshots/nba/latest/260x190/%d.png", id)

players_with_stats <- bio_raw %>%
  transmute(
    `_id` = as.integer(player_id),
    player_id = as.integer(player_id),
    player_name,
    team_id = as.integer(team_id),
    team_abbr = team_abbreviation,
    age,
    height = player_height,
    height_inches = as.integer(player_height_inches),
    weight_lbs = as.integer(player_weight),
    college, country,
    draft_year, draft_round, draft_number,
    games_played = as.integer(gp),
    has_stats = TRUE,
    headshot_url = headshot_url(as.integer(player_id))
  )

injured_without_stats <- injuries %>%
  filter(!player_id %in% players_with_stats$player_id) %>%
  left_join(teams %>% select(team_id, team_abbr = abbreviation), by = "team_id") %>%
  transmute(
    `_id` = player_id,
    player_id,
    player_name,
    team_id,
    team_abbr,
    has_stats = FALSE,
    headshot_url = headshot_url(player_id)
  )

# bind_rows() stacks the two tables. Columns that only one table has are
# filled with missing values for the other.
players <- bind_rows(players_with_stats, injured_without_stats) %>%
  arrange(team_id, player_name)

# 9. Write ------------------------------------------------------------------
write_jsonl(teams, "teams")
write_jsonl(players, "players")
write_jsonl(standings, "standings")
write_jsonl(schedule, "schedule")
write_jsonl(game_logs, "game_logs")
write_jsonl(injuries, "injuries")

# The meta file is a single document, so it is plain JSON and not JSON Lines.
# "Data as of" is the date of the latest game in the game logs, which is the
# honest answer to "how fresh are these numbers".
meta <- list(
  `_id` = "seed",
  season = season_label,
  last_season = last_season_label,
  data_as_of = max(game_logs$game_date),
  pulled_at = as_utc_text(Sys.time()),
  latest_injury_report = as_utc_text(max(reports$report_datetime)),
  counts = list(
    teams = nrow(teams), players = nrow(players), standings = nrow(standings),
    schedule = nrow(schedule), game_logs = nrow(game_logs), injuries = nrow(injuries)
  )
)
write_json(meta, file.path(seed_dir, "meta.json"), auto_unbox = TRUE, pretty = TRUE)
cat(sprintf("  %-16s %6d document\n", "meta.json", 1L))

# 10. Summary ---------------------------------------------------------------
cat("\nPlayers with stats:              ", nrow(players_with_stats), "\n")
cat("Injured players with no stats yet:", nrow(injured_without_stats), "\n")
if (nrow(injured_without_stats) > 0) {
  cat("  ", paste(injured_without_stats$player_name, collapse = ", "), "\n")
}
cat("Schedule rows by season and type:\n")
print(as.data.frame(count(schedule, season, season_type)), row.names = FALSE)
cat("This season played / still to play:", sum(this_season_games$played), "/", sum(!this_season_games$played), "\n")
cat("Data as of:                       ", meta$data_as_of, "\n")

files <- list.files(seed_dir, full.names = TRUE)
total_mb <- sum(file.size(files)) / 1024^2
cat(sprintf("Total size of %s: %.2f MB\n", seed_dir, total_mb))
