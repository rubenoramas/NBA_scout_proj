#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Opponent Scout: stats pull for ratings and badges
#
# What this does
#   Pulls the tables behind the twelve attributes and the trait badges for
#   this season and last season, keeps regular-season totals only, trims
#   them to the columns used, and writes seed files into data/seed/:
#     player_stats.jsonl     base, advanced and tracking stats, one row per
#                            player per season
#     play_types.jsonl       post-up possessions and points per player season
#     play_type_mix.jsonl    every offensive play type per player season
#     assist_pairs.jsonl     who assisted whom this season, from play-by-play
#     hustle.jsonl           deflections, contested threes, charges
#     steals.jsonl           steals from ESPN play-by-play, split into
#                            lost-ball steals and other steals
#     shot_extras.jsonl      deep threes, dunks by type, and the counts for
#                            the streaky shooter test
#     matchup_defense.jsonl  points allowed as the primary defender
#     combine_drills.jsonl   max vertical leap
#     player_onoff.jsonl     possessions and points with each player on and
#                            off the floor, per season and team
#     team_priors.jsonl      final net rating per team, the two seasons before
#                            this one (for the game preview)
#     matchup_top.jsonl.gz   each scorer's top defender in every game, both
#                            seasons, playoffs and play-in included
#   R only pulls and trims. The ratings and badges are computed in Python
#   (app/model/), when the loader runs.
#
# How to run (from the repo root)
#   Rscript pulls/pull_stats.R      (or ./refresh.sh)
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

this_start <- most_recent_nba_stats_season()
make_label <- function(start) sprintf("%d-%02d", start, (start + 1) %% 100)
seasons <- c(this_start - 1, this_start)
seed_dir <- "data/seed"

write_jsonl <- function(df, name, gz = FALSE) {
  path <- file.path(seed_dir, paste0(name, if (gz) ".jsonl.gz" else ".jsonl"))
  con <- if (gz) gzfile(path, open = "w", encoding = "UTF-8") else file(path, open = "w", encoding = "UTF-8")
  stream_out(df, con, na = "null", digits = NA, verbose = FALSE)
  close(con)
  cat(sprintf("  %-24s %7d rows\n", basename(path), nrow(df)))
}

# Regular season only. Last season's tables also hold playoff rows, and the
# play type and hustle files hold every row twice (per game and totals).
regular <- function(df) {
  df %>% filter(tolower(gsub("[^a-z]", "", tolower(season_type))) == "regularseason")
}
totals <- function(df) df %>% filter(tolower(per_mode) == "totals")
dash <- function(start, table) regular(suppressMessages(load_nba_stats_leaguedash(seasons = start, table = table)))

cat("Opponent Scout stats pull,", make_label(this_start), "and", make_label(this_start - 1), "\n\n")

