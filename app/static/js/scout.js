// Scouting page. Reads ?us=BOS&them=NYK from the URL, looks up the team
// ids, and shows the game context header.

import { badge, el, errorBox, formatDay, getJSON, showAsOf, skeleton } from "./api.js";

const root = document.getElementById("scout");
const params = new URLSearchParams(window.location.search);
const usAbbr = (params.get("us") || "").trim().toUpperCase();
const themAbbr = (params.get("them") || "").trim().toUpperCase();

function invalid(message) {
  root.replaceChildren(
    el("div", { class: "state state-error", role: "alert" },
      el("p", { text: message }),
      el("a", { class: "btn", href: "/", text: "Pick a game" })));
}

async function load() {
  if (!usAbbr || !themAbbr) {
    invalid("This link is missing a team. It should look like /scout?us=BOS&them=NYK.");
    return;
  }
  if (usAbbr === themAbbr) {
    invalid("Pick two different teams to scout.");
    return;
  }
  root.replaceChildren(skeleton(6, "Loading the scouting report"));
  try {
    const { teams } = await getJSON("/api/teams");
    const us = teams.find((t) => t.abbreviation === usAbbr);
    const them = teams.find((t) => t.abbreviation === themAbbr);
    const unknown = [!us && usAbbr, !them && themAbbr].filter(Boolean);
    if (unknown.length) {
      invalid(`No NBA team uses the abbreviation ${unknown.join(" or ")}.`);
      return;
    }
    document.title = `${us.abbreviation} vs ${them.abbreviation} | Opponent Scout`;
    const query = new URLSearchParams({ us: us.team_id, them: them.team_id });
    const ctx = await getJSON(`/api/games/context?${query}`);
    showAsOf(ctx.data_as_of);
    render(ctx);
  } catch (err) {
    root.replaceChildren(errorBox(err.message, load));
  }
}

// ---- Rendering --------------------------------------------------------

function streakClass(streak) {
  if (!streak) return "";
  return streak.startsWith("W") ? "pos" : streak.startsWith("L") ? "neg" : "";
}

function ordinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function stat(label, value, extraClass = "") {
  return el("div", { class: "stat" },
    el("span", { class: "stat-label", text: label }),
    el("span", { class: `stat-value ${extraClass}`, text: value ?? "-" }));
}

function gameLine(game) {
  if (!game) return el("p", { class: "muted", text: "No games played yet this season." });
  const win = game.result === "W";
  return el("div", { class: "game-line" },
    el("span", { class: `result-pill ${win ? "pos" : "neg"}`, text: game.result }),
    el("span", { class: "game-line-score", text: `${game.team_pts}-${game.opp_pts}` }),
    el("span", { class: "muted", text: game.home ? "vs" : "at" }),
    badge(game.opponent.abbreviation, { size: "sm" }),
    el("span", { class: "muted game-line-date", text: formatDay(game.date) }));
}

function standoutCard(standout, ctx) {
  if (!standout) {
    return el("div", { class: "standout none" },
      el("span", { class: "standout-kicker", text: "Last game standout" }),
      el("p", { class: "muted", text: "No one beat his season average by enough in the last game." }));
  }
  const rule = ctx.standout_rule.rules.find((r) => r.stat === standout.stat);
  const small = standout.earlier_games < 10;
  return el("div", { class: "standout" },
    el("span", { class: "standout-kicker", text: "Last game standout" }),
    el("div", { class: "standout-main" },
      el("span", { class: "standout-name", text: standout.player_name }),
      el("span", { class: "standout-value" },
        el("strong", { text: standout.value }), ` ${standout.stat_label}`)),
    el("p", { class: "standout-detail" },
      `Season average ${standout.average} over ${standout.earlier_games} earlier games. ${standout.minutes} minutes, against ${standout.avg_minutes} a game.`,
      small ? el("span", { class: "tag tag-small", text: "Small sample" }) : null),
    el("p", { class: "standout-rule muted",
      text: `Rule: at least ${rule.min_jump} more ${rule.label} than his average and ${ctx.standout_rule.min_ratio} times it, `
        + `averaging ${ctx.standout_rule.min_avg_minutes}+ minutes and playing ${ctx.standout_rule.min_last_game_minutes}+ in the last game.` }));
}

