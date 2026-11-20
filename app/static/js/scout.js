// Scouting page. Reads ?us=BOS&them=NYK from the URL, looks up the team
// ids, and shows the matchup band plus the Overview panels.

import {
  MY_TEAM_KEY, SEASON_TYPE_LABEL, badgeTip, chevron, chip, el, injuryTag, pct1, postJSON, rankText, sendJSON, emptyLine, errorLine, fill, formatDay, getJSON,
  resultChip, seedText, shortStreak, skeletonRows, store, streakClass, tag,
} from "./api.js";
import { aiLoading, aiSections, factsPanel, modelLine } from "./aireport.js";
import { lineupLine, matchupNotes, matchupTable } from "./matchtable.js";
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

// Tabs switch in place, without a page reload, so the lineups and status
// changes made in the Lineups tab carry over to Matchups and Report. The
// address still changes (?tab=...), so a refresh or bookmark lands on the
// same tab.
const TABS = ["overview", "players", "matchups", "lineups", "report"];
let activeTab = TABS.includes(params.get("tab")) ? params.get("tab") : "overview";
let currentCtx = null;
function tabUrl(tab) {
  const q = new URLSearchParams({ us: usAbbr, them: themAbbr });
  if (tab !== "overview") q.set("tab", tab);
  return `/scout?${q}`;
}
function markTabs() {
  for (const tab of TABS) {
    const link = document.getElementById(`tab-${tab}`);
    link.setAttribute("href", tabUrl(tab));
    if (tab === activeTab) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}
markTabs();
for (const tab of TABS) {
  document.getElementById(`tab-${tab}`).addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || !currentCtx) return; // new tab or not loaded yet
    event.preventDefault();
    if (tab === activeTab) return;
    activeTab = tab;
    window.history.pushState({ tab }, "", tabUrl(tab));
    markTabs();
    render(currentCtx);
  });
}
window.addEventListener("popstate", () => {
  const tab = new URLSearchParams(window.location.search).get("tab");
  activeTab = TABS.includes(tab) ? tab : "overview";
  markTabs();
  if (currentCtx) render(currentCtx);
});
setScoutNav(tabUrl("overview"), { current: true });

