#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Opponent Scout: data pull test
#
# What this does
#   Calls every data source the app depends on, once, and prints a table that
#   says which pulls work from this computer. Nothing else in the project
#   should be built until the required rows say PASS.
#
# How to run (from the repo root)
#   Rscript pulls/test_pulls.R
#
# First time only, inside R:
#   install.packages("hoopR")
#
# Notes
#   - Run this on a laptop or desktop. The NBA stats site blocks cloud servers.
#   - hoopR's NBA functions default to LAST season, so every call below passes
#     the season on purpose. Do the same in the real pull scripts.
#   - The script waits a couple of seconds between NBA calls to stay polite.
#     The whole run takes a few minutes.
#   - It starts with a network check. Some networks (cloud servers, and some
#     campus or office networks) get no answer from the NBA stats site. If the
#     check fails, switch to a phone hotspot or home internet and rerun.
#   - Press Control + C at any time to stop the run.
# ---------------------------------------------------------------------------

if (!requireNamespace("hoopR", quietly = TRUE)) {
  stop("hoopR is not installed. In R, run: install.packages(\"hoopR\")", call. = FALSE)
}
if (!requireNamespace("curl", quietly = TRUE)) {
  stop("The curl package is missing. In R, run: install.packages(\"curl\")", call. = FALSE)
}
suppressPackageStartupMessages(library(hoopR))
options(width = 200)

# Seasons -------------------------------------------------------------------
# most_recent_nba_season() returns the END year of the current season.
# In November 2026 it returns 2027, so the current season is "2026-27".
this_season <- year_to_season(most_recent_nba_season() - 1)
last_season <- year_to_season(most_recent_nba_season() - 2)
espn_season <- most_recent_nba_season()
pause_seconds <- 2

# hoopR gives up on a call after about 60 seconds. A call that fails after
# waiting this long is counted as a timeout.
slow_seconds <- 50

# Set to FALSE by the network check below, or after two NBA calls in a row
# time out. Once FALSE, the remaining NBA stats tests are skipped.
nba_reachable <- TRUE
nba_timeouts_in_a_row <- 0

cat("Opponent Scout pull test\n")
cat("R version:    ", R.version.string, "\n")
cat("hoopR version:", as.character(utils::packageVersion("hoopR")), "\n")
cat("This season:  ", this_season, "\n")
cat("Last season:  ", last_season, "\n\n")

results <- list()

# Helpers -------------------------------------------------------------------

# hoopR's NBA functions return a named list of tables. This picks the table we
# asked for by name, or falls back to the first table that has rows.
first_table <- function(x, pick = NULL) {
  if (is.null(x)) {
    return(NULL)
  }
  if (is.data.frame(x)) {
    return(x)
  }
  if (is.list(x)) {
    if (!is.null(pick) && pick %in% names(x) && is.data.frame(x[[pick]])) {
      return(x[[pick]])
    }
    for (item in x) {
      if (is.data.frame(item) && nrow(item) > 0) {
        return(item)
      }
    }
    for (item in x) {
      if (is.data.frame(item)) {
        return(item)
      }
    }
  }
  NULL
}

# Fetches one URL with a hard time limit set inside curl itself, and reports
# whether it answered. Used for the network check before the real tests.
site_answers <- function(url, seconds, headers = NULL) {
  handle <- curl::new_handle()
  curl::handle_setopt(handle, timeout = seconds, connecttimeout = 10)
  if (!is.null(headers)) {
    do.call(curl::handle_setheaders, c(list(handle), as.list(headers)))
  }
  started <- Sys.time()
  out <- tryCatch(
    {
      res <- curl::curl_fetch_memory(url, handle = handle)
      list(ok = res$status_code == 200, detail = paste("HTTP status", res$status_code))
    },
    error = function(e) list(ok = FALSE, detail = conditionMessage(e))
  )
  out$seconds <- round(as.numeric(difftime(Sys.time(), started, units = "secs")), 1)
  out
}

record_result <- function(name, feeds, status, required, rows, cols, seconds, note) {
  results[[length(results) + 1]] <<- data.frame(
    test = name,
    feeds = feeds,
    status = status,
    required = required,
    rows = rows,
    cols = cols,
    seconds = seconds,
    note = substr(note, 1, 200),
    stringsAsFactors = FALSE
  )
}

