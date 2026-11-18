#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Opponent Scout: check which side of the floor x_legacy points to
#
# Optional. Needs the live NBA stats site, which does not answer from campus
# Wi-Fi. Run it from home internet or a phone hotspot:
#   Rscript pulls/check_sides.R
#
# Why: pulls/pull_shots.R labels a shot "left" or "right" from the sign of
# x_legacy, assuming negative x is the shooter's right. The pre-pulled files
# do not say which way is which. The live shot chart endpoint does: each
# shot has LOC_X (the same numbers as x_legacy) and SHOT_ZONE_AREA, such as
# "Left Side(L)" or "Right Side(R)". This script compares the two.
#
# The app keeps sides out of the UI until this check confirms the rule.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages(library(hoopR))

# Live nba_* functions default to LAST season, so the season is always
# passed. Last season gives a full season of shots to check.
season <- year_to_season(most_recent_nba_season() - 2)
player_id <- "1628369" # Jayson Tatum: high volume from both sides of the floor

cat("Asking the live NBA stats site for", season, "shots of player", player_id, "...\n")
result <- tryCatch(
  nba_shotchartdetail(player_id = player_id, season = season, season_type = "Regular Season",
                      context_measure = "FGA", team_id = "0"),
  error = function(e) e
)
if (inherits(result, "error")) {
  stop("The live NBA stats site did not answer: ", conditionMessage(result),
       "\nThis is expected on campus Wi-Fi. Try again from home internet or a phone hotspot.", call. = FALSE)
}

shots <- result[["Shot_Chart_Detail"]]
if (is.null(shots) || nrow(shots) == 0) stop("The answer had no shots. Try another player_id.", call. = FALSE)

shots$LOC_X <- as.numeric(shots$LOC_X)
sided <- shots[shots$SHOT_ZONE_AREA %in% c("Left Side(L)", "Right Side(R)"), ]
cat("Shots in the left or right side areas:", nrow(sided), "\n\n")

table_out <- table(
  area = sided$SHOT_ZONE_AREA,
  x_sign = ifelse(sided$LOC_X < 0, "negative x", "positive x")
)
print(table_out)

left_negative <- sum(sided$SHOT_ZONE_AREA == "Left Side(L)" & sided$LOC_X < 0)
left_positive <- sum(sided$SHOT_ZONE_AREA == "Left Side(L)" & sided$LOC_X > 0)

cat("\n")
if (left_positive > left_negative) {
  cat("RESULT: positive x is the left side. This matches pull_shots.R (negative x = right).\n")
  cat("Sides can be shown in the app. Tell Claude Code: \"check_sides.R confirmed the rule\".\n")
} else if (left_negative > left_positive) {
  cat("RESULT: negative x is the left side. pull_shots.R has left and right swapped.\n")
  cat("Tell Claude Code: \"check_sides.R says flip the sides\", then rerun ./refresh.sh.\n")
} else {
  cat("RESULT: unclear. Try another player_id.\n")
}