// "Generate report" in the band: switch to the Report tab and start a draft.
const generateButton = document.getElementById("generate-report");
const NO_KEY_TEXT = "AI reports need an API key. Add ANTHROPIC_API_KEY to the .env file and restart the app. Everything else works without it.";
getJSON("/api/health").then((h) => {
  editor.ai.keySet = Boolean(h.ai_key_set);
  generateButton.disabled = false;
  if (!editor.ai.keySet) generateButton.title = NO_KEY_TEXT;
  if (currentCtx && activeTab === "report") render(currentCtx);
}).catch(() => { editor.ai.keySet = null; generateButton.disabled = false; });
generateButton.addEventListener("click", () => {
  if (!currentCtx) return;
  if (activeTab !== "report") {
    activeTab = "report";
    window.history.pushState({ tab: "report" }, "", tabUrl("report"));
    markTabs();
  }
  if (editor.ai.keySet === false) { render(currentCtx); return; }
  if (editor.ai.state !== "loading" && editor.ai.state !== "ready") generateDraft(currentCtx);
  else render(currentCtx);
});

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
  if (activeTab !== "overview") {
    const titles = { players: "Roster", matchups: "Suggested matchups", lineups: "Lineups", report: "Report" };
    fill(root, panel("span-12", titles[activeTab], null, skeletonRows(10, [180, 30, 30, 40, 40, 40, 40, 50, 50])));
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
  currentCtx = ctx;
  renderBand(ctx);
  if (activeTab === "players") {
    renderPlayers(ctx);
    return;
  }
  if (activeTab === "matchups") {
    renderMatchups(ctx);
    return;
  }
  if (activeTab === "lineups") {
    renderLineups(ctx);
    return;
  }
  if (activeTab === "report") {
    renderReport(ctx);
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




// ---- Lineup editor state (shared by Lineups, Matchups and Report) ---------

const STATUSES = ["Available", "Probable", "Questionable", "Doubtful", "Out"];
const editor = {
  us: { ids: null, overrides: {}, loaded: null },
  them: { ids: null, overrides: {}, loaded: null },
  result: null,     // the latest matchup answer
  error: null,      // the latest error message, if the request failed
  loading: false,
  version: 0,       // ignore answers that arrive after a newer request
  draft: { title: null, notes: "" },
  // AI report: state is idle, loading, ready or error.
  ai: { state: "idle", draft: null, error: null, facts: null, keySet: null, request: 0 },
};
const rosters = {}; // team_id -> roster players (with the official injury status)

function sideTeam(ctx, side) {
  return side === "us" ? ctx.us.team : ctx.them.team;
}

function officialStatus(teamId, pid) {
  const p = (rosters[teamId] || []).find((x) => x.player_id === pid);
  return (p && p.injury && p.injury.status) || "Available";
}

function statusOf(ctx, side, pid) {
  return editor[side].overrides[pid] || officialStatus(sideTeam(ctx, side).team_id, pid);
}

function playerName(teamId, pid) {
  const p = (rosters[teamId] || []).find((x) => x.player_id === pid);
  return p ? p.player_name : `Player ${pid}`;
}

function overridesPayload(side) {
  return Object.entries(editor[side].overrides).map(([pid, status]) => ({ player_id: Number(pid), status }));
}

// Browser-side check, the same rules as the API: five players, no
// duplicates, nobody Out.
function lineupProblem(ctx, side) {
  const ids = editor[side].ids;
  const abbr = sideTeam(ctx, side).abbreviation;
  if (!ids) return null;
  if (ids.length !== 5) return `${abbr}: pick exactly five players (${ids.length} picked).`;
  if (new Set(ids).size !== 5) return `${abbr}: a player is listed twice.`;
  const out = ids.find((pid) => statusOf(ctx, side, pid) === "Out");
  if (out) return `${abbr}: ${playerName(sideTeam(ctx, side).team_id, out)} is Out. Change his status or take him out of the lineup.`;
  return null;
}

async function fetchMatchups(ctx) {
  const version = ++editor.version;
  editor.loading = true;
  refreshMatchupViews(ctx);
  const payload = {
    us: ctx.us.team.team_id, them: ctx.them.team.team_id,
    us_overrides: overridesPayload("us"), them_overrides: overridesPayload("them"),
  };
  if (editor.us.ids) payload.us_lineup = editor.us.ids;
  if (editor.them.ids) payload.them_lineup = editor.them.ids;
  try {
    const data = await postJSON("/api/matchups", payload);
    if (version !== editor.version) return;
    editor.result = data;
    editor.error = null;
    // The first answer fills the editor with the default lineups.
    if (!editor.us.ids) editor.us.ids = data.us_lineup.map((p) => p.player_id);
    if (!editor.them.ids) editor.them.ids = data.them_lineup.map((p) => p.player_id);
  } catch (err) {
    if (version !== editor.version) return;
    editor.error = err.message;
  }
  editor.loading = false;
  refreshMatchupViews(ctx);
}

// Every change waits 300 ms after the last click, then recomputes once.
let matchupTimer = null;
function scheduleMatchups(ctx) {
  clearTimeout(matchupTimer);
  if (lineupProblem(ctx, "us") || lineupProblem(ctx, "them")) {
    editor.version += 1; // drop any answer still on its way
    editor.loading = false;
    refreshMatchupViews(ctx);
    return;
  }
  editor.loading = true;
  refreshMatchupViews(ctx);
  matchupTimer = setTimeout(() => fetchMatchups(ctx), 300);
}

// Draw the matchup result into every matchup box on the current tab.
function refreshMatchupViews(ctx) {
  for (const box of document.querySelectorAll("[data-matchup-box]")) drawMatchupBox(box, ctx);
}

function drawMatchupBox(box, ctx) {
  const problem = lineupProblem(ctx, "us") || lineupProblem(ctx, "them");
  if (problem) {
    fill(box, el("p", { class: "state-error", role: "alert", text: `${problem} Matchups update once both lineups are valid.` }));
    return;
  }
  if (editor.error && !editor.loading) {
    fill(box, errorLine(editor.error, () => fetchMatchups(ctx)));
    return;
  }
  if (!editor.result) {
    fill(box, skeletonRows(6, [180, 50, 160, 200, 60, 60]));
    return;
  }
  const data = editor.result;
  fill(box,
    editor.loading ? el("p", { class: "recompute", role: "status", text: "Recomputing matchups..." }) : null,
    el("div", { class: editor.loading ? "is-stale" : "" },
      lineupLine(data, ctx.us.team.abbreviation, ctx.them.team.abbreviation),
      matchupTable(data),
      box.dataset.matchupBox === "full" ? matchupNotes(data) : null));
}

// ---- Matchups tab -------------------------------------------------------

function renderMatchups(ctx) {
  const box = el("div", { "data-matchup-box": "full" });
  fill(root, el("section", { class: "panel span-12", "aria-label": "Suggested matchups" },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: "Suggested matchups" }),
      el("span", { class: "panel-note", text: "Our five against their five, sorted by their USG%. Change the lineups in the Lineups tab." })),
    box));
  drawMatchupBox(box, ctx);
  if (!editor.result && !editor.loading) fetchMatchups(ctx);
}