# Prints the newest date found in a table, so we can see how fresh a
# pre-pulled file is. Looks at the first column with "date" in its name.
show_latest_date <- function(tbl) {
  if (is.null(tbl) || nrow(tbl) == 0) {
    return(invisible(NULL))
  }
  date_cols <- grep("date", names(tbl), ignore.case = TRUE, value = TRUE)
  if (length(date_cols) == 0) {
    return(invisible(NULL))
  }
  latest <- tryCatch(
    {
      raw <- as.character(tbl[[date_cols[1]]])
      raw <- raw[!is.na(raw) & nchar(raw) >= 8]
      as.character(max(raw))
    },
    error = function(e) NA_character_,
    warning = function(w) NA_character_
  )
  cat(sprintf("    newest value in %s: %s\n", date_cols[1], latest))
  invisible(NULL)
}

# Prints the most common values in one column, so we can learn the labels a
# file uses (for example shot types or game types).
show_values <- function(tbl, col, n = 12, label = col) {
  if (is.null(tbl) || nrow(tbl) == 0 || !(col %in% names(tbl))) {
    return(invisible(NULL))
  }
  tryCatch(
    {
      counts <- sort(table(as.character(tbl[[col]])), decreasing = TRUE)
      top <- utils::head(counts, n)
      cat(sprintf("    most common %s: %s\n", label,
                  paste(sprintf("%s (%s)", names(top), as.integer(top)), collapse = "; ")))
    },
    error = function(e) NULL
  )
  invisible(NULL)
}

# Runs one pull, records PASS / EMPTY / CHECK / FAIL / TIMEOUT / SKIP, and
# returns the table.
#   name      short label for the pull
#   feeds     which app feature depends on it
#   pull      a function with no arguments that makes the hoopR call
#   pick      name of the table to take from the returned list (optional)
#   needs     column names the app relies on (checked without regard to case)
#   required  FALSE for nice-to-have pulls
#   nba_stats TRUE if the call hits the NBA stats site (adds the pause)
#   peek      TRUE prints the column names, for pulls where we still need to
#             learn what the fields are called
run_test <- function(name, feeds, pull, pick = NULL, needs = character(0),
                     required = TRUE, nba_stats = TRUE, peek = FALSE) {
  if (nba_stats && !nba_reachable) {
    # Recorded quietly. The summary reports how many were skipped.
    record_result(name, feeds, "SKIP", required, 0L, 0L, 0, "NBA stats site not reachable")
    return(invisible(NULL))
  }
  cat(sprintf("Testing: %s ... ", name))
  started <- Sys.time()
  # Warnings are collected here and shown in the note, so they do not flood
  # the screen.
  warn_msgs <- character(0)
  out <- tryCatch(
    withCallingHandlers(
      list(value = pull(), error = NA_character_),
      warning = function(w) {
        warn_msgs <<- c(warn_msgs, conditionMessage(w))
        invokeRestart("muffleWarning")
      }
    ),
    error = function(e) list(value = NULL, error = conditionMessage(e))
  )
  seconds <- round(as.numeric(difftime(Sys.time(), started, units = "secs")), 1)
  tbl <- first_table(out$value, pick)
  timed_out <- is.null(tbl) && seconds >= slow_seconds

  status <- "PASS"
  note <- ""
  if (timed_out) {
    status <- "TIMEOUT"
    note <- sprintf("no answer after %s seconds", seconds)
  } else if (!is.na(out$error)) {
    status <- "FAIL"
    note <- out$error
  } else if (is.null(tbl)) {
    status <- "FAIL"
    note <- "returned no table"
  } else if (nrow(tbl) == 0) {
    status <- "EMPTY"
    note <- "table has 0 rows"
    if (any(grepl("arrow", warn_msgs, fixed = TRUE))) {
      note <- "needs the arrow package (see the install line in the summary)"
    } else if (length(warn_msgs) > 0) {
      note <- gsub("\\s+", " ", warn_msgs[length(warn_msgs)])
    }
  } else {
    missing_cols <- setdiff(toupper(needs), toupper(names(tbl)))
    if (length(missing_cols) > 0) {
      status <- "CHECK"
      note <- paste("missing columns:", paste(missing_cols, collapse = ", "))
    }
  }

  rows <- if (is.null(tbl)) 0L else nrow(tbl)
  cols <- if (is.null(tbl)) 0L else ncol(tbl)
  cat(sprintf("%s (%s rows, %s sec)\n", status, rows, seconds))
  if (status != "PASS" && nzchar(note)) {
    cat("    ", substr(note, 1, 160), "\n", sep = "")
  }
  if (peek && !is.null(tbl) && ncol(tbl) > 0) {
    shown <- utils::head(names(tbl), 40)
    more <- if (ncol(tbl) > 40) sprintf(" ... (%s columns in all)", ncol(tbl)) else ""
    cat("    columns: ", paste(shown, collapse = ", "), more, "\n", sep = "")
  }

  record_result(name, feeds, status, required, rows, cols, seconds, note)

  if (nba_stats) {
    if (timed_out) {
      nba_timeouts_in_a_row <<- nba_timeouts_in_a_row + 1
      if (nba_timeouts_in_a_row >= 2) {
        nba_reachable <<- FALSE
        cat("  Two NBA calls in a row timed out. Skipping the rest of the NBA stats tests.\n")
      }
    } else {
      nba_timeouts_in_a_row <<- 0
    }
    Sys.sleep(pause_seconds)
  }
  invisible(tbl)
}