# 1. Base, advanced and tracking stats ---------------------------------------
# One call per table per season. Each table is trimmed to its columns, then
# all are joined on player_id into one row per player per season.
season_stats <- function(start) {
  base <- dash(start, "player_stats_base") %>%
    transmute(player_id = as.integer(player_id), player_name, team_abbr = team_abbreviation,
              gp = as.integer(gp), min, pts, fgm, fga, fg3m = fg3_m, fg3a = fg3_a, ftm, fta,
              oreb, dreb, reb, ast, tov, stl, blk)
  adv <- dash(start, "player_stats_advanced") %>%
    transmute(player_id = as.integer(player_id), ast_pct, ast_to, oreb_pct, dreb_pct, usg_pct)
  drives <- dash(start, "player_tracking_drives") %>%
    transmute(player_id = as.integer(player_id), drives, drive_pts, drive_fgm, drive_fga)
  passing <- dash(start, "player_tracking_passing") %>%
    transmute(player_id = as.integer(player_id), potential_ast)
  reb <- dash(start, "player_tracking_rebounding") %>%
    transmute(player_id = as.integer(player_id), reb_chances, reb_chance_pct)
  cs <- dash(start, "player_tracking_catchshoot") %>%
    transmute(player_id = as.integer(player_id), catch_shoot_fga, catch_shoot_fgm, catch_shoot_fg3m = catch_shoot_fg3_m,
              catch_shoot_efg_pct)
  pu <- dash(start, "player_tracking_pullupshot") %>%
    transmute(player_id = as.integer(player_id), pull_up_fga, pull_up_fgm, pull_up_fg3m = pull_up_fg3_m, pull_up_efg_pct)
  post <- dash(start, "player_tracking_posttouch") %>%
    transmute(player_id = as.integer(player_id), post_touches, post_touch_pts)
  speed <- dash(start, "player_tracking_speeddistance") %>%
    transmute(player_id = as.integer(player_id), dist_miles, avg_speed)
  def <- dash(start, "player_tracking_defense") %>%
    transmute(player_id = as.integer(player_id), def_rim_fgm, def_rim_fga)
  # Reduce(left_join, ...) joins the list of tables one after another.
  Reduce(function(a, b) left_join(a, b, by = "player_id"),
         list(base, adv, drives, passing, reb, cs, pu, post, speed, def)) %>%
    mutate(season = make_label(start), `_id` = paste(player_id, season, sep = "_")) %>%
    relocate(`_id`, season)
}
player_stats <- bind_rows(lapply(seasons, season_stats))

# 2. Play types: post-ups ---------------------------------------------------
# Offensive post-up possessions, totals copy only. A traded player has one
# row per team, so they are summed.
play_types <- bind_rows(lapply(seasons, function(start) {
  regular(totals(suppressMessages(load_nba_stats_synergy(seasons = start)))) %>%
    filter(play_type == "Postup", type_grouping == "Offensive") %>%
    group_by(player_id = as.integer(player_id)) %>%
    summarise(postup_poss = sum(poss), postup_pts = sum(pts), .groups = "drop") %>%
    mutate(season = make_label(start))
})) %>% mutate(`_id` = paste(player_id, season, sep = "_")) %>% relocate(`_id`)

# 2b. Play type mix: every offensive play type ------------------------------
# For the one-pager's "How he gets his shots". One row per player, season and
# play type. A traded player has one row per team, so rows are summed.
# poss_pct is that type's share of his possessions on that team, so
# poss / poss_pct gives his total possessions there; the median over his
# types smooths rounding. Kept apart from play_types.jsonl so the ratings
# inputs do not change.
play_type_mix <- bind_rows(lapply(seasons, function(start) {
  rows <- regular(totals(suppressMessages(load_nba_stats_synergy(seasons = start)))) %>%
    filter(type_grouping == "Offensive") %>%
    mutate(player_id = as.integer(player_id), team_id = as.integer(team_id))
  team_poss <- rows %>%
    filter(poss_pct > 0) %>%
    group_by(player_id, team_id) %>%
    summarise(team_total = median(poss / poss_pct), .groups = "drop") %>%
    group_by(player_id) %>%
    summarise(total_poss = round(sum(team_total)), .groups = "drop")
  rows %>%
    group_by(player_id, play_type) %>%
    summarise(poss = sum(poss), pts = sum(pts), fga = sum(fga), fgm = sum(fgm),
              tov_poss = sum(tov_poss_pct * poss), .groups = "drop") %>%
    left_join(team_poss, by = "player_id") %>%
    mutate(tov_poss = round(tov_poss), season = make_label(start))
})) %>% mutate(`_id` = paste(player_id, season, play_type, sep = "_")) %>% relocate(`_id`)

# 2c. Assist pairs from the play-by-play ------------------------------------
# For "who feeds him". About two in three made shots name the passer, as in
# "Tatum 4' Layup (3 PTS) (Robinson 1 AST)". The passer is written as a last
# name (sometimes with a first initial), so it is matched to the scorer's
# four teammates on the floor (off_player_1 to off_player_5). This season
# only, regular season only (game ids starting 002).
cat("Assist pairs from play-by-play:\n")
pbp <- suppressMessages(load_nba_stats_pbp(seasons = this_start)) %>%
  filter(substr(game_id, 1, 3) == "002", action_type == "Made Shot")