// ---- Lineups tab --------------------------------------------------------

async function loadRoster(teamId) {
  if (!rosters[teamId]) rosters[teamId] = (await getJSON(`/api/teams/${teamId}/roster`)).players;
  return rosters[teamId];
}

async function renderLineups(ctx) {
  const usBox = el("div");
  const themBox = el("div");
  const live = el("div", { "data-matchup-box": "live" });
  const sidePanel = (side, box) => el("section", { class: "panel span-6", "aria-label": `${sideTeam(ctx, side).abbreviation} lineup` },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: `${side === "us" ? "Us" : "Them"}: ${sideTeam(ctx, side).full_name}` }),
      el("span", { class: "panel-note", id: `count-${side}` })),
    box);
  fill(root, sidePanel("us", usBox), sidePanel("them", themBox),
    el("section", { class: "panel span-12", "aria-label": "Matchups for these lineups" },
      el("div", { class: "panel-head", style: "justify-content: space-between" },
        el("h2", { class: "panel-title", text: "Matchups for these lineups" }),
        el("span", { class: "panel-note", text: "Updates on every change" })),
      live));
  fill(usBox, skeletonRows(8, [60, 180, 40, 40, 120]));
  fill(themBox, skeletonRows(8, [60, 180, 40, 40, 120]));
  drawMatchupBox(live, ctx);
  try {
    await Promise.all([loadRoster(ctx.us.team.team_id), loadRoster(ctx.them.team.team_id)]);
    if (!editor.result) await fetchMatchups(ctx);
  } catch (err) {
    fill(usBox, errorLine(err.message, () => renderLineups(ctx)));
    fill(themBox, emptyLine("Waiting for the rosters."));
    return;
  }
  if (activeTab !== "lineups") return;
  drawSide(ctx, "us", usBox);
  drawSide(ctx, "them", themBox);
  refreshMatchupViews(ctx);
}