# 0. Network check ----------------------------------------------------------
# Two quick requests with a hard time limit. The first confirms the internet
# works at all. The second asks the NBA stats site for a small table. The NBA
# stats site does not answer some networks (cloud servers, and some campus or
# office networks). If it fails here, the NBA tests are skipped so the run
# takes seconds, not an hour.

cat("Checking the internet connection (ESPN) ... ")
espn_check <- site_answers(
  "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams", 15
)
cat(sprintf("%s (%s, %s sec)\n", if (espn_check$ok) "ok" else "NO",
            espn_check$detail, espn_check$seconds))

cat("Checking the NBA stats site ... ")
nba_check <- site_answers(
  paste0("https://stats.nba.com/stats/commonallplayers?LeagueID=00&Season=",
         this_season, "&IsOnlyCurrentSeason=1"),
  20,
  headers = c(
    "Host" = "stats.nba.com",
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0",
    "Accept" = "application/json, text/plain, */*",
    "Accept-Language" = "en-US,en;q=0.5",
    "x-nba-stats-origin" = "stats",
    "x-nba-stats-token" = "true",
    "Referer" = "https://www.nba.com/",
    "Connection" = "keep-alive"
  )
)
cat(sprintf("%s (%s, %s sec)\n\n", if (nba_check$ok) "ok" else "NO",
            nba_check$detail, nba_check$seconds))

if (!nba_check$ok) {
  nba_reachable <- FALSE
  if (espn_check$ok) {
    cat("  The internet works, but the NBA stats site did not give a usable answer\n")
    cat("  from this network. A timeout or an HTTP status other than 200 both mean\n")
    cat("  the same thing: a network block, not a problem with your setup.\n")
    cat("  Fix: switch to a phone hotspot or a home internet connection, turn off\n")
    cat("  any VPN, and run this script again.\n")
  } else {
    cat("  Neither site answered. Check that this computer is online, then rerun.\n")
  }
  cat("  The live NBA stats tests are skipped. The ESPN and file tests still run.\n\n")
}

# 1. Players and teams ------------------------------------------------------

player_stats <- run_test(
  "Player season stats (this season)", "player cards, ratings",
  function() nba_leaguedashplayerstats(season = this_season, per_mode = "PerGame"),
  needs = c("PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", "PTS")
)

# Pick a real, active player and his team for the per-player tests below.
# Falls back to fixed ids if the pull above failed.
test_player_id <- "203999"
test_team_id <- "1610612743"
test_player_name <- "fallback player"
if (!is.null(player_stats) && nrow(player_stats) > 0 &&
    all(c("PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", "PTS") %in% names(player_stats))) {
  gp <- suppressWarnings(as.numeric(player_stats$GP))
  pts <- suppressWarnings(as.numeric(player_stats$PTS))
  regulars <- which(!is.na(gp) & !is.na(pts) & gp >= max(gp, na.rm = TRUE) / 2)
  if (length(regulars) > 0) {
    top <- regulars[which.max(pts[regulars])]
    test_player_id <- as.character(player_stats$PLAYER_ID[top])
    test_team_id <- as.character(player_stats$TEAM_ID[top])
    test_player_name <- as.character(player_stats$PLAYER_NAME[top])
  }
}
if (nba_reachable) {
  cat(sprintf("  Using %s (player %s, team %s) for the per-player tests\n",
              test_player_name, test_player_id, test_team_id))
}

run_test(
  "Player season stats (last season)", "blend with last season",
  function() nba_leaguedashplayerstats(season = last_season, per_mode = "PerGame"),
  needs = c("PLAYER_ID", "PTS")
)

run_test(
  "Player height and weight", "matchup model, top three defenders",
  function() nba_leaguedashplayerbiostats(season = this_season),
  needs = c("PLAYER_ID", "PLAYER_HEIGHT_INCHES", "PLAYER_WEIGHT")
)