name_of <- player_stats %>% filter(season == make_label(this_start)) %>%
  distinct(player_id, player_name)
# Names are compared without accents ("Jokić" is written "Jokic" in the
# text). The passer text is a last name, a last name without "Jr.", or a
# shortened first name plus last name ("Jal. Williams").
plain <- function(x) gsub("['`^~\"]", "", iconv(x, from = "UTF-8", to = "ASCII//TRANSLIT"))
name_of <- name_of %>% mutate(first = plain(sub("\\s.*$", "", player_name)),
                              last = plain(sub("^\\S+\\s+", "", player_name)))
made <- pbp %>%
  transmute(row = row_number(), scorer_id = as.integer(person_id), shot_value = as.integer(shot_value),
            passer_text = ifelse(grepl("\\([^()]+ [0-9]+ AST\\)", description),
                                 sub(".*\\(([^()]+) [0-9]+ AST\\).*", "\\1", description), NA_character_),
            off_player_1, off_player_2, off_player_3, off_player_4, off_player_5)
assisted <- made %>% filter(!is.na(passer_text))
# One row per assisted shot and teammate on the floor, then keep the
# teammate whose name matches the passer text.
candidates <- bind_rows(lapply(paste0("off_player_", 1:5), function(col) {
  assisted %>% transmute(row, scorer_id, shot_value, passer_text, passer_id = .data[[col]])
})) %>%
  filter(!is.na(passer_id), passer_id != scorer_id) %>%
  mutate(passer_id = as.integer(passer_id), text = plain(passer_text)) %>%
  left_join(name_of, by = c("passer_id" = "player_id")) %>%
  filter(!is.na(last)) %>%
  mutate(
    prefix = ifelse(grepl("^\\S+\\. ", text), sub("\\. .*$", "", text), NA_character_),
    rest = sub("^\\S+\\. ", "", text),
    hit = text == last |
      text == sub("\\s+(Jr\\.?|Sr\\.?|II|III|IV)$", "", last) |
      (!is.na(prefix) & startsWith(first, prefix) &
         (rest == last | rest == sub("\\s+(Jr\\.?|Sr\\.?|II|III|IV)$", "", last))))
matched <- candidates %>% group_by(row) %>% filter(sum(hit) == 1, hit) %>% ungroup()
cat(sprintf("  %d made shots, %d name a passer, %d matched to one teammate on the floor (%.1f%%)\n",
            nrow(made), nrow(assisted), nrow(matched), 100 * nrow(matched) / max(1, nrow(assisted))))
scorer_totals <- made %>% group_by(scorer_id) %>%
  summarise(scorer_fgm = n(), scorer_assisted = sum(!is.na(passer_text)), .groups = "drop")
assist_pairs <- matched %>%
  group_by(scorer_id, passer_id) %>%
  summarise(ast = n(), ast_fg3 = sum(shot_value == 3), .groups = "drop") %>%
  left_join(scorer_totals, by = "scorer_id") %>%
  mutate(season = make_label(this_start), `_id` = paste(season, scorer_id, passer_id, sep = "_")) %>%
  relocate(`_id`, season)

# 3. Hustle -----------------------------------------------------------------
hustle <- bind_rows(lapply(seasons, function(start) {
  regular(totals(suppressMessages(load_nba_stats_hustle_player(seasons = start)))) %>%
    group_by(player_id = as.integer(player_id)) %>%
    summarise(deflections = sum(deflections), contested_3pt = sum(contested_shots_3_pt),
              charges_drawn = sum(charges_drawn), .groups = "drop") %>%
    mutate(season = make_label(start))
})) %>% mutate(`_id` = paste(player_id, season, sep = "_")) %>% relocate(`_id`)