function drawSide(ctx, side, box) {
  const team = sideTeam(ctx, side);
  const state = editor[side];
  const ids = state.ids || [];
  const message = el("p", { class: "side-message", role: "status", id: `msg-${side}` });
  // Messages look the element up by id, because a redraw replaces it.
  const say = (text, isError = false) => {
    const node = document.getElementById(`msg-${side}`) || message;
    node.textContent = text;
    node.className = `side-message ${isError ? "loss" : "muted"}`;
  };
  const count = document.getElementById(`count-${side}`);
  if (count) count.textContent = `${ids.length} of 5 selected`;

  const redraw = () => {
    drawSide(ctx, side, box);
    scheduleMatchups(ctx);
  };

  // Roster table: select button, player, minutes, USG%, official and chosen status.
  const players = [...(rosters[team.team_id] || [])].sort((a, b) =>
    (b.season ? b.season.min : -1) - (a.season ? a.season.min : -1));
  const rows = players.map((p) => {
    const pid = p.player_id;
    const inLineup = ids.includes(pid);
    const status = statusOf(ctx, side, pid);
    const official = officialStatus(team.team_id, pid);
    const isOut = status === "Out";
    const toggle = el("button", {
      type: "button", class: `btn toggle-btn${inLineup ? " on" : ""}`, "aria-pressed": String(inLineup),
      disabled: isOut && !inLineup,
      title: isOut && !inLineup ? "Out: change his status to pick him" : null,
      "aria-label": `${inLineup ? "Remove" : "Add"} ${p.player_name}`,
      onclick: () => {
        if (inLineup) state.ids = ids.filter((x) => x !== pid);
        else if (ids.length >= 5) { say("Five players are already picked. Remove one first.", true); return; }
        else state.ids = [...ids, pid];
        redraw();
      },
    }, inLineup ? "In" : "Add");
    const select = el("select", { class: "select select-sm", "aria-label": `Status for ${p.player_name}` },
      STATUSES.map((st) => el("option", { value: st, text: st, selected: st === status })));
    select.addEventListener("change", () => {
      if (select.value === official) delete state.overrides[pid];
      else state.overrides[pid] = select.value;
      redraw();
    });
    const tags = [];
    if (state.overrides[pid]) tags.push(tag("Changed", "accent"));
    if (inLineup && status === "Doubtful") tags.push(tag("Doubtful", "gold"));
    if (inLineup && isOut) tags.push(tag("Out", "loss"));
    return el("div", { class: `trow cols-lineup${inLineup ? " highlight" : ""}` },
      el("span", {}, toggle),
      el("span", { class: "player-cell" }, el("a", { class: "name-link", href: `/player/${pid}`, text: p.player_name }),
        p.position ? el("span", { class: "muted", text: p.position }) : null),
      el("span", { class: "num text-2", text: p.season ? p.season.min.toFixed(1) : "–" }),
      el("span", { class: "num text-2", text: p.usage && p.usage.usg_pct !== null ? p.usage.usg_pct.toFixed(1) : "–" }),
      el("span", { class: "text-2", text: official }),
      el("span", {}, select),
      el("span", { class: "tag-cell" }, tags));
  });

  const problem = lineupProblem(ctx, side);
  fill(box,
    savedBar(ctx, side, say, redraw),
    message,
    problem ? el("p", { class: "state-error", role: "alert", text: problem }) : null,
    el("div", { class: "table-scroll" }, el("div", { style: "min-width: 620px" },
      el("div", { class: "trow thead short-head cols-lineup" },
        el("span", { text: "Lineup" }), el("span", { text: "Player" }), el("span", { class: "num", text: "MIN" }),
        el("span", { class: "num", text: "USG%" }), el("span", { text: "Official" }), el("span", { text: "Status for this game" }),
        el("span")),
      rows)),
    el("p", { class: "panel-foot", text: "Official is the latest NBA injury report. Change a status for this game only; Out players cannot be picked, and a Doubtful pick gets a warning." }));
}