run_test(
  "Team advanced stats", "team scouting profile (pace, ratings)",
  function() nba_leaguedashteamstats(season = this_season, measure_type = "Advanced",
                                     per_mode = "PerGame"),
  needs = c("TEAM_ID", "PACE")
)

run_test(
  "Team four factors", "team scouting profile",
  function() nba_leaguedashteamstats(season = this_season, measure_type = "Four Factors",
                                     per_mode = "PerGame"),
  needs = c("TEAM_ID")
)

# 2. Shots ------------------------------------------------------------------

run_test(
  "Shot chart, one player (this season)", "shot profiles, favorite shots",
  function() nba_shotchartdetail(player_id = test_player_id, season = this_season,
                                 context_measure = "FGA"),
  pick = "Shot_Chart_Detail",
  needs = c("LOC_X", "LOC_Y", "ACTION_TYPE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA",
            "SHOT_DISTANCE", "SHOT_MADE_FLAG")
)

run_test(
  "Shot chart, one player (last season)", "blend with last season",
  function() nba_shotchartdetail(player_id = test_player_id, season = last_season,
                                 context_measure = "FGA"),
  pick = "Shot_Chart_Detail",
  needs = c("LOC_X", "LOC_Y", "ACTION_TYPE")
)

# Nice to have: if this passes, the whole league's shots come in one call per
# date range instead of one call per player. It decides how long seeding takes.
run_test(
  "Shot chart, whole league, last 4 days", "faster seed pull",
  function() nba_shotchartdetail(player_id = "0", team_id = 0, season = this_season,
                                 context_measure = "FGA",
                                 date_from = format(Sys.Date() - 4, "%m/%d/%Y")),
  pick = "Shot_Chart_Detail",
  needs = c("PLAYER_ID", "LOC_X", "LOC_Y", "ACTION_TYPE"),
  required = FALSE
)

run_test(
  "Tracking shots: 0 dribbles", "catch-and-shoot rating",
  function() nba_leaguedashplayerptshot(season = this_season, dribble_range = "0 Dribbles"),
  needs = c("PLAYER_ID", "FGA", "FG_PCT")
)

run_test(
  "Tracking shots: 3-6 dribbles", "pull-up rating",
  function() nba_leaguedashplayerptshot(season = this_season, dribble_range = "3-6 Dribbles"),
  needs = c("PLAYER_ID", "FGA")
)

run_test(
  "Tracking shots: tightly guarded", "shot profiles",
  function() nba_leaguedashplayerptshot(season = this_season,
                                        close_def_dist_range = "0-2 Feet - Very Tight"),
  needs = c("PLAYER_ID", "FGA")
)

run_test(
  "Tracking shots: pull-ups", "pull-up rating",
  function() nba_leaguedashplayerptshot(season = this_season, general_range = "Pullups"),
  needs = c("PLAYER_ID", "FGA")
)

# 3. Play types -------------------------------------------------------------

run_test(
  "Play types: player isolation (offense)", "how he gets his shots",
  function() nba_synergyplaytypes(play_type = "Isolation", player_or_team = "P",
                                  type_grouping = "Offensive", season = this_season),
  needs = c("PLAYER_ID", "POSS", "PPP")
)

run_test(
  "Play types: player pick and roll ball handler", "how he gets his shots",
  function() nba_synergyplaytypes(play_type = "PRBallHandler", player_or_team = "P",
                                  type_grouping = "Offensive", season = this_season),
  needs = c("PLAYER_ID", "POSS", "PPP")
)

run_test(
  "Play types: player post up", "post scoring rating",
  function() nba_synergyplaytypes(play_type = "Postup", player_or_team = "P",
                                  type_grouping = "Offensive", season = this_season),
  needs = c("PLAYER_ID", "POSS", "PPP")
)

run_test(
  "Play types: team transition (offense)", "team scouting profile",
  function() nba_synergyplaytypes(play_type = "Transition", player_or_team = "T",
                                  type_grouping = "Offensive", season = this_season),
  needs = c("TEAM_ID", "POSS", "PPP")
)

run_test(
  "Play types: team spot up (defense)", "team scouting profile",
  function() nba_synergyplaytypes(play_type = "Spotup", player_or_team = "T",
                                  type_grouping = "Defensive", season = this_season),
  needs = c("TEAM_ID", "POSS", "PPP")
)

run_test(
  "Play types: player isolation (last season)", "blend with last season",
  function() nba_synergyplaytypes(play_type = "Isolation", player_or_team = "P",
                                  type_grouping = "Offensive", season = last_season),
  needs = c("PLAYER_ID", "POSS")
)

# 4. Defense and matchups ---------------------------------------------------

