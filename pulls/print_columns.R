#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Opponent Scout: print column names
#
# What this does
#   Loads every table that docs/DATA_SOURCES.md marks "not printed yet" and
#   prints its column names. It also answers three open questions:
#     1. Which season_type and per_mode values do the play type and hustle
#        files hold? (Each player has one row per combination, so the pull
#        scripts must pick one.)
#     2. Does the play type file have team rows, or only player rows?
#     3. Which season_type_id values does last season's per-game matchup
#        file hold?
#
# How to run (from the repo root)
#   Rscript pulls/print_columns.R
#
# It only reads hoopR's pre-pulled files, so it works on any network and
# writes nothing to disk.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages(library(hoopR))
options(width = 200)

# load_nba_stats_* functions take the START year of a season.
# In November 2026 this is 2026, which means the 2026-27 season.
stats_season <- most_recent_nba_stats_season()
cat("Season start year:", stats_season, "\n")

# Prints a table's size and all of its column names.
print_columns <- function(label, tbl) {
  cat("\n==", label, "==\n")
  cat("rows:", nrow(tbl), " columns:", ncol(tbl), "\n")
  cat(paste(names(tbl), collapse = ", "), "\n")
}

# Prints each distinct value in one column with how many rows have it.
# useNA = "ifany" also counts rows where the value is missing.
print_values <- function(label, tbl, col) {
  cat("\n--", label, ":", col, "--\n")
  if (!col %in% names(tbl)) {
    cat("(no column called", col, ")\n")
    return(invisible(NULL))
  }
  print(table(tbl[[col]], useNA = "ifany"))
}

# 1. Tables from the league dashboard file ----------------------------------
# One call per table name. The loop runs the same two lines for each name.
tables <- c(
  "player_stats_base", "player_stats_advanced", "team_stats_fourfactors",
  "player_tracking_drives", "player_tracking_passing",
  "player_tracking_rebounding", "player_tracking_catchshoot",
  "player_tracking_pullupshot", "player_tracking_posttouch",
  "player_tracking_speeddistance"
)
for (table_name in tables) {
  tbl <- load_nba_stats_leaguedash(seasons = stats_season, table = table_name)
  print_columns(table_name, tbl)
}

# 2. Play types -------------------------------------------------------------
synergy <- load_nba_stats_synergy(seasons = stats_season)
print_columns("play types (synergy)", synergy)
print_values("play types", synergy, "season_type")
print_values("play types", synergy, "per_mode")
print_values("play types", synergy, "type_grouping")
print_values("play types", synergy, "play_type")
print_values("play types", synergy, "player_or_team")

# A team row is a row with a team id but no player id.
# is.na() is TRUE where a value is missing.
if ("player_id" %in% names(synergy)) {
  team_rows <- sum(is.na(synergy$player_id))
  cat("\nPlay type rows with no player_id (team rows):", team_rows, "\n")
  cat("Play type rows with a player_id:", sum(!is.na(synergy$player_id)), "\n")
}

# 3. Hustle -----------------------------------------------------------------
hustle <- load_nba_stats_hustle_player(seasons = stats_season)
print_columns("hustle", hustle)
print_values("hustle", hustle, "season_type")
print_values("hustle", hustle, "per_mode")

# 4. Matchups ---------------------------------------------------------------
# Last season's per-game file covers more games than a regular season, so
# check which season types are inside before summing it.
game_matchups_last <- load_nba_stats_game_matchups(seasons = stats_season - 1)
print_values("per-game matchups, last season", game_matchups_last, "season_type_id")

# The season-totals file is only used as a cross-check on our own sums.
matchup_totals_last <- load_nba_stats_matchups(seasons = stats_season - 1)
print_columns("matchup season totals, last season", matchup_totals_last)
print_values("matchup season totals, last season", matchup_totals_last, "season_type")
print_values("matchup season totals, last season", matchup_totals_last, "per_mode")

cat("\nDone.\n")
