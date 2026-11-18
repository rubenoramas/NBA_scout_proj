#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Opponent Scout: shot pull
#
# What this does
#   Writes three seed files into data/seed/:
#     shots.jsonl.gz        this season, one document per shot (gzip)
#     shot_zones_last.jsonl last season, per-player totals by zone
#     shot_types_last.jsonl last season, per-player totals by shot type
#   Each shot gets a zone and a side, worked out from its coordinates with
#   the rule below, and the script prints checks of that rule.
#
# How to run (from the repo root)
#   Rscript pulls/pull_shots.R      (or ./refresh.sh, which runs every pull)
#
# The zone rule
#   x_legacy and y_legacy are in tenths of a foot. The basket is at (0, 0),
#   the baseline is at y = -47.5, and x runs from -250 to 250 across the
#   court. Whether a shot is a 2 or a 3 comes from the official shot_value.
#     Restricted area        2-pointer within 4 ft: sqrt(x^2 + y^2) <= 40
#     Paint                  other 2-pointer inside the lane: |x| <= 80 and
#                            y <= 142.5 (the free throw line)
#     Midrange               any other 2-pointer
#     Corner three           3-pointer with y <= 92.5 (the straight part of
#                            the line, 14 ft from the baseline)
#     Above-the-break three  any other 3-pointer
#   Side: "center" when |x| <= 80 (the width of the lane), otherwise "left"
#   or "right" from the shooter's view facing the basket, assuming negative
#   x is the shooter's right. That assumption is NOT confirmed yet. Run
#   pulls/check_sides.R from a network that reaches the NBA stats site to
#   check it. The app does not show sides until it is confirmed.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(hoopR)
  library(dplyr)
  library(jsonlite)
})
if (!requireNamespace("arrow", quietly = TRUE)) {
  stop("The arrow package is missing, so the shot files would load empty. In R, run: install.packages(\"arrow\")",
       call. = FALSE)
}

season_start <- most_recent_nba_stats_season()
make_label <- function(start) sprintf("%d-%02d", start, (start + 1) %% 100)
seed_dir <- "data/seed"
dir.create(seed_dir, recursive = TRUE, showWarnings = FALSE)

write_jsonl <- function(df, name, gz = FALSE) {
  path <- file.path(seed_dir, paste0(name, if (gz) ".jsonl.gz" else ".jsonl"))
  con <- if (gz) gzfile(path, open = "w", encoding = "UTF-8") else file(path, open = "w", encoding = "UTF-8")
  stream_out(df, con, na = "null", digits = NA, verbose = FALSE)
  close(con)
  cat(sprintf("  %-22s %7d rows\n", basename(path), nrow(df)))
}

cat("Opponent Scout shot pull, season", make_label(season_start), "\n\nDownloading...\n")
shots_raw      <- suppressMessages(load_nba_stats_shots(seasons = season_start))
last_shots_raw <- suppressMessages(load_nba_stats_shots(seasons = season_start - 1))
# Shots have no date, so dates come from the schedule by game id.
schedule_raw   <- suppressMessages(load_nba_stats_schedule(seasons = season_start))
if (nrow(shots_raw) == 0) stop("The shots file came back empty. Nothing was written.", call. = FALSE)

# 1. The zone rule ----------------------------------------------------------
# case_when() checks each condition in order and uses the first that is TRUE.
add_zones <- function(df) {
  df %>% mutate(
    x = as.numeric(x_legacy),
    y = as.numeric(y_legacy),
    zone = case_when(
      shot_value == 2 & sqrt(x^2 + y^2) <= 40 ~ "restricted_area",
      shot_value == 2 & abs(x) <= 80 & y <= 142.5 ~ "paint",
      shot_value == 2 ~ "midrange",
      shot_value == 3 & y <= 92.5 ~ "corner_three",
      shot_value == 3 ~ "above_break_three"
    ),
    side = case_when(abs(x) <= 80 ~ "center", x < 0 ~ "right", TRUE ~ "left")
  )
}

shots_zoned <- add_zones(shots_raw)
last_zoned  <- add_zones(last_shots_raw)