run_test(
  "Matchups: who guarded whom (one team's defenders)", "matchup model",
  function() nba_leagueseasonmatchups(def_team_id = test_team_id, season = this_season),
  pick = "SeasonMatchups",
  needs = c("OFF_PLAYER_ID", "DEF_PLAYER_ID", "PARTIAL_POSS", "PLAYER_PTS")
)

run_test(
  "Matchups (last season)", "blend with last season",
  function() nba_leagueseasonmatchups(def_team_id = test_team_id, season = last_season),
  pick = "SeasonMatchups",
  needs = c("OFF_PLAYER_ID", "DEF_PLAYER_ID")
)

run_test(
  "Tracking defense: overall", "perimeter defense rating, matchup model",
  function() nba_leaguedashptdefend(season = this_season, defense_category = "Overall"),
  needs = c("D_FGA", "D_FG_PCT")
)

run_test(
  "Tracking defense: inside 6 feet", "interior defense rating",
  function() nba_leaguedashptdefend(season = this_season, defense_category = "Less Than 6Ft"),
  needs = character(0)
)

# 5. Other tracking stats ---------------------------------------------------

run_test(
  "Tracking: drives", "finishing rating, shot profiles",
  function() nba_leaguedashptstats(season = this_season, pt_measure_type = "Drives",
                                   player_or_team = "Player"),
  needs = c("PLAYER_ID", "DRIVES")
)

run_test(
  "Tracking: passing", "playmaking rating",
  function() nba_leaguedashptstats(season = this_season, pt_measure_type = "Passing",
                                   player_or_team = "Player"),
  needs = c("PLAYER_ID")
)

run_test(
  "Tracking: rebounding", "rebounding rating",
  function() nba_leaguedashptstats(season = this_season, pt_measure_type = "Rebounding",
                                   player_or_team = "Player"),
  needs = c("PLAYER_ID")
)

run_test(
  "Tracking: speed and distance", "speed rating",
  function() nba_leaguedashptstats(season = this_season, pt_measure_type = "SpeedDistance",
                                   player_or_team = "Player"),
  needs = c("PLAYER_ID", "AVG_SPEED"),
  required = FALSE
)

run_test(
  "Passing: who feeds one player", "how he gets his shots",
  function() nba_playerdashptpass(player_id = test_player_id, team_id = test_team_id,
                                  season = this_season),
  pick = "PassesReceived",
  needs = character(0)
)

# 6. Lineups and rotations --------------------------------------------------

run_test(
  "Five-man lineups (one team)", "rotation scouting",
  function() nba_leaguedashlineups(team_id = test_team_id, group_quantity = 5,
                                   season = this_season),
  needs = c("GROUP_ID", "GROUP_NAME", "MIN")
)

game_log <- run_test(
  "League game log", "finds game ids for rotation pulls",
  function() nba_leaguegamelog(season = this_season, player_or_team = "T"),
  pick = "LeagueGameLog",
  needs = c("GAME_ID", "TEAM_ID", "GAME_DATE")
)

test_game_id <- NULL
if (!is.null(game_log) && nrow(game_log) > 0 && "GAME_ID" %in% names(game_log)) {
  test_game_id <- as.character(game_log$GAME_ID[nrow(game_log)])
}

if (!is.null(test_game_id)) {
  run_test(
    "Substitution pattern for one game", "rotation scouting",
    function() nba_gamerotation(game_id = test_game_id),
    needs = c("PERSON_ID", "IN_TIME_REAL", "OUT_TIME_REAL")
  )
} else {
  if (nba_reachable) cat("Skipping the substitution pattern test: no game id available\n")
}

# 7. Measurements -----------------------------------------------------------

run_test(
  "Draft combine measurements", "wingspan for the matchup model",
  function() nba_draftcombineplayeranthro(season_year = most_recent_nba_season() - 2),
  needs = c("PLAYER_ID", "WINGSPAN"),
  required = FALSE
)

# 8. ESPN feeds (not the NBA stats site) ------------------------------------

schedule <- run_test(
  "Season schedule (ESPN)", "calendar of upcoming games",
  function() load_nba_schedule(seasons = espn_season),
  nba_stats = FALSE
)

# How many games are still ahead? The calendar needs future games.
if (!is.null(schedule) && nrow(schedule) > 0) {
  date_col <- intersect(c("game_date", "date"), names(schedule))
  if (length(date_col) > 0) {
    upcoming <- tryCatch(
      sum(as.Date(substr(as.character(schedule[[date_col[1]]]), 1, 10)) >= Sys.Date(),
          na.rm = TRUE),
      error = function(e) NA
    )
    cat(sprintf("  Upcoming games found in the schedule: %s\n", upcoming))
  } else {
    cat("  Could not find a date column. Columns start with:",
        paste(utils::head(names(schedule), 12), collapse = ", "), "\n")
  }
}

