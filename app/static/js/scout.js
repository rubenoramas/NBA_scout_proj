// Scouting page. Reads ?us=BOS&them=NYK from the URL, looks up the team
// ids, and shows the matchup band plus the Overview panels.

import {
  MY_TEAM_KEY, SEASON_TYPE_LABEL, badgeTip, chevron, chip, el, injuryTag, pct1, rankText, emptyLine, errorLine, fill, formatDay, getJSON,
  resultChip, seedText, shortStreak, skeletonRows, store, streakClass, tag,
} from "./api.js";
import { newRosterState, renderRoster } from "./roster.js";
import { loadTeams, setScoutNav, setSwitcher } from "./topbar.js";

function boxLink(gameId, label) {
  return el("a", { class: "scout-link", href: `/game/${gameId}`, "aria-label": label }, "Box score", chevron());
}

const band = document.getElementById("band-teams");
const root = document.getElementById("scout");
const params = new URLSearchParams(window.location.search);
const usAbbr = (params.get("us") || "").trim().toUpperCase();
const themAbbr = (params.get("them") || "").trim().toUpperCase();

// Tabs: Overview (no tab parameter) and Players (?tab=players).
const activeTab = params.get("tab") === "players" ? "players" : "overview";
function tabUrl(tab) {
  const q = new URLSearchParams({ us: usAbbr, them: themAbbr });
  if (tab !== "overview") q.set("tab", tab);
  return `/scout?${q}`;
}
for (const tab of ["overview", "players"]) {
  const link = document.getElementById(`tab-${tab}`);
  link.setAttribute("href", tabUrl(tab));
  if (tab === activeTab) link.setAttribute("aria-current", "page");
}
setScoutNav(tabUrl("overview"), { current: true });

function panel(span, title, note, ...body) {
  return el("section", { class: `panel ${span}`, "aria-label": title },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: title }),
      note ? el("span", { class: "panel-note", text: note }) : null),
    body);
}

function showProblem(message, retry) {
  fill(band, el("p", { class: "muted", style: "padding-bottom: 4px", text: "No matchup to show." }));
  fill(root, el("section", { class: "panel span-12" },
    retry ? errorLine(message, retry)
      : el("div", { class: "state-error", role: "alert" },
        el("span", { text: message }),
        el("a", { class: "btn", href: "/", text: "Back to schedule" }))));
}

function showLoading() {
  fill(band, el("div", { class: "band-side" }, skeletonRows(2, [60, 160])));
  if (activeTab === "players") {
    fill(root, panel("span-12", "Roster", null, skeletonRows(10, [180, 30, 30, 40, 40, 40, 40, 50, 50])));
    return;
  }
  fill(root,
    panel("span-5", "Head to head", null, skeletonRows(6, [120, 60, 60])),
    panel("span-7", "Recent results", null, skeletonRows(3, [40, 80, 180, 24, 80])),
    panel("span-12", "Last game standouts", null, skeletonRows(2, [40, 160, 60, 60, 60, 40])));
}

async function load() {
  if (!usAbbr || !themAbbr) {
    showProblem("This link is missing a team. It should look like /scout?us=BOS&them=NYK.");
    return;
  }
  if (usAbbr === themAbbr) {
    showProblem("Pick two different teams to scout.");
    return;
  }
  showLoading();
  try {
    const { teams } = await loadTeams();
    const mine = teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY));
    setSwitcher(mine || null);
    const us = teams.find((t) => t.abbreviation === usAbbr);
    const them = teams.find((t) => t.abbreviation === themAbbr);
    const unknown = [!us && usAbbr, !them && themAbbr].filter(Boolean);
    if (unknown.length) {
      showProblem(`No NBA team uses the abbreviation ${unknown.join(" or ")}.`);
      return;
    }
    document.title = `${us.abbreviation} vs ${them.abbreviation} | Opponent Scout`;
    const query = new URLSearchParams({ us: us.team_id, them: them.team_id });
    const ctx = await getJSON(`/api/games/context?${query}`);
    if (mine && mine.team_id === us.team_id && ctx.us.standing) setSwitcher(mine, ctx.us.standing.record);
    render(ctx);
  } catch (err) {
    showProblem(err.message, load);
  }
}

// ---- Matchup band -----------------------------------------------------

function bandSide(side, label, right) {
  const s = side.standing || {};
  const info = el("div", {},
    el("div", { class: "label", text: label }),
    el("div", { class: "band-name", text: side.team.full_name }),
    el("div", { class: "band-sub" },
      `${s.record || "–"} · ${seedText(s)} · `,
      el("span", { class: `strong ${streakClass(s.streak)}`, text: shortStreak(s.streak) })));
  const abbr = chip(side.team.abbreviation, { xl: true, link: true });
  return el("div", { class: `band-side${right ? " right" : ""}` }, right ? [info, abbr] : [abbr, info]);
}