# 4. Steals from ESPN play-by-play -----------------------------------------
# The NBA play-by-play never says who made a steal; ESPN's does. On a
# turnover row, athlete_id_2 is the stealer and the text ends "(Name steals)".
# ESPN functions take the END year of the season, so 2027 means 2026-27.
# season_type 2 is the regular season.
cat("Steals from ESPN play-by-play:\n")
nba_names <- player_stats %>% distinct(player_id, player_name, team_abbr)
steals <- bind_rows(lapply(seasons, function(start) {
  pbp <- suppressMessages(load_nba_pbp(seasons = start + 1))
  st <- pbp %>%
    filter(season_type == 2, grepl("Turnover", type_text), !is.na(athlete_id_2), grepl("steals\\)", text)) %>%
    mutate(
      espn_name = sub(".*\\((.*) steals\\).*", "\\1", text),
      # The row's team turned the ball over, so the stealer is on the other team.
      espn_team = ifelse(team_id == home_team_id, away_team_abbrev, home_team_abbrev),
      lost_ball = grepl("Lost Ball", type_text)
    )
  counts <- st %>%
    group_by(espn_name, espn_team) %>%
    summarise(steals = n(), lost_ball_steals = sum(lost_ball), .groups = "drop")
  matched <- match_espn_players(counts, nba_names, label = sprintf("ESPN stealers %s", make_label(start)))
  matched %>%
    filter(!is.na(nba_player_id)) %>%
    group_by(player_id = as.integer(nba_player_id)) %>%
    summarise(steals = sum(steals), lost_ball_steals = sum(lost_ball_steals), .groups = "drop") %>%
    mutate(other_steals = steals - lost_ball_steals, season = make_label(start))
})) %>% mutate(`_id` = paste(player_id, season, sep = "_")) %>% relocate(`_id`)

# Check one player: ESPN steals against the NBA game logs.
logs <- regular(suppressMessages(load_nba_stats_player_game_logs(seasons = this_start)))
check_id <- logs %>% group_by(player_id) %>% summarise(stl = sum(stl), .groups = "drop") %>%
  arrange(desc(stl)) %>% slice(1)
espn_total <- steals %>% filter(player_id == check_id$player_id, season == make_label(this_start)) %>% pull(steals)
check_name <- logs$player_name[match(check_id$player_id, logs$player_id)]
cat(sprintf("  Steal check, %s this season: ESPN play-by-play %s, NBA game logs %d\n",
            check_name, ifelse(length(espn_total), espn_total, "none"), check_id$stl))