# 2. Checks of the rule -----------------------------------------------------
cat("\nChecks of the zone rule (this season):\n")
# The description states the distance, such as "Collins 25' 3PT Jump Shot".
stated <- suppressWarnings(as.numeric(sub(".*? ([0-9]+)' .*", "\\1", shots_zoned$description)))
has_stated <- grepl(" [0-9]+' ", shots_zoned$description)
computed <- sqrt(shots_zoned$x^2 + shots_zoned$y^2) / 10
cat(sprintf("  Shots with a distance in the description: %d of %d\n", sum(has_stated), nrow(shots_zoned)))
cat(sprintf("  Distance from x and y within 1 ft of the stated distance: %.1f%%\n",
            100 * mean(abs(computed[has_stated] - stated[has_stated]) <= 1)))
cat(sprintf("  \"3PT\" in the description agrees with shot_value: %.2f%%\n",
            100 * mean(grepl("3PT", shots_zoned$description) == (shots_zoned$shot_value == 3))))
corner <- shots_zoned$zone == "corner_three"
cat(sprintf("  Corner threes: %d, nearest one %.1f ft from the basket (should be about 22)\n",
            sum(corner), min(computed[corner])))
cat(sprintf("  Shots with no zone: %d\n", sum(is.na(shots_zoned$zone))))
cat("  Shots by zone:\n")
print(as.data.frame(count(shots_zoned, zone)), row.names = FALSE)
cat("  A few shots with their stated distance and zone:\n")
set.seed(7)
sample_rows <- shots_zoned[has_stated, ][sample(sum(has_stated), 8), ]
print(as.data.frame(sample_rows %>% transmute(description, x, y, computed_ft = round(sqrt(x^2 + y^2) / 10, 1), zone)),
      row.names = FALSE)

# 3. This season, shot by shot ----------------------------------------------
game_dates <- schedule_raw %>% transmute(game_id, game_date = as.character(game_date))
shots <- shots_zoned %>%
  filter(!is.na(zone)) %>%
  left_join(game_dates, by = "game_id") %>%
  transmute(
    `_id` = paste(game_id, row_number(), sep = "_"),
    game_id, game_date,
    player_id = as.integer(person_id),
    team_id = as.integer(team_id),
    period = as.integer(period),
    x = as.integer(x), y = as.integer(y),
    distance = as.integer(shot_distance),
    value = as.integer(shot_value),
    made = shot_result == "Made",
    shot_type = sub_type,
    zone, side
  )

# 4. Last season, per-player totals -----------------------------------------
# group_by() plus summarise() turns 234,876 shots into one row per player
# and zone (and per player and shot type), which keeps the repo small.
last_label <- make_label(season_start - 1)
zones_last <- last_zoned %>%
  filter(!is.na(zone)) %>%
  group_by(player_id = as.integer(person_id), zone) %>%
  summarise(fga = n(), fgm = sum(shot_result == "Made"), .groups = "drop") %>%
  mutate(`_id` = paste(player_id, zone, sep = "_"), season = last_label) %>%
  relocate(`_id`)
types_last <- last_zoned %>%
  filter(!is.na(zone)) %>%
  group_by(player_id = as.integer(person_id), shot_type = sub_type) %>%
  summarise(fga = n(), fgm = sum(shot_result == "Made"),
            level = names(sort(table(ifelse(zone == "restricted_area", "rim",
                                            ifelse(zone %in% c("paint", "midrange"), "midrange", "three"))),
                               decreasing = TRUE))[1],
            .groups = "drop") %>%
  mutate(`_id` = paste(player_id, shot_type, sep = "_"), season = last_label) %>%
  relocate(`_id`)

# 5. Write ------------------------------------------------------------------
cat("\nWriting seed files to", seed_dir, "\n")
write_jsonl(shots, "shots", gz = TRUE)
write_jsonl(zones_last, "shot_zones_last")
write_jsonl(types_last, "shot_types_last")
cat(sprintf("\nShots missing a game date: %d\n", sum(is.na(shots$game_date))))
files <- list.files(seed_dir, full.names = TRUE)
cat(sprintf("Total size of %s: %.2f MB\n", seed_dir, sum(file.size(files)) / 1024^2))