function renderBand(ctx) {
  const next = ctx.next_meeting;
  let mid;
  if (next) {
    const venue = next.home ? ctx.us.team.abbreviation : ctx.them.team.abbreviation;
    mid = el("div", { class: "band-mid" },
      el("div", { class: "band-date", text: formatDay(next.date, { weekday: "short", month: "short", day: "numeric", year: "numeric" }) }),
      el("div", { class: "muted", style: "margin-top: 2px", text: `at ${venue} · ${SEASON_TYPE_LABEL[next.season_type] || next.season_type}` }));
  } else {
    mid = el("div", { class: "band-mid" },
      el("div", { class: "band-date", text: "No game scheduled" }),
      el("div", { class: "muted", style: "margin-top: 2px", text: `No more meetings in ${ctx.season}` }));
  }
  fill(band, bandSide(ctx.us, "US", false), mid, bandSide(ctx.them, "OPPONENT", true));
}

// ---- Panels -----------------------------------------------------------

function headToHead(ctx) {
  const us = ctx.us.standing || {};
  const them = ctx.them.standing || {};
  const row = (label, a, b, classes = ["", ""]) =>
    el("div", { class: "trow cols-h2h", style: "min-height: 34px" },
      el("span", { class: "muted", text: label }),
      el("span", { class: `num strong ${classes[0]}`, text: a || "–" }),
      el("span", { class: `num strong ${classes[1]}`, text: b || "–" }));
  return panel("span-5", "Head to head", "Season to date",
    el("div", { class: "trow thead cols-h2h short-head" },
      el("span"), el("span", { class: "num", text: ctx.us.team.abbreviation }), el("span", { class: "num", text: ctx.them.team.abbreviation })),
    row("Record", us.record, them.record),
    row("Conference seed", seedText(us, { short: true }), seedText(them, { short: true })),
    row("Streak", shortStreak(us.streak), shortStreak(them.streak), [streakClass(us.streak), streakClass(them.streak)]),
    row("Last 10", us.last_ten, them.last_ten),
    row("Home", us.home_record, them.home_record),
    row("Road", us.road_record, them.road_record));
}

function typeTag(game) {
  if (game.season_type === "playoffs") return [" ", tag("Playoffs", "accent")];
  if (game.season_type === "play-in") return [" ", tag("Play-in", "accent")];
  if (game.season_type === "nba-cup") return [" ", tag("NBA Cup", "gold")];
  return null;
}

// One team's last game, from that team's point of view.
function lastGameRow(side) {
  const g = side.last_game;
  if (!g) {
    return el("div", { class: "trow cols-recent tall" },
      el("span", { class: "bold", text: side.team.abbreviation }),
      el("span", { class: "muted", text: "–" }),
      el("span", { class: "muted", text: "No games played yet this season" }),
      el("span"), el("span"), el("span"));
  }
  return el("div", { class: "trow cols-recent tall" },
    el("span", {}, chip(side.team.abbreviation, { link: true })),
    el("span", { class: "text-2", text: formatDay(g.date) }),
    el("span", { class: "text-2" }, `${g.home ? "vs" : "at"} `, chip(g.opponent.abbreviation, { link: true }), " · last game", typeTag(g)),
    el("span", {}, resultChip(g.result)),
    el("span", { class: "num strong", text: `${g.team_pts}-${g.opp_pts}` }),
    boxLink(g.game_id, `Box score, ${side.team.abbreviation} last game`));
}

// The last meeting between the two. Result is from our point of view; the
// score names the winner first.
function seriesRow(ctx, m) {
  const usT = ctx.us.team.abbreviation;
  const themT = ctx.them.team.abbreviation;
  const venue = m.home ? usT : themT;
  const winner = m.result === "W" ? usT : themT;
  const hi = Math.max(m.team_pts, m.opp_pts);
  const lo = Math.min(m.team_pts, m.opp_pts);
  const seasonNote = m.season === ctx.season ? "last meeting" : `last meeting, ${m.season}`;
  return el("div", { class: "trow cols-recent tall highlight" },
    el("span", { class: "bold", text: "Series" }),
    el("span", { class: "text-2", text: formatDay(m.date, { month: "short", day: "numeric", year: "numeric" }) }),
    el("span", { class: "text-2" }, `at ${venue} · ${seasonNote}`, typeTag(m)),
    el("span", {}, resultChip(m.result)),
    el("span", { class: "num strong", text: `${winner} ${hi}-${lo}` }),
    boxLink(m.game_id, "Box score, last meeting"));
}

function recentResults(ctx) {
  const rows = [lastGameRow(ctx.us), lastGameRow(ctx.them)];
  const m = ctx.last_meeting;
  let foot = null;
  if (m) {
    rows.push(seriesRow(ctx, m));
    if (m.season !== ctx.season) {
      foot = ctx.next_meeting
        ? `This game is the first meeting of the ${ctx.season} season.`
        : `They have not met in the ${ctx.season} season.`;
    }
  } else {
    foot = "These teams have not met this season or last.";
  }
  return panel("span-7", "Recent results", "Last game and series",
    el("div", { class: "trow thead cols-recent short-head" },
      el("span", { text: "Team" }), el("span", { text: "Date" }), el("span", { text: "Game" }),
      el("span", { text: "Res" }), el("span", { class: "num", text: "Score" }), el("span")),
    rows,
    foot ? el("div", { class: "panel-foot", text: foot }) : null);
}

