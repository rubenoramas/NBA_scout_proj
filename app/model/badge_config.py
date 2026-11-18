"""Badge names and wording, in one place so a rename is one edit.

Names and art are our own, not NBA 2K's (see CLAUDE.md).
"""

BADGES = {
    "deep_range": {
        "name": "Deep Range",
        "short": "Deep",
        "meaning": "Takes and makes threes from well behind the line.",
        "rule": "At least 40 threes from 28 to 39 ft, at least 20% of his threes from that far, "
                "and he makes them at or above the league's overall 3P%.",
    },
    "streaky_shooter": {
        "name": "Streaky Shooter",
        "short": "Streaky",
        "meaning": "His make rate after a make is clearly higher than after a miss.",
        "rule": "At least 300 shots that followed another shot in the same game. A one-sided "
                "two-proportion z-test must find his make rate after a make higher than after a "
                "miss, with p below 0.05 divided by the number of players tested (Bonferroni).",
        "caveat": "Research finds the hot hand effect small. Comparing make rates after makes and "
                  "misses within games is biased slightly against finding streakiness (Miller and "
                  "Sanjurjo, 2018), so this test is conservative.",
    },
    "on_ball_pest": {
        "name": "On-Ball Pest",
        "short": "Pest",
        "meaning": "Takes the ball off the dribbler.",
        "rule": "At least 15 lost-ball steals, top 10% of qualified players in lost-ball steals per "
                "36 minutes, and deflections per 36 above the median. Per-36 rates are pulled toward "
                "the league average by 400 minutes.",
    },
    "poster_maker": {
        "name": "Poster Maker",
        "short": "Poster",
        "meaning": "Creates his own dunks on the move.",
        "rule": "Counts driving, running and cutting dunks only (alley-oops and putbacks are left out). "
                "At least 25 of them, and top 10% of qualified players in those dunks per 36 minutes.",
    },
}

# Every badge needs this many minutes over this season and last season.
BADGE_MIN_MINUTES = 500