# 5. Shot extras: deep threes, dunks, and the streaky shooter counts --------
# The shot clock reads like "PT11M32.00S". This turns it into seconds left.
clock_seconds <- function(x) {
  mins <- suppressWarnings(as.numeric(sub("^PT([0-9]+)M.*", "\\1", x)))
  secs <- suppressWarnings(as.numeric(sub("^PT[0-9]+M([0-9.]+)S$", "\\1", x)))
  mins * 60 + secs
}
dunk_kind <- function(sub_type) {
  case_when(
    grepl("Alley Oop", sub_type, ignore.case = TRUE) ~ "alley_oop",
    grepl("Putback|Tip", sub_type, ignore.case = TRUE) ~ "putback",
    grepl("Driving", sub_type, ignore.case = TRUE) ~ "driving",
    grepl("Cutting", sub_type, ignore.case = TRUE) ~ "cutting",
    grepl("Running", sub_type, ignore.case = TRUE) ~ "running",
    TRUE ~ "other"
  )
}
shot_extras <- bind_rows(lapply(seasons, function(start) {
  shots <- suppressMessages(load_nba_stats_shots(seasons = start)) %>%
    filter(season_type_id == 2 | is.na(season_type_id)) %>%
    mutate(row = row_number(), made = shot_result == "Made", t = clock_seconds(clock),
           dunk = grepl("Dunk", sub_type, ignore.case = TRUE))
  # Streaky counts: order each player's shots within a game (period, then
  # the clock counting down, then file order), and look at the shot before.
  # lag() gives the previous row's value inside each group.
  seq_counts <- shots %>%
    arrange(game_id, person_id, period, desc(t), row) %>%
    group_by(game_id, person_id) %>%
    mutate(prev = lag(made)) %>%
    ungroup() %>%
    filter(!is.na(prev)) %>%
    group_by(player_id = as.integer(person_id)) %>%
    summarise(after_make_fga = sum(prev), after_make_fgm = sum(prev & made),
              after_miss_fga = sum(!prev), after_miss_fgm = sum(!prev & made), .groups = "drop")
  other <- shots %>%
    group_by(player_id = as.integer(person_id)) %>%
    summarise(
      fg3a = sum(shot_value == 3), fg3m = sum(shot_value == 3 & made),
      deep3_fga = sum(shot_value == 3 & shot_distance >= 28 & shot_distance <= 39),
      deep3_fgm = sum(shot_value == 3 & shot_distance >= 28 & shot_distance <= 39 & made),
      dunks = sum(dunk & made),
      dunks_driving = sum(dunk & made & dunk_kind(sub_type) == "driving"),
      dunks_cutting = sum(dunk & made & dunk_kind(sub_type) == "cutting"),
      dunks_running = sum(dunk & made & dunk_kind(sub_type) == "running"),
      dunks_putback = sum(dunk & made & dunk_kind(sub_type) == "putback"),
      dunks_alley_oop = sum(dunk & made & dunk_kind(sub_type) == "alley_oop"),
      .groups = "drop")
  left_join(other, seq_counts, by = "player_id") %>% mutate(season = make_label(start))
})) %>% mutate(`_id` = paste(player_id, season, sep = "_")) %>% relocate(`_id`)

# 6. Defense as the primary defender ----------------------------------------
# Summed from the per-game matchup files. season_type_id 2 is the regular season.
matchup_defense <- bind_rows(lapply(seasons, function(start) {
  suppressMessages(load_nba_stats_game_matchups(seasons = start)) %>%
    filter(season_type_id == 2) %>%
    group_by(player_id = as.integer(def_person_id)) %>%
    summarise(def_partial_poss = sum(partial_possessions), def_player_pts = sum(player_points), .groups = "drop") %>%
    mutate(season = make_label(start))
})) %>% mutate(`_id` = paste(player_id, season, sep = "_")) %>% relocate(`_id`)

# 6b. Matchup pairs and games ----------------------------------------------
# Totals for every defender and scorer pair per season, for the matchup
# model, plus this season pair by pair and game by game (with the date) for
# validation and "who guarded whom most". Regular season only.
matchup_rows <- bind_rows(lapply(seasons, function(start) {
  suppressMessages(load_nba_stats_game_matchups(seasons = start)) %>%
    filter(season_type_id == 2) %>%
    transmute(game_id, season = make_label(start),
              off_id = as.integer(off_person_id), def_id = as.integer(def_person_id),
              off_team_id = as.integer(off_team_id), def_team_id = as.integer(def_team_id),
              poss = partial_possessions, pts = player_points,
              fga = matchup_field_goals_attempted, fgm = matchup_field_goals_made,
              fg3a = matchup_three_pointers_attempted, fg3m = matchup_three_pointers_made,
              tov = matchup_turnovers, switches = switches_on)
}))
matchup_pairs <- matchup_rows %>%
  group_by(season, off_id, def_id) %>%
  summarise(games = n_distinct(game_id), across(c(poss, pts, fga, fgm, fg3a, fg3m, tov, switches), sum),
            .groups = "drop") %>%
  mutate(`_id` = paste(season, off_id, def_id, sep = "_")) %>%
  relocate(`_id`)