function teamPanel(side, label, ctx) {
  const { team, standing, last_game: lastGame, standout } = side;
  const s = standing || {};
  return el("section", { class: "team-panel" },
    el("div", { class: "team-panel-head" },
      badge(team.abbreviation, { conference: team.conference, size: "xl" }),
      el("div", {},
        el("span", { class: "eyebrow", text: label }),
        el("h2", { class: "team-panel-name", text: team.full_name }),
        el("span", { class: "muted", text: s.seed ? `${ordinal(s.seed)} in the ${s.conference}` : team.conference }))),
    el("div", { class: "stat-row" },
      stat("Record", s.record),
      stat("Streak", s.streak, streakClass(s.streak)),
      stat("Last 10", s.last_ten),
      stat("Home", s.home_record),
      stat("Road", s.road_record)),
    el("div", { class: "block" },
      el("span", { class: "block-title", text: "Last game" }),
      gameLine(lastGame)),
    standoutCard(standout, ctx));
}

function meetingCard(title, game, us, them, upcoming) {
  if (!game) {
    return el("div", { class: "meeting" },
      el("span", { class: "block-title", text: title }),
      el("p", { class: "muted", text: upcoming ? "No more meetings this season." : "These teams have not met this season or last." }));
  }
  const tags = [];
  if (game.season_type === "playoffs") tags.push(el("span", { class: "tag tag-playoffs", text: "Playoffs" }));
  if (game.season_type === "play-in") tags.push(el("span", { class: "tag tag-playoffs", text: "Play-in" }));
  if (game.season_type === "nba-cup") tags.push(el("span", { class: "tag tag-cup", text: "NBA Cup" }));
  const where = game.home ? `at ${us.abbreviation}` : `at ${them.abbreviation}`;
  const dateText = formatDay(game.date, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  let body;
  if (upcoming) {
    body = el("p", { class: "meeting-main" }, el("strong", { text: dateText }), el("span", { class: "muted", text: ` ${where}` }));
  } else {
    const win = game.result === "W";
    body = el("div", {},
      el("p", { class: "meeting-main" },
        el("span", { class: `result-pill ${win ? "pos" : "neg"}`, text: `${us.abbreviation} ${win ? "won" : "lost"}` }),
        el("strong", { class: "meeting-score", text: ` ${game.team_pts}-${game.opp_pts}` })),
      el("p", { class: "muted", text: `${dateText}, ${where}, ${game.season} season` }));
  }
  return el("div", { class: "meeting" },
    el("div", { class: "meeting-head" }, el("span", { class: "block-title", text: title }), tags),
    body);
}

function render(ctx) {
  const us = ctx.us.team;
  const them = ctx.them.team;
  const header = el("header", { class: "matchup-head" },
    el("div", { class: "matchup-teams" },
      badge(us.abbreviation, { conference: us.conference, size: "lg" }),
      el("span", { class: "matchup-vs", text: "vs" }),
      badge(them.abbreviation, { conference: them.conference, size: "lg" })),
    el("div", {},
      el("p", { class: "eyebrow", text: "Game context" }),
      el("h1", { class: "matchup-title", text: `${us.name} scouting the ${them.name}` })));

  const middle = el("div", { class: "meetings" },
    meetingCard("Next meeting", ctx.next_meeting, us, them, true),
    meetingCard("Last meeting", ctx.last_meeting, us, them, false));

  root.replaceChildren(
    header,
    middle,
    el("div", { class: "panels" },
      teamPanel(ctx.us, "Us", ctx),
      teamPanel(ctx.them, "Opponent", ctx)),
    el("p", { class: "muted asof-note", text: `Data as of ${formatDay(ctx.data_as_of, { month: "long", day: "numeric", year: "numeric" })}. Records and streaks change daily.` }));
}

load();