run_test(
  "Player box scores with headshot link (ESPN)", "player cards",
  function() load_nba_player_box(seasons = espn_season),
  needs = c("athlete_id", "athlete_display_name", "athlete_headshot_href"),
  nba_stats = FALSE
)

run_test(
  "Team list (ESPN)", "team picker and search box",
  function() espn_nba_teams(),
  nba_stats = FALSE
)

run_test(
  "Injuries (ESPN)", "injury tags in the lineup editor",
  function() espn_nba_injuries(),
  nba_stats = FALSE
)

# 9. Team context: records, seeds, streaks, game types ----------------------
# These print their column names so we can see what the fields are called.

run_test(
  "Standings: record, seed, streak", "team page header",
  function() nba_leaguestandingsv3(season = this_season),
  pick = "Standings",
  peek = TRUE
)

run_test(
  "NBA Cup standings", "NBA Cup icon and group info",
  function() nba_iststandings(season = this_season),
  required = FALSE,
  peek = TRUE
)

run_test(
  "NBA schedule with game labels", "NBA Cup and playoff icons",
  function() nba_schedule(season = this_season),
  required = FALSE,
  peek = TRUE
)

# 10. Trait badges ----------------------------------------------------------

run_test(
  "Hustle stats (deflections, loose balls)", "on-ball pest badge",
  function() nba_leaguehustlestatsplayer(season = this_season),
  needs = c("PLAYER_ID", "DEFLECTIONS")
)

if (!is.null(test_game_id)) {
  run_test(
    "Play-by-play for one game", "on-ball steals (lost ball vs bad pass)",
    function() nba_pbp(game_id = test_game_id, on_court = FALSE),
    peek = TRUE
  )
} else {
  if (nba_reachable) cat("Skipping the play-by-play test: no game id available\n")
}

run_test(
  "Dunk score leaders", "dunk badge",
  function() nba_dunkscoreleaders(season = this_season),
  required = FALSE,
  peek = TRUE
)

run_test(
  "Draft combine drill results (vertical leap)", "dunk badge",
  function() nba_draftcombinedrillresults(season_year = most_recent_nba_season() - 2),
  required = FALSE,
  peek = TRUE
)

run_test(
  "Clutch stats", "clutch badge",
  function() nba_leaguedashplayerclutch(season = this_season),
  needs = c("PLAYER_ID"),
  required = FALSE
)

# 11. Pre-pulled NBA stats files --------------------------------------------
# hoopR also publishes ready-made copies of many NBA stats tables as files.
# They download from a file host, not from the NBA stats site, so they work on
# networks the NBA site ignores, and one file holds a whole season. These
# tests run on any network. Their `seasons` argument is the season's START
# year (2026 for 2026-27).

stats_season <- most_recent_nba_stats_season()
cat(sprintf("\nPre-pulled files: this season = %s, last season = %s\n",
            stats_season, stats_season - 1))

arrow_install_line <- "Rscript -e 'install.packages(\"arrow\", repos = \"https://cloud.r-project.org\")'"
has_arrow <- requireNamespace("arrow", quietly = TRUE)
if (!has_arrow) {
  cat("  NOTE: the arrow package is not installed, so most file tests will be EMPTY.\n")
  cat("  Install it with this line, then rerun:\n")
  cat("    ", arrow_install_line, "\n", sep = "")
}