// Saved lineups for one side: load, save as new, save changes, rename, delete.
function savedBar(ctx, side, say, redraw) {
  const team = sideTeam(ctx, side);
  const state = editor[side];
  const select = el("select", { class: "select", "aria-label": `Saved ${team.abbreviation} lineups` },
    el("option", { value: "", text: "Loading saved lineups..." }));
  const name = el("input", { class: "input", type: "text", maxlength: "60", placeholder: "Lineup name",
    "aria-label": "Lineup name", value: state.loaded ? state.loaded.name : "" });
  const confirmRow = el("div", { class: "confirm-row", hidden: true });
  const busy = (button, text) => { button.disabled = true; button.textContent = text; };

  getJSON(`/api/lineups?team=${team.team_id}`).then((data) => {
    fill(select,
      el("option", { value: "", text: data.lineups.length ? "Choose a saved lineup" : "No saved lineups yet" }),
      data.lineups.map((l) => el("option", { value: l.id, text: l.name, selected: state.loaded && state.loaded.id === l.id })));
  }).catch((err) => {
    fill(select, el("option", { value: "", text: "Saved lineups could not load" }));
    say(err.message, true);
  });

  const load = el("button", { type: "button", class: "btn", text: "Load" });
  load.addEventListener("click", async () => {
    if (!select.value) { say("Choose a saved lineup first.", true); return; }
    busy(load, "Loading...");
    try {
      const l = await getJSON(`/api/lineups/${select.value}`);
      state.ids = l.player_ids;
      state.overrides = Object.fromEntries(l.overrides.map((o) => [o.player_id, o.status]));
      state.loaded = { id: l.id, name: l.name };
      redraw();
    } catch (err) {
      say(err.message, true);
      load.disabled = false; load.textContent = "Load";
    }
  });

  const body = () => ({ team_id: team.team_id, name: name.value, player_ids: state.ids, overrides: overridesPayload(side) });
  const checkFirst = () => {
    const problem = lineupProblem(ctx, side);
    if (problem) { say(problem, true); return false; }
    if (!name.value.trim()) { say("Give the lineup a name.", true); name.focus(); return false; }
    return true;
  };

  const saveNew = el("button", { type: "button", class: "btn", text: "Save as new" });
  saveNew.addEventListener("click", async () => {
    if (!checkFirst()) return;
    busy(saveNew, "Saving...");
    try {
      const l = await postJSON("/api/lineups", body());
      state.loaded = { id: l.id, name: l.name };
      redraw();
      say(`Saved "${l.name}".`);
    } catch (err) {
      say(err.message, true);
      saveNew.disabled = false; saveNew.textContent = "Save as new";
    }
  });

  const update = el("button", { type: "button", class: "btn", text: "Save changes", disabled: !state.loaded });
  update.addEventListener("click", async () => {
    if (!checkFirst()) return;
    busy(update, "Saving...");
    try {
      const l = await sendJSON("PUT", `/api/lineups/${state.loaded.id}`, body());
      state.loaded = { id: l.id, name: l.name };
      redraw();
      say(`Updated "${l.name}".`);
    } catch (err) {
      say(err.message, true);
      update.disabled = false; update.textContent = "Save changes";
    }
  });

  const rename = el("button", { type: "button", class: "btn", text: "Rename", disabled: !state.loaded });
  rename.addEventListener("click", async () => {
    if (!name.value.trim()) { say("Type the new name first.", true); name.focus(); return; }
    busy(rename, "Renaming...");
    try {
      const l = await sendJSON("PUT", `/api/lineups/${state.loaded.id}`, { name: name.value });
      state.loaded = { id: l.id, name: l.name };
      redraw();
      say(`Renamed to "${l.name}".`);
    } catch (err) {
      say(err.message, true);
      rename.disabled = false; rename.textContent = "Rename";
    }
  });

  const del = el("button", { type: "button", class: "btn", text: "Delete", disabled: !state.loaded });
  del.addEventListener("click", () => {
    // Confirm inline, not with a browser pop-up.
    const yes = el("button", { type: "button", class: "btn btn-danger", text: "Yes, delete" });
    const no = el("button", { type: "button", class: "btn", text: "Cancel" });
    fill(confirmRow, el("span", { text: `Delete the saved lineup "${state.loaded.name}"? This cannot be undone.` }), yes, no);
    confirmRow.hidden = false;
    no.addEventListener("click", () => { confirmRow.hidden = true; del.focus(); });
    yes.addEventListener("click", async () => {
      busy(yes, "Deleting...");
      try {
        await sendJSON("DELETE", `/api/lineups/${state.loaded.id}`);
        const gone = state.loaded.name;
        state.loaded = null;
        redraw();
        say(`Deleted "${gone}". The lineup in the editor is unchanged.`);
      } catch (err) {
        say(err.message, true);
        yes.disabled = false; yes.textContent = "Yes, delete";
      }
    });
    yes.focus();
  });

  return el("div", { class: "saved-bar" },
    el("div", { class: "saved-row" }, select, load),
    el("div", { class: "saved-row" }, name, saveNew, update, rename, del,
      state.loaded ? el("span", { class: "muted", text: `Loaded: ${state.loaded.name}` }) : null),
    confirmRow);
}