game_dates <- suppressMessages(load_nba_stats_schedule(seasons = this_start)) %>%
  transmute(game_id, game_date = as.character(game_date))
matchup_games <- matchup_rows %>%
  filter(season == make_label(this_start)) %>%
  left_join(game_dates, by = "game_id") %>%
  mutate(`_id` = paste(game_id, off_id, def_id, sep = "_")) %>%
  relocate(`_id`) %>%
  select(-season)

# 6c. Who guarded each scorer most, every game -------------------------------
# For the series history ("who actually guarded whom" in each meeting). One
# row per game and scorer: the defender with the most partial possessions on
# him, what that defender allowed, and the scorer's totals in the game. Both
# seasons and every game type (season_type_id 2 regular season, 4 playoffs,
# 5 play-in, 6 NBA Cup final), unlike matchup_pairs, which the model reads
# and keeps to the regular season. Only the top defender is kept, so the
# file stays small.
name_lookup <- player_stats %>% group_by(player_id) %>% summarise(name = last(player_name), .groups = "drop")
matchup_top <- bind_rows(lapply(seasons, function(start) {
  suppressMessages(load_nba_stats_game_matchups(seasons = start)) %>%
    transmute(game_id, season = make_label(start), season_type_id = as.integer(season_type_id),
              off_id = as.integer(off_person_id), def_id = as.integer(def_person_id),
              off_team_id = as.integer(off_team_id), def_team_id = as.integer(def_team_id),
              poss = partial_possessions, pts = player_points,
              fga = matchup_field_goals_attempted, fgm = matchup_field_goals_made,
              fg3a = matchup_three_pointers_attempted, fg3m = matchup_three_pointers_made)
})) %>%
  group_by(game_id, off_id) %>%
  mutate(scorer_poss = sum(poss), scorer_pts = sum(pts), scorer_fga = sum(fga), scorer_fgm = sum(fgm),
         defenders = n()) %>%
  slice_max(poss, n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  left_join(name_lookup %>% rename(off_name = name), by = c("off_id" = "player_id")) %>%
  left_join(name_lookup %>% rename(def_name = name), by = c("def_id" = "player_id")) %>%
  mutate(`_id` = paste(game_id, off_id, sep = "_")) %>%
  relocate(`_id`)

# 6d. On/off: points and possessions with each player on and off the floor --
# The play-by-play and the game lineups file line up row for row, so every
# row has the ten players on the floor. Regular season only (game ids 002).
#   Points: the running score only appears on scoring rows, so it is carried
#     forward and each change is credited to ten players.
#   Free throws are credited to the ten players on the floor at the foul
#     that caused them (the latest Foul row before them), not when they are
#     shot, because substitutions between free throws are common.
#   Possessions are counted, not estimated: the file numbers every
#     possession (an offensive rebound keeps the number). Each possession
#     belongs to the team on offense and is credited to the ten players on
#     the floor when it ends, by the same rule: if it ends on a free throw,
#     the players at the foul.
#   "Off" counts only games he played, so games he missed do not count.
# Output: one row per player, season and team with possessions and points
# on and off. Python computes the ratings (app/services/onoff.py).
cat("On/off from play-by-play and game lineups:\n")
onoff_season <- function(start) {
  p <- suppressMessages(load_nba_stats_pbp(seasons = start))
  l <- suppressMessages(load_nba_stats_game_lineups(seasons = start))
  if (nrow(p) != nrow(l) || !all(p$game_id == l$game_id & p$action_number == l$action_number)) {
    stop("The play-by-play and game lineups files do not line up row for row for ", make_label(start), call. = FALSE)
  }
  five <- c(paste0("home_player_", 1:5), paste0("away_player_", 1:5))
  d <- bind_cols(p %>% select(game_id, period, action_type, score_home, score_away, possession_number, off_player_1),
                 l %>% select(all_of(five))) %>%
    filter(substr(game_id, 1, 3) == "002") %>%
    group_by(game_id) %>%
    mutate(row = row_number(),
           sh = cummax(coalesce(suppressWarnings(as.numeric(score_home)), 0)),
           sa = cummax(coalesce(suppressWarnings(as.numeric(score_away)), 0)),
           pts_home = sh - lag(sh, default = 0), pts_away = sa - lag(sa, default = 0),
           foul_row = cummax(ifelse(action_type == "Foul", row, 0L)),
           credit = ifelse(action_type == "Free Throw" & foul_row > 0, foul_row, row),
           home_off = off_player_1 == home_player_1 | off_player_1 == home_player_2 | off_player_1 == home_player_3 |
             off_player_1 == home_player_4 | off_player_1 == home_player_5,
           # The ten players credited with this row.
           across(all_of(five), ~ .x[credit], .names = "c_{.col}")) %>%
    ungroup()
  own_key <- do.call(paste, d[five])
  credit_key <- do.call(paste, d[paste0("c_", five)])
  moved <- d$action_type == "Free Throw" & own_key != credit_key
  ft_pts <- sum((d$pts_home + d$pts_away)[d$action_type == "Free Throw"])
  moved_pts <- sum((d$pts_home + d$pts_away)[moved])
  pts_ev <- d %>% filter(pts_home + pts_away > 0) %>%
    transmute(game_id, across(starts_with("c_")), pts_home, pts_away, poss_home = 0L, poss_away = 0L)
  # A possession is credited at its last real play: substitutions, timeouts,
  # replays and period markers listed after the free throws do not count.
  poss_ev <- d %>% filter(!is.na(possession_number),
                          !action_type %in% c("Substitution", "Timeout", "Instant Replay", "period", "")) %>%
    group_by(game_id, possession_number) %>%
    summarise(home_off = first(na.omit(home_off)), across(starts_with("c_"), last), .groups = "drop") %>%
    filter(!is.na(home_off)) %>%
    transmute(game_id, across(starts_with("c_")), pts_home = 0, pts_away = 0,
              poss_home = as.integer(home_off), poss_away = as.integer(!home_off))
  ev <- bind_rows(pts_ev, poss_ev) %>%
    group_by(game_id, across(starts_with("c_"))) %>%
    summarise(across(c(pts_home, pts_away, poss_home, poss_away), sum), .groups = "drop")
  games <- suppressMessages(load_nba_stats_schedule(seasons = start)) %>%
    transmute(game_id, home_team_id = as.integer(home_team_id), away_team_id = as.integer(away_team_id)) %>%
    distinct()
  # Checks: points against the final score, possessions against pace.
  per_game <- ev %>% group_by(game_id) %>%
    summarise(h = sum(pts_home), a = sum(pts_away), ph = sum(poss_home), pa = sum(poss_away), .groups = "drop") %>%
    left_join(d %>% group_by(game_id) %>% summarise(minutes = 48 + 5 * max(0, max(period) - 4), .groups = "drop"),
              by = "game_id")
  side <- function(prefix, for_pts, against, own_poss, opp_poss, team_col) {
    bind_rows(lapply(1:5, function(i) {
      ev %>% transmute(game_id, player_id = as.integer(.data[[paste0("c_", prefix, "_player_", i)]]),
                       pts_for = .data[[for_pts]], pts_against = .data[[against]],
                       poss_off = .data[[own_poss]], poss_def = .data[[opp_poss]], home = prefix == "home")
    }))
  }
  on_game <- bind_rows(side("home", "pts_home", "pts_away", "poss_home", "poss_away"),
                       side("away", "pts_away", "pts_home", "poss_away", "poss_home")) %>%
    group_by(game_id, player_id, home) %>%
    summarise(across(c(pts_for, pts_against, poss_off, poss_def), sum), .groups = "drop")
  team_game <- bind_rows(
    per_game %>% transmute(game_id, home = TRUE, t_for = h, t_against = a, t_off = ph, t_def = pa),
    per_game %>% transmute(game_id, home = FALSE, t_for = a, t_against = h, t_off = pa, t_def = ph))
  out <- on_game %>%
    inner_join(team_game, by = c("game_id", "home")) %>%
    left_join(games, by = "game_id") %>%
    mutate(team_id = ifelse(home, home_team_id, away_team_id)) %>%
    group_by(player_id, team_id) %>%
    summarise(games = n_distinct(game_id),
              on_poss_off = sum(poss_off), on_poss_def = sum(poss_def),
              on_pts_for = sum(pts_for), on_pts_against = sum(pts_against),
              off_poss_off = sum(t_off - poss_off), off_poss_def = sum(t_def - poss_def),
              off_pts_for = sum(t_for - pts_for), off_pts_against = sum(t_against - pts_against), .groups = "drop") %>%
    mutate(season = make_label(start), `_id` = paste(player_id, season, team_id, sep = "_")) %>%
    relocate(`_id`, season)
  list(rows = out, per_game = per_game %>% left_join(games, by = "game_id"),
       ft_pts = ft_pts, moved_pts = moved_pts, moved_rows = sum(moved))
}
onoff_parts <- lapply(seasons, onoff_season)
player_onoff <- bind_rows(lapply(onoff_parts, `[[`, "rows"))
for (i in seq_along(seasons)) {
  part <- onoff_parts[[i]]
  cat(sprintf("  %s: %d games; free throw points moved to the players at the foul: %d of %d (%d free throws)\n",
              make_label(seasons[i]), nrow(part$per_game), part$moved_pts, part$ft_pts, part$moved_rows))
}

# 6e. Team priors for the game preview ---------------------------------------
# Each team's final regular-season net rating for the two seasons before
# this one. The preview blends a team's pre-game net rating with the
# previous season's while few games have been played.
team_priors <- bind_rows(lapply(c(this_start - 2, this_start - 1), function(start) {
  regular(suppressMessages(load_nba_stats_leaguedash(seasons = start, table = "team_stats_advanced"))) %>%
    transmute(team_id = as.integer(team_id), season = make_label(start), gp = as.integer(gp),
              net_rating, off_rating, def_rating)
})) %>% mutate(`_id` = paste(team_id, season, sep = "_")) %>% relocate(`_id`)

# 7. Combine drills: max vertical --------------------------------------------
drills <- bind_rows(lapply(2000:(this_start - 1), function(cl) {
  tryCatch(suppressMessages(load_nba_stats_draft_combine_drills(seasons = cl)), error = function(e) NULL)
})) %>%
  filter(!is.na(max_vertical_leap)) %>%
  group_by(player_id = as.integer(player_id)) %>%
  slice_max(as.integer(substr(as.character(season), 1, 4)), n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  transmute(`_id` = player_id, player_id, max_vertical_in = as.numeric(max_vertical_leap))

# 8. Write ------------------------------------------------------------------
cat("\nWriting seed files to", seed_dir, "\n")
write_jsonl(player_stats, "player_stats")
write_jsonl(play_types, "play_types")
write_jsonl(play_type_mix, "play_type_mix")
write_jsonl(assist_pairs, "assist_pairs")
write_jsonl(hustle, "hustle")
write_jsonl(steals, "steals")
write_jsonl(shot_extras, "shot_extras")
write_jsonl(matchup_defense, "matchup_defense")
write_jsonl(drills, "combine_drills")
write_jsonl(matchup_pairs, "matchup_pairs", gz = TRUE)
write_jsonl(matchup_games, "matchup_games", gz = TRUE)
write_jsonl(matchup_top, "matchup_top", gz = TRUE)
write_jsonl(player_onoff, "player_onoff")
write_jsonl(team_priors, "team_priors")
files <- list.files(seed_dir, full.names = TRUE)
cat(sprintf("Total size of %s: %.2f MB\n", seed_dir, sum(file.size(files)) / 1024^2))
