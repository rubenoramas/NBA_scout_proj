# ---------------------------------------------------------------------------
# Opponent Scout: match ESPN players to NBA stats player ids
#
# ESPN and the NBA stats site number players differently. This file matches
# them by name, with team as a tie-breaker. It is shared by every pull that
# uses ESPN data (positions now, steals later). Load it with:
#   source("pulls/espn_match.R")
#
# Matching rules
#   1. A manual override table wins first, for names that never match.
#   2. Names are compared as a "key": accents removed, lower case, and
#      suffixes (Jr., Sr., II, III, IV, V) and punctuation dropped. So
#      "Bobby Portis Jr." and "Bobby Portis" both become "bobbyportis".
#   3. If two NBA players share a key, the one on the same team wins.
#   4. Every name that still does not match is printed, so it can be added
#      to the override table.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages(library(dplyr))

# ESPN abbreviation -> NBA stats abbreviation, for the six teams that differ.
espn_team_map <- c(GS = "GSW", NO = "NOP", NY = "NYK", SA = "SAS", UTAH = "UTA", WSH = "WAS")

espn_to_nba_team <- function(abbr) {
  ifelse(abbr %in% names(espn_team_map), espn_team_map[abbr], abbr)
}

# Manual overrides: ESPN name -> NBA player id. Add a row when a name is
# printed as unmatched. Bobby Portis is listed as "Bobby Portis Jr." by the
# NBA; suffix stripping already handles him, and the row stays as a safe
# example of the format.
name_overrides <- data.frame(
  espn_name = c("Bobby Portis"),
  nba_player_id = c(1626171L),
  stringsAsFactors = FALSE
)

name_key <- function(x) {
  x <- iconv(x, to = "ASCII//TRANSLIT")
  x <- tolower(x)
  x <- gsub("[.,']", "", x)
  # \\b marks a word boundary, so "ii" is only removed as a whole word.
  x <- gsub("\\b(jr|sr|ii|iii|iv|v)\\b", "", x)
  gsub("[^a-z]", "", x)
}

# espn:  a data frame with espn_name and espn_team (ESPN abbreviation)
# nba:   a data frame with player_id, player_name and team_abbr
# Returns espn with an nba_player_id column (NA when no match).
match_espn_players <- function(espn, nba, label = "ESPN players") {
  espn <- espn %>% mutate(key = name_key(espn_name), team = espn_to_nba_team(espn_team))
  nba <- nba %>% distinct(player_id, .keep_all = TRUE) %>% mutate(key = name_key(player_name))

  # Candidates by name key. A key shared by two NBA players gives two rows.
  candidates <- espn %>%
    left_join(nba %>% select(key, player_id, team_abbr), by = "key", relationship = "many-to-many") %>%
    group_by(espn_name, espn_team) %>%
    # Prefer the candidate on the same team; otherwise keep the only one.
    mutate(same_team = team_abbr == team, n_candidates = sum(!is.na(player_id))) %>%
    filter(n_candidates <= 1 | same_team %in% TRUE) %>%
    slice_head(n = 1) %>%
    ungroup() %>%
    mutate(nba_player_id = ifelse(n_candidates > 1 & !(same_team %in% TRUE), NA_integer_, player_id)) %>%
    select(espn_name, espn_team, nba_player_id)

  # Overrides win over name matches.
  out <- espn %>%
    select(-key, -team) %>%
    left_join(candidates, by = c("espn_name", "espn_team")) %>%
    left_join(name_overrides, by = "espn_name", suffix = c("", "_override")) %>%
    mutate(nba_player_id = ifelse(!is.na(nba_player_id_override), nba_player_id_override, nba_player_id)) %>%
    select(-nba_player_id_override)

  unmatched <- unique(out$espn_name[is.na(out$nba_player_id)])
  cat(sprintf("  %s matched to NBA ids: %d of %d\n", label,
              length(unique(out$espn_name)) - length(unmatched), length(unique(out$espn_name))))
  if (length(unmatched) > 0) {
    cat("  Unmatched ESPN names (add to name_overrides in pulls/espn_match.R):\n   ",
        paste(unmatched, collapse = "; "), "\n")
  }
  out
}
