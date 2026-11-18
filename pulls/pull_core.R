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
source("pulls/espn_match.R")

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
# gz = TRUE writes a gzip-compressed .jsonl.gz file, used for the two big
# files (game logs and shots) to keep the repo small.
write_jsonl <- function(df, name, gz = FALSE) {
  path <- file.path(seed_dir, paste0(name, if (gz) ".jsonl.gz" else ".jsonl"))
  con <- if (gz) gzfile(path, open = "w", encoding = "UTF-8") else file(path, open = "w", encoding = "UTF-8")
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
# Last season's game logs give box scores for last meetings from 2025-26.
last_logs_raw <- suppressMessages(load_nba_stats_player_game_logs(seasons = season_start - 1))
# Game lineups list the five players on the floor for every play. They are
# only used to find each game's starters, then thrown away.
lineups_raw      <- suppressMessages(load_nba_stats_game_lineups(seasons = season_start))
last_lineups_raw <- suppressMessages(load_nba_stats_game_lineups(seasons = season_start - 1))
injury_raw    <- suppressMessages(load_nba_stats_injury_report(seasons = season_start))
# Team ratings, pace and four factors for the team page.
team_adv_raw  <- suppressMessages(load_nba_stats_leaguedash(seasons = season_start, table = "team_stats_advanced"))
team_ff_raw   <- suppressMessages(load_nba_stats_leaguedash(seasons = season_start, table = "team_stats_fourfactors"))
# Season totals per player, for the season line on player cards.
base_raw      <- suppressMessages(load_nba_stats_leaguedash(seasons = season_start, table = "player_stats_base"))
# Positions: the per-game matchup files list a position (C, F or G) for
# many players. ESPN box scores fill the rest.
matchups_raw      <- suppressMessages(load_nba_stats_game_matchups(seasons = season_start))
last_matchups_raw <- suppressMessages(load_nba_stats_game_matchups(seasons = season_start - 1))
# ESPN functions take the END year of the season (2027 for 2026-27).
espn_box_raw  <- suppressMessages(load_nba_player_box(seasons = season_start + 1))
# Draft combine measurements, one file per draft class. Classes back to 2000
# cover nearly every current player who attended a combine.
combine_raw <- bind_rows(lapply(2000:(season_start - 1), function(cl) {
  tryCatch(suppressMessages(load_nba_stats_draft_combine_anthro(seasons = cl)), error = function(e) NULL)
}))

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
# One document per player per game, for this season and last season. The id
# joins game and player, such as "0022600002_1628369", so the same line can
# never load twice. Box scores are built from these lines.
#
# Starters: the lineup file lists the ten players on the floor for every
# play. The first play of the first period shows who started. For each game
# we keep that one row, then turn its ten id columns into a long list of
# (game, player) pairs with tidyr-free base R.
find_starters <- function(lineups) {
  first_play <- lineups %>%
    filter(period == 1) %>%
    group_by(game_id) %>%
    slice_min(action_number, n = 1, with_ties = FALSE) %>%
    ungroup()
  id_columns <- c(paste0("home_player_", 1:5), paste0("away_player_", 1:5))
  # For each of the ten columns, take (game_id, that column) and stack them.
  pairs <- lapply(id_columns, function(col) {
    data.frame(game_id = first_play$game_id, player_id = as.integer(first_play[[col]]))
  })
  starters <- distinct(bind_rows(pairs))
  starters$starter <- TRUE
  starters
}

tidy_logs <- function(raw, lineups, label) {
  raw %>%
    filter(!grepl("pre", season_type, ignore.case = TRUE)) %>%
    transmute(
      `_id` = paste(game_id, player_id, sep = "_"),
      game_id,
      season = label,
      game_date = substr(as.character(game_date), 1, 10),
      player_id = as.integer(player_id),
      player_name,
      team_id = as.integer(team_id),
      team_abbr = team_abbreviation,
      # The matchup reads "BOS vs. ORL" at home and "BOS @ ORL" on the road.
      home = grepl(" vs. ", matchup, fixed = TRUE),
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
    left_join(find_starters(lineups), by = c("game_id", "player_id")) %>%
    # Games with no lineup data get NA for every player; mark those NA
    # instead of FALSE so the app knows it cannot tell.
    group_by(game_id) %>%
    mutate(starter = if (any(!is.na(starter))) !is.na(starter) else NA) %>%
    ungroup()
}

this_logs <- tidy_logs(logs_raw, lineups_raw, season_label)
last_logs <- tidy_logs(last_logs_raw, last_lineups_raw, last_season_label)
game_logs <- bind_rows(last_logs, this_logs) %>%
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
players <- bind_rows(players_with_stats, injured_without_stats)

# Season line: totals from player_stats_base. Per-game numbers are worked
# out in the app (totals divided by games).
season_line <- base_raw %>%
  transmute(
    player_id = as.integer(player_id),
    gp = as.integer(gp), min_total = min,
    pts_total = pts, reb_total = reb, ast_total = ast, stl_total = stl, blk_total = blk, tov_total = tov,
    oreb_total = oreb, dreb_total = dreb, pf_total = pf,
    fgm_total = fgm, fga_total = fga, fg3m_total = fg3_m, fg3a_total = fg3_a,
    ftm_total = ftm, fta_total = fta, plus_minus_total = plus_minus
  )

# Position, step 1: the most common position in the matchup files.
most_common <- function(x) names(sort(table(x), decreasing = TRUE))[1]
matchup_position <- bind_rows(
  matchups_raw %>% select(player_id = off_person_id, position = off_position),
  last_matchups_raw %>% select(player_id = off_person_id, position = off_position)
) %>%
  filter(!is.na(position), position != "") %>%
  group_by(player_id = as.integer(player_id)) %>%
  summarise(position = most_common(position), .groups = "drop")

# Position, step 2: ESPN box scores for players the matchup files miss.
espn_positions <- espn_box_raw %>%
  filter(!is.na(athlete_position_abbreviation), athlete_position_abbreviation != "") %>%
  group_by(espn_name = athlete_display_name, espn_team = team_abbreviation) %>%
  summarise(position = most_common(athlete_position_abbreviation), .groups = "drop")
espn_matched <- match_espn_players(espn_positions,
                                   players %>% select(player_id, player_name, team_abbr),
                                   label = "ESPN box score players")
espn_position <- espn_matched %>%
  filter(!is.na(nba_player_id)) %>%
  distinct(player_id = as.integer(nba_player_id), .keep_all = TRUE) %>%
  select(player_id, espn_position = position)

# Wingspan: the most recent combine measurement for each player, in inches.
wingspans <- combine_raw %>%
  filter(!is.na(wingspan)) %>%
  group_by(player_id = as.integer(player_id)) %>%
  slice_max(as.integer(substr(as.character(season), 1, 4)), n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  transmute(player_id, wingspan_inches = round(as.numeric(wingspan), 2),
            standing_reach_inches = round(as.numeric(standing_reach), 2))

players <- players %>%
  left_join(season_line, by = "player_id") %>%
  left_join(matchup_position, by = "player_id") %>%
  left_join(espn_position, by = "player_id") %>%
  mutate(
    position_source = case_when(!is.na(position) ~ "matchups", !is.na(espn_position) ~ "espn", TRUE ~ NA_character_),
    position = coalesce(position, espn_position)
  ) %>%
  select(-espn_position) %>%
  left_join(wingspans, by = "player_id") %>%
  arrange(team_id, player_name)

# Team stats: one document per team. All rates are fractions (0.527 = 52.7%).
team_stats <- team_adv_raw %>%
  transmute(team_id = as.integer(team_id), gp = as.integer(gp), w = as.integer(w), l = as.integer(l),
            off_rating, def_rating, net_rating, pace) %>%
  left_join(team_ff_raw %>% transmute(team_id = as.integer(team_id), efg_pct, fta_rate, tov_pct = tm_tov_pct,
                                      oreb_pct, opp_efg_pct, opp_fta_rate, opp_tov_pct, opp_oreb_pct),
            by = "team_id") %>%
  mutate(`_id` = team_id, season = season_label) %>%
  relocate(`_id`)

# 9. Write ------------------------------------------------------------------
write_jsonl(teams, "teams")
write_jsonl(players, "players")
write_jsonl(standings, "standings")
write_jsonl(schedule, "schedule")
write_jsonl(game_logs, "game_logs", gz = TRUE)
write_jsonl(injuries, "injuries")
write_jsonl(team_stats, "team_stats")

# The meta file is a single document, so it is plain JSON and not JSON Lines.
# "Data as of" is the date of the latest game in the game logs, which is the
# honest answer to "how fresh are these numbers".
meta <- list(
  `_id` = "seed",
  season = season_label,
  last_season = last_season_label,
  data_as_of = max(this_logs$game_date),
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
cat("Game log lines this season / last: ", nrow(this_logs), "/", nrow(last_logs), "\n")
starters_per_game <- game_logs %>% group_by(season, game_id) %>% summarise(n = sum(starter %in% TRUE), .groups = "drop")
cat("Games with 10 starters marked:     ", sum(starters_per_game$n == 10), "of", nrow(starters_per_game), "\n")
print(as.data.frame(count(starters_per_game, season, starters = n)), row.names = FALSE)
cat("Games through:                    ", meta$data_as_of, "\n")
cat("Players with a position:           ", sum(!is.na(players$position)), "of", nrow(players),
    sprintf("(%d from matchups, %d from ESPN)\n", sum(players$position_source %in% "matchups"), sum(players$position_source %in% "espn")))
cat("Players with a wingspan:           ", sum(!is.na(players$wingspan_inches)), "of", nrow(players),
    sprintf("(%.0f%%; %d of %d players with stats)\n", 100 * mean(!is.na(players$wingspan_inches)),
            sum(!is.na(players$wingspan_inches) & players$has_stats), sum(players$has_stats)))

files <- list.files(seed_dir, full.names = TRUE)
total_mb <- sum(file.size(files)) / 1024^2
cat(sprintf("Total size of %s: %.2f MB\n", seed_dir, total_mb))