// ---- Report tab ---------------------------------------------------------

// Ask the server for an AI draft built from the current lineups and overrides.
async function generateDraft(ctx) {
  const ai = editor.ai;
  const problem = lineupProblem(ctx, "us") || lineupProblem(ctx, "them");
  if (problem) { ai.state = "error"; ai.error = problem; render(ctx); return; }
  const request = ++ai.request;
  ai.state = "loading"; ai.error = null;
  generateButton.disabled = true;
  if (activeTab === "report") render(ctx);
  try {
    const draft = await postJSON("/api/reports/draft", {
      us: ctx.us.team.team_id, them: ctx.them.team.team_id,
      us_lineup: editor.us.ids || undefined, them_lineup: editor.them.ids || undefined,
      us_overrides: overridesPayload("us"), them_overrides: overridesPayload("them"),
    }, { timeoutMs: 300000 });
    if (request !== ai.request) return;
    draft.edited = false;
    ai.draft = draft; ai.state = "ready";
  } catch (err) {
    if (request !== ai.request) return;
    ai.state = "error"; ai.error = err.message;
  }
  generateButton.disabled = false;
  if (activeTab === "report") render(ctx);
}

// The AI part of the Report tab: idle, loading, error or the editable draft.
function aiPanels(ctx) {
  const ai = editor.ai;
  const head = (note) => el("div", { class: "panel-head", style: "justify-content: space-between" },
    el("h2", { class: "panel-title", text: "AI scouting report" }),
    el("span", { class: "panel-note", text: note }));
  const generate = (text) => {
    const b = el("button", { type: "button", class: "btn btn-primary", text });
    b.addEventListener("click", () => generateDraft(ctx));
    return b;
  };
  if (ai.keySet === false) {
    return [el("section", { class: "panel span-12", "aria-label": "AI scouting report" },
      head("Needs an API key"),
      el("div", { class: "ai-idle" }, el("button", { type: "button", class: "btn", disabled: true, text: "Generate report" }),
        el("span", { class: "muted", text: NO_KEY_TEXT })))];
  }
  if (ai.state === "idle") {
    return [el("section", { class: "panel span-12", "aria-label": "AI scouting report" },
      head("Written only from the numbers this app computed"),
      el("div", { class: "ai-idle" }, generate("Generate report"),
        el("span", { class: "muted", text: "Claude writes four sections from the lineups and numbers on this page. Every number in the text is checked against those facts." })))];
  }
  if (ai.state === "loading") {
    return [el("section", { class: "panel span-12", "aria-label": "AI scouting report" }, head("Writing..."), aiLoading())];
  }
  if (ai.state === "error") {
    return [el("section", { class: "panel span-12", "aria-label": "AI scouting report" }, head("Something went wrong"),
      el("div", { class: "state-error", role: "alert" }, el("span", { text: ai.error }), generate("Try again")))];
  }
  // Ready: editable sections on the left, the facts used on the right.
  const draft = ai.draft;
  const regen = el("button", { type: "button", class: "btn", text: "Regenerate" });
  const confirm = el("div", { class: "confirm-row", hidden: true });
  regen.addEventListener("click", () => {
    if (!draft.edited) { generateDraft(ctx); return; }
    const yes = el("button", { type: "button", class: "btn btn-danger", text: "Yes, replace it" });
    const no = el("button", { type: "button", class: "btn", text: "Cancel" });
    fill(confirm, el("span", { text: "Replace your edited text with a new draft?" }), yes, no);
    confirm.hidden = false;
    no.addEventListener("click", () => { confirm.hidden = true; regen.focus(); });
    yes.addEventListener("click", () => generateDraft(ctx));
    yes.focus();
  });
  let meta = modelLine(draft);
  const sections = aiSections(draft, { onEdit: () => {
    const fresh = modelLine(draft);
    if (fresh.textContent !== meta.textContent) { meta.replaceWith(fresh); meta = fresh; }
  } });
  return [
    el("section", { class: "panel span-8", "aria-label": "AI scouting report" },
      head("Edit anything before saving"), sections, meta,
      el("div", { class: "ai-actions" }, regen, confirm)),
    el("section", { class: "panel span-4", "aria-label": "Facts used" }, factsPanel(draft.facts)),
  ];
}