function standouts(ctx) {
  const rule = ctx.standout_rule;
  const jumps = rule.rules.map((r) => `${r.min_jump} ${r.label}`).join(", ");
  const note = `Rule: at least ${jumps} more than his average, and ${rule.min_ratio} times it. `
    + `${rule.min_avg_minutes}+ minutes a game, ${rule.min_last_game_minutes}+ in the last game.`;
  const sides = [ctx.us, ctx.them].filter((s) => s.standout);
  const header = el("div", { class: "trow thead cols-standouts short-head" },
    ["Team", "Player", "Stat"].map((t) => el("span", { text: t })),
    ["Last game", "Season avg", "Min", "Games", "Jump", "Sample"].map((t) => el("span", { class: "num", text: t })));
  const rows = sides.map((side) => {
    const s = side.standout;
    const jump = s.value - s.average;
    const small = s.earlier_games < 10;
    return el("div", { class: "trow cols-standouts tall" },
      el("span", { class: "bold", text: side.team.abbreviation }),
      el("span", { class: "strong", text: s.player_name }),
      el("span", { class: "text-2", text: s.stat_label.charAt(0).toUpperCase() + s.stat_label.slice(1) }),
      el("span", { class: "num bold", style: "color: var(--gold)", text: s.value }),
      el("span", { class: "num text-2", text: s.average.toFixed(1) }),
      el("span", { class: "num text-2", text: s.minutes ?? "–" }),
      el("span", { class: "num text-2", text: s.earlier_games }),
      el("span", { class: "num strong", text: `+${jump.toFixed(1)}` }),
      el("span", { class: "num" }, small ? tag("Small sample", "gold") : el("span", { class: "muted", text: "OK" })));
  });
  return el("section", { class: "panel span-12", "aria-label": "Last game standouts" },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: "Last game standouts" }),
      el("span", { class: "panel-note", text: note })),
    rows.length
      ? el("div", { class: "table-scroll" }, el("div", { class: "minw-820" }, header, rows))
      : emptyLine("Neither team had a standout in its last game."));
}

function render(ctx) {
  renderBand(ctx);
  if (activeTab === "players") {
    renderPlayers(ctx);
    return;
  }
  const usagePanel = el("section", { class: "panel span-12", "aria-label": "Who runs the offense" },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: "Who runs the offense" }),
      el("span", { class: "panel-note", text: "Top three by USG% this season (100+ minutes)" })),
    el("div", { id: "usage-body" }, skeletonRows(3, [40, 160, 50, 50, 50])));
  fill(root, headToHead(ctx), recentResults(ctx), usagePanel, standouts(ctx));
  loadUsage(ctx);
}

async function loadUsage(ctx) {
  const body = document.getElementById("usage-body");
  if (!body) return;
  fill(body, skeletonRows(3, [40, 160, 50, 50, 50]));
  let rosters;
  try {
    rosters = await Promise.all([ctx.us, ctx.them].map((side) => getJSON(`/api/teams/${side.team.team_id}/roster`)));
  } catch (err) {
    fill(body, errorLine(err.message, () => loadUsage(ctx)));
    return;
  }
  const columns = [ctx.us, ctx.them].map((side, i) => {
    const top = rosters[i].players
      .filter((p) => p.usage && p.usage.usg_pct !== null && !p.usage.small_sample && p.season)
      .sort((a, b) => b.usage.usg_pct - a.usage.usg_pct)
      .slice(0, 3);
    return el("div", { class: "usage-team" },
      el("div", { class: "trow thead short-head cols-usage" },
        el("span", { text: side.team.abbreviation }),
        ["USG%", "Rank", "PTS", "TS%"].map((t) => el("span", { class: "num", text: t }))),
      top.length ? top.map((p) => el("div", { class: "trow cols-usage" },
        el("a", { class: "name-link", href: `/player/${p.player_id}`, text: p.player_name }),
        el("span", { class: "num strong", text: p.usage.usg_pct.toFixed(1) }),
        el("span", { class: "num text-2", text: rankText(p.usage.rank) || "–" }),
        el("span", { class: "num text-2", text: p.season.pts.toFixed(1) }),
        el("span", { class: "num text-2", text: pct1(p.season.ts_pct) })))
        : emptyLine("No player has 100 minutes yet."));
  });
  fill(body, el("div", { class: "usage-grid" }, columns));
}

// ---- Players tab: the opponent's roster ------------------------------

const rosterState = newRosterState();
async function renderPlayers(ctx) {
  const them = ctx.them.team;
  const body = el("div");
  fill(root, panel("span-12", `${them.full_name} roster`, `${ctx.season} · per game · sorted by USG% · click a name for the player card`, body));
  fill(body, skeletonRows(10, [180, 30, 30, 40, 40, 40, 40, 50, 50]));
  let data;
  try {
    data = await getJSON(`/api/teams/${them.team_id}/roster`);
  } catch (err) {
    fill(body, errorLine(err.message, () => renderPlayers(ctx)));
    return;
  }
  renderRoster(body, data.players, rosterState, `${them.full_name} roster`);
}

load();