file_shots <- run_test(
  "File: shots (this season)", "shot profiles, favorite shots, badges",
  function() load_nba_stats_shots(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE
)
show_latest_date(file_shots)
show_values(file_shots, "sub_type", 20, "shot types")
show_values(file_shots, "season_type_id", 6, "season_type_id values")

run_test(
  "File: shots (last season)", "blend with last season",
  function() load_nba_stats_shots(seasons = stats_season - 1),
  nba_stats = FALSE
)

run_test(
  "File: play types", "team profile, how he gets his shots",
  function() load_nba_stats_synergy(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE
)

# Matchups come in two files. The per-game file has one row per offensive
# player, defensive player and game, and it exists for this season. The app
# sums it into pair totals. The season-totals file had no 2026-27 copy when
# checked on Nov 16, 2026, so its this-season test is not required.
matchup_columns <- c(
  "game_id", "off_team_id", "def_team_id", "off_person_id", "def_person_id",
  "partial_possessions", "switches_on", "player_points", "team_points",
  "matchup_field_goals_made", "matchup_field_goals_attempted",
  "matchup_three_pointers_made", "matchup_three_pointers_attempted",
  "matchup_free_throws_attempted", "matchup_turnovers"
)

file_game_matchups <- run_test(
  "File: per-game matchups (this season)", "matchup model, model check",
  function() load_nba_stats_game_matchups(seasons = stats_season),
  needs = matchup_columns, nba_stats = FALSE, peek = TRUE
)
if (!is.null(file_game_matchups) && "game_id" %in% names(file_game_matchups)) {
  cat(sprintf("  Games covered: %d\n", length(unique(file_game_matchups$game_id))))
}

run_test(
  "File: per-game matchups (last season)", "blend with last season",
  function() load_nba_stats_game_matchups(seasons = stats_season - 1),
  needs = matchup_columns, nba_stats = FALSE
)

run_test(
  "File: season matchup totals (this season)", "not needed, per-game file is used",
  function() load_nba_stats_matchups(seasons = stats_season),
  required = FALSE, nba_stats = FALSE, peek = TRUE
)

run_test(
  "File: season matchup totals (last season)", "cross-check for summed per-game rows",
  function() load_nba_stats_matchups(seasons = stats_season - 1),
  required = FALSE, nba_stats = FALSE, peek = TRUE
)

leaguedash_tables <- c(
  "player_bio", "player_stats_base", "player_stats_advanced",
  "team_stats_advanced", "team_stats_fourfactors",
  "player_tracking_defense", "player_tracking_drives", "player_tracking_passing",
  "player_tracking_rebounding", "player_tracking_catchshoot",
  "player_tracking_pullupshot", "player_tracking_posttouch",
  "player_tracking_speeddistance", "lineups_base", "standings"
)
for (tbl_name in leaguedash_tables) {
  local({
    this_table <- tbl_name
    run_test(
      sprintf("File: %s", this_table), "ratings, team profile, rotations, header",
      function() load_nba_stats_leaguedash(seasons = stats_season, table = this_table),
      nba_stats = FALSE,
      peek = this_table %in% c("player_bio", "standings", "lineups_base",
                               "player_tracking_defense", "team_stats_advanced")
    )
  })
}

run_test(
  "File: hustle stats", "on-ball pest badge",
  function() load_nba_stats_hustle_player(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE
)

file_logs <- run_test(
  "File: player game logs", "last game standout, streaks",
  function() load_nba_stats_player_game_logs(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE
)
show_latest_date(file_logs)

file_schedule <- run_test(
  "File: NBA schedule", "calendar, NBA Cup and playoff icons",
  function() load_nba_stats_schedule(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE
)
show_latest_date(file_schedule)
show_values(file_schedule, "season_type", 8, "season_type values")

run_test(
  "File: game lineups", "rotation scouting",
  function() load_nba_stats_game_lineups(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE, required = FALSE
)

file_pbp <- run_test(
  "File: play-by-play", "on-ball steals (lost ball vs bad pass)",
  function() load_nba_stats_pbp(seasons = stats_season),
  nba_stats = FALSE, peek = TRUE, required = FALSE
)
if (!is.null(file_pbp) && nrow(file_pbp) > 0 &&
    all(c("action_type", "sub_type") %in% names(file_pbp))) {
  show_values(file_pbp, "action_type", 15, "play-by-play action types")
  turnovers <- file_pbp[grepl("turnover", tolower(as.character(file_pbp$action_type))), ]
  show_values(turnovers, "sub_type", 12, "turnover types")
  # About two thirds of made shots name the passer, as in "(Robinson 1 AST)".
  made_shots <- file_pbp[as.character(file_pbp$action_type) == "Made Shot", ]
  if (nrow(made_shots) > 0 && "description" %in% names(made_shots)) {
    cat(sprintf("  Made shots that name a passer: %.1f%%\n",
                100 * mean(grepl("AST\\)", made_shots$description))))
  }
}

# Injury report. Uses NBA ids, so no name matching is needed. Rows whose
# reason is "NOT YET SUBMITTED" have no player and are skipped by the pull.
file_injuries <- run_test(
  "File: injury report", "injury tags in the lineup editor",
  function() load_nba_stats_injury_report(seasons = stats_season),
  needs = c("report_datetime", "game_date", "team_id", "person_id",
            "report_player_name", "current_status", "reason"),
  nba_stats = FALSE, peek = TRUE
)
if (!is.null(file_injuries) && nrow(file_injuries) > 0 &&
    "report_datetime" %in% names(file_injuries)) {
  cat("  Latest report:", format(max(file_injuries$report_datetime, na.rm = TRUE)), "\n")
  show_values(file_injuries, "current_status", 8, "injury statuses")
}

# ESPN play-by-play. The NBA stats play-by-play does not name who made a
# steal, but ESPN does: on a turnover row, athlete_id_2 is the stealer and
# the text ends with "(Name steals)". ESPN takes the END year of the season.
espn_pbp <- run_test(
  "ESPN play-by-play", "on-ball pest badge (lost-ball steals)",
  function() load_nba_pbp(seasons = espn_season),
  needs = c("game_id", "type_text", "text", "team_id", "athlete_id_1", "athlete_id_2"),
  nba_stats = FALSE
)
if (!is.null(espn_pbp) && nrow(espn_pbp) > 0 &&
    all(c("type_text", "text", "athlete_id_2") %in% names(espn_pbp))) {
  lost_ball <- espn_pbp[espn_pbp$type_text == "Lost Ball Turnover", ]
  named <- sum(!is.na(lost_ball$athlete_id_2) & grepl("steals\\)", lost_ball$text))
  cat(sprintf("  Lost-ball turnovers: %d, with a named stealer: %d\n", nrow(lost_ball), named))
  if (named == 0) {
    record_result("ESPN play-by-play names the stealer", "on-ball pest badge",
                  "CHECK", TRUE, 0L, 0L, 0, "no lost-ball turnover names a stealer")
  }
}

run_test(
  "File: draft combine measurements", "wingspan",
  function() load_nba_stats_draft_combine_anthro(seasons = stats_season - 1),
  nba_stats = FALSE, peek = TRUE, required = FALSE
)

run_test(
  "File: draft combine drills", "vertical leap",
  function() load_nba_stats_draft_combine_drills(seasons = stats_season - 1),
  nba_stats = FALSE, peek = TRUE, required = FALSE
)

# Summary -------------------------------------------------------------------

summary_table <- do.call(rbind, results)
skipped <- summary_table[summary_table$status == "SKIP", ]
ran <- summary_table[summary_table$status != "SKIP", ]

cat("\n================ RESULTS ================\n")
if (nrow(ran) > 0) {
  print(ran[, c("test", "status", "required", "rows", "seconds")], row.names = FALSE)
}
if (nrow(skipped) > 0) {
  cat(sprintf("\n%s live NBA stats tests were skipped (site not reachable from this network).\n",
              nrow(skipped)))
}

problems <- ran[ran$status != "PASS", ]
if (nrow(problems) > 0) {
  cat("\n---- Details for anything that ran and did not pass ----\n")
  for (i in seq_len(nrow(problems))) {
    cat(sprintf("[%s] %s\n    feeds: %s\n    note:  %s\n",
                problems$status[i], problems$test[i], problems$feeds[i], problems$note[i]))
  }
}

out_dir <- if (dir.exists("pulls")) "pulls" else "."
out_file <- file.path(out_dir, "test_pulls_results.csv")
utils::write.csv(summary_table, out_file, row.names = FALSE)
cat(sprintf("\nSaved the full table to %s\n", out_file))

required_bad <- ran[ran$required & ran$status != "PASS", ]
cat("\n================ VERDICT ================\n")
cat(sprintf("Passed: %s   Did not pass: %s   Skipped: %s\n",
            sum(ran$status == "PASS"), sum(ran$status != "PASS"), nrow(skipped)))
if (nrow(required_bad) == 0 && nrow(skipped) == 0) {
  cat("All required pulls passed. The data gate is clear.\n")
} else {
  if (nrow(required_bad) > 0) {
    cat(sprintf("%s required pull(s) ran and need attention:\n", nrow(required_bad)))
    cat(paste0("  - ", required_bad$test, " [", required_bad$status, "]"), sep = "\n")
  } else {
    cat("Every required pull that ran has passed.\n")
  }
  if (!has_arrow) {
    cat("\nThe arrow package is missing. Install it, then rerun:\n")
    cat("  ", arrow_install_line, "\n", sep = "")
  }
  if (nrow(skipped) > 0) {
    cat("\nTo test the skipped live NBA pulls, rerun on a phone hotspot or home internet.\n")
  }
  cat("\nWhat the statuses mean:\n")
  cat("  TIMEOUT  no answer after about a minute. Usually a network block.\n")
  cat("  FAIL     the call errored or returned nothing.\n")
  cat("  EMPTY    the call worked but had no rows. The note says why when known.\n")
  cat("  CHECK    rows came back but an expected column has a different name.\n")
}