function renderReport(ctx) {
  const next = ctx.next_meeting;
  if (editor.draft.title === null) {
    editor.draft.title = `${ctx.us.team.abbreviation} vs ${ctx.them.team.abbreviation}` +
      (next ? `, ${formatDay(next.date, { month: "short", day: "numeric" })}` : "");
  }
  const title = el("input", { class: "input input-wide", type: "text", maxlength: "120", id: "report-title", value: editor.draft.title });
  const notes = el("textarea", { class: "textarea", id: "report-notes", rows: "6", maxlength: "10000",
    placeholder: "Your own notes: coverages, who to load up on..." });
  notes.value = editor.draft.notes;
  title.addEventListener("input", () => { editor.draft.title = title.value; });
  notes.addEventListener("input", () => { editor.draft.notes = notes.value; });
  const message = el("p", { class: "side-message", role: "status" });
  const save = el("button", { type: "button", class: "btn btn-primary", text: "Save report" });
  const box = el("div", { "data-matchup-box": "summary" });
  const ai = editor.ai;

  save.addEventListener("click", async () => {
    const problem = lineupProblem(ctx, "us") || lineupProblem(ctx, "them");
    if (!title.value.trim()) { message.textContent = "Give the report a title."; message.className = "side-message loss"; title.focus(); return; }
    if (problem) { message.textContent = problem; message.className = "side-message loss"; return; }
    if (ai.state === "loading") { message.textContent = "Wait for the AI report to finish, or save after it is done."; message.className = "side-message loss"; return; }
    save.disabled = true; save.textContent = "Saving...";
    message.textContent = ""; message.className = "side-message";
    const lineup = (side) => ({ player_ids: editor[side].ids || undefined, overrides: overridesPayload(side) });
    const d = ai.state === "ready" ? ai.draft : null;
    try {
      const report = await postJSON("/api/reports", {
        us_team_id: ctx.us.team.team_id, them_team_id: ctx.them.team.team_id,
        game_id: next ? next.game_id : null, title: title.value, notes: notes.value,
        us_lineup: lineup("us"), them_lineup: lineup("them"),
        ai_text: d ? {
          sections: d.sections, model: d.model, requested_model: d.requested_model, prompt_version: d.prompt_version,
          generated_at: d.generated_at, flags: d.flags, facts: d.facts, edited: Boolean(d.edited), usage: d.usage,
        } : null,
      });
      fill(message, "Saved. ", el("a", { href: `/reports/${report.id}`, text: "Open the saved report" }),
        el("span", { class: "muted", text: d ? " The AI text, matchups and facts are stored as they are now." : " The matchups are stored as they are now." }));
      message.className = "side-message";
    } catch (err) {
      message.textContent = err.message;
      message.className = "side-message loss";
    }
    save.disabled = false; save.textContent = "Save report";
  });

  fill(root,
    aiPanels(ctx),
    el("section", { class: "panel span-12", "aria-label": "Report" },
      el("div", { class: "panel-head", style: "justify-content: space-between" },
        el("h2", { class: "panel-title", text: "Save the report" }),
        el("span", { class: "panel-note", text: ai.state === "ready" ? "Saves the AI text above with your notes" : "You can save notes only, or generate the AI report first" })),
      el("div", { class: "form-body" },
        el("label", { class: "field" }, el("span", { class: "label", text: "Title" }), title),
        el("label", { class: "field" }, el("span", { class: "label", text: "Your notes" }), notes),
        el("div", { class: "form-actions" }, save, message))),
    el("section", { class: "panel span-12", "aria-label": "What will be saved" },
      el("div", { class: "panel-head", style: "justify-content: space-between" },
        el("h2", { class: "panel-title", text: "Lineups and matchups" }),
        el("span", { class: "panel-note", text: "Both lineups and the matchups at this moment" })),
      box));
  drawMatchupBox(box, ctx);
  if (!editor.result && !editor.loading) fetchMatchups(ctx);
}
