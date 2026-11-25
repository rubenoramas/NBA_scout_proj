// Landing page. First visit: choose your team. After that: the season
// schedule as a table, plus a sidebar with the next game, a team snapshot
// and a mini month view.

import { spotLine } from "./spots.js";
import {
  MY_TEAM_KEY, SEASON_TYPE_LABEL, chevron, chip, el, emptyLine, errorLine, fill, formatDay, getJSON,
  parseDay, resultChip, scoutUrl, seedText, shortStreak, skeletonRows, store, streakClass, tag,
} from "./api.js";
import { defaultState, nextSort, renderBoxTable } from "./boxtable.js";
import { loadTeams, matchTeams, setScoutNav, setSwitcher } from "./topbar.js";

const loadView = document.getElementById("load-view");
const selectView = document.getElementById("select-view");
const scheduleView = document.getElementById("schedule-view");

let teams = [];
let teamsById = new Map();
let asOf = null;
let myTeam = null;

function showView(view) {
  loadView.hidden = view !== loadView;
  selectView.hidden = view !== selectView;
  scheduleView.hidden = view !== scheduleView;
}

async function start() {
  showView(loadView);
  fill(loadView, skeletonRows(6, [38, 220, 160]));
  try {
    const data = await loadTeams();
    teams = data.teams;
    asOf = data.data_as_of;
    teamsById = new Map(teams.map((t) => [t.team_id, t]));
  } catch (err) {
    fill(loadView, errorLine(err.message, start));
    return;
  }
  if (!teams.length) {
    fill(loadView, emptyLine("No teams are loaded yet. Run the data pull and restart the app."));
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const saved = teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY));
  if (saved && !params.has("choose")) {
    showSchedule(saved);
  } else {
    showSelect(saved);
  }
}

// ---- Team selection ---------------------------------------------------

const filterInput = document.getElementById("team-filter");
const selectBody = document.getElementById("select-body");

function showSelect(current) {
  myTeam = null;
  setSwitcher(current || null);
  setScoutNav(null);
  document.getElementById("nav-schedule").setAttribute("aria-current", "page");
  showView(selectView);
  renderSelect();
  filterInput.focus();
}

function renderSelect() {
  const shown = new Set(matchTeams(teams, filterInput.value).map((t) => t.team_id));
  if (shown.size === 0) {
    fill(selectBody, emptyLine(`No team matches "${filterInput.value.trim()}".`));
    return;
  }
  const conferences = ["East", "West"].map((conf) => {
    const confTeams = teams.filter((t) => t.conference === conf);
    const divisions = [...new Set(confTeams.map((t) => t.division))].sort();
    return el("div", { class: "conf" },
      el("div", { class: "conf-head", text: `${conf}ern Conference` }),
      el("div", { class: "divisions" },
        divisions.map((division) => {
          const rows = confTeams
            .filter((t) => t.division === division && shown.has(t.team_id))
            .sort((a, b) => a.city.localeCompare(b.city))
            .map((t) =>
              el("button", { type: "button", class: "team-row", onclick: () => chooseTeam(t) },
                chip(t.abbreviation, { fixed: true }),
                el("span", { class: "team-row-name" },
                  el("span", { class: "muted", text: t.city }),
                  el("span", { class: "strong", text: ` ${t.name}` }))));
          return el("div", { class: "division" },
            el("div", { class: "division-name", text: division }),
            rows.length ? rows : el("div", { class: "division-empty", text: "No match" }));
        })));
  });
  fill(selectBody, el("div", { class: "conf-wrap" }, conferences));
}

filterInput.addEventListener("input", renderSelect);
filterInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const found = matchTeams(teams, filterInput.value);
    if (found.length === 1) chooseTeam(found[0]);
  }
});

function chooseTeam(team) {
  store.set(MY_TEAM_KEY, team.abbreviation);
  window.history.replaceState(null, "", "/");
  filterInput.value = "";
  showSchedule(team);
}

// ---- Schedule ---------------------------------------------------------

const rowsBody = document.getElementById("schedule-rows");
const monthLabel = document.getElementById("month-label");
const prevBtn = document.getElementById("prev-month");
const nextBtn = document.getElementById("next-month");
const segButtons = [...document.querySelectorAll(".seg button")];

let games = [];
let recordAfter = new Map(); // game_id -> "W-L" after that game
let nextGame = null;
let month = null;
let firstMonth = null;
let lastMonth = null;
let filter = "all";

function showSchedule(team) {
  myTeam = team;
  lastBox = null;
  showTab("schedule");
  setSwitcher(team);
  document.getElementById("nav-schedule").setAttribute("aria-current", "page");
  document.getElementById("snapshot-title").textContent = `${team.abbreviation} snapshot`;
  showView(scheduleView);
  loadSchedule();
}

function monthStart(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

// Running record over the whole season, in date order, so any month starts
// from the record before its first game. The NBA Cup final does not count in
// the standings, so it is skipped.
function computeRecords(list) {
  const map = new Map();
  let wins = 0;
  let losses = 0;
  for (const g of list) {
    if (!g.played) continue;
    if (g.season_type !== "nba-cup") {
      if (g.result === "W") wins++;
      else if (g.result === "L") losses++;
    }
    map.set(g.game_id, `${wins}-${losses}`);
  }
  return { map, record: `${wins}-${losses}` };
}

async function loadSchedule() {
  const team = myTeam;
  monthLabel.textContent = "";
  prevBtn.disabled = nextBtn.disabled = true;
  fill(rowsBody, skeletonRows(8, [88, 200, 24, 64, 40, 40]));
  fill(document.getElementById("next-body"), skeletonRows(3, [60, 120, 60]));
  fill(document.getElementById("snapshot-body"), skeletonRows(2, [60, 60, 60]));
  fill(document.getElementById("mini-body"), skeletonRows(4, [220]));
  document.getElementById("next-note").textContent = "";
  try {
    const data = await getJSON(`/api/teams/${team.team_id}/schedule`);
    if (team !== myTeam) return; // the user switched teams meanwhile
    games = data.games;
    document.getElementById("schedule-note").textContent = `${data.season} season`;
  } catch (err) {
    fill(rowsBody, errorLine(err.message, loadSchedule));
    for (const id of ["next-body", "snapshot-body", "mini-body"]) {
      fill(document.getElementById(id), emptyLine("Waiting for the schedule."));
    }
    return;
  }

  const { map, record } = computeRecords(games);
  recordAfter = map;
  setSwitcher(team, record);
  nextGame = games.find((g) => !g.played) || null;
  setScoutNav(nextGame ? scoutUrl(team.abbreviation, nextGame.opponent.abbreviation) : null);

  if (!games.length) {
    fill(rowsBody, emptyLine("No games are scheduled for this team."));
    fill(document.getElementById("mini-body"), emptyLine("No games scheduled."));
  } else {
    firstMonth = monthStart(parseDay(games[0].date));
    lastMonth = monthStart(parseDay(games[games.length - 1].date));
    let start = asOf ? monthStart(parseDay(asOf)) : firstMonth;
    if (start < firstMonth) start = firstMonth;
    if (start > lastMonth) start = lastMonth;
    month = start;
    renderMonth();
  }
  loadSide();
}

function oppTeam(game) {
  return teamsById.get(game.opponent.team_id) || { abbreviation: game.opponent.abbreviation, name: game.opponent.abbreviation };
}

function scheduleRow(game) {
  const opp = oppTeam(game);
  const isNext = nextGame && game.game_id === nextGame.game_id;
  const oppCell = el("span", { class: "opp" },
    el("span", { class: "ha", text: game.home ? "vs" : "@" }),
    chip(opp.abbreviation, { link: true }),
    el("span", { class: "text-2", text: opp.name }),
    game.season_type === "nba-cup" ? tag("NBA Cup", "gold") : null,
    isNext ? tag("Next", "accent") : null);
  if (game.played) {
    const margin = game.team_pts - game.opp_pts;
    return el("div", { class: "trow cols-schedule" },
      el("span", { class: "text-2", text: formatDay(game.date) }),
      oppCell,
      el("span", {}, resultChip(game.result)),
      el("span", { class: "strong", text: `${game.team_pts}-${game.opp_pts}` }),
      el("span", { class: "num text-2", text: margin > 0 ? `+${margin}` : String(margin) }),
      el("span", { class: "num text-2", text: recordAfter.get(game.game_id) || "–" }),
      el("a", {
        class: "scout-link",
        href: `/game/${game.game_id}`,
        "aria-label": `Box score, ${formatDay(game.date)} ${game.home ? "vs" : "at"} ${opp.abbreviation}`,
      }, "Box score", chevron()));
  }
  // Upcoming: rest and travel facts for both teams, in place of the score.
  return el("div", { class: "trow cols-schedule" },
    el("span", { class: "text-2", text: formatDay(game.date) }),
    oppCell,
    el("span", { class: "spots-cell", "aria-label": "Schedule spots" },
      spotLine(myTeam.abbreviation, game.spots), spotLine(opp.abbreviation, game.opp_spots)),
    el("a", {
      class: "scout-link",
      href: scoutUrl(myTeam.abbreviation, opp.abbreviation),
      "aria-label": `Scout ${opp.full_name || opp.abbreviation}, ${formatDay(game.date)}`,
    }, "Scout", chevron()));
}

function dividerRow() {
  return el("div", { class: "divider-row" },
    `Games through ${formatDay(asOf, { weekday: "short", month: "short", day: "numeric" })}`,
    el("span", { class: "divider-note", text: "Games below have not been played yet" }));
}

function inMonth(dateText) {
  const d = parseDay(dateText);
  return d.getFullYear() === month.getFullYear() && d.getMonth() === month.getMonth();
}

function renderMonth() {
  monthLabel.textContent = month.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  prevBtn.disabled = month <= firstMonth;
  nextBtn.disabled = month >= lastMonth;

  const shown = games.filter((g) => inMonth(g.date) &&
    (filter === "all" || (filter === "home" ? g.home : !g.home)));
  const rows = [];
  let dividerDone = !(asOf && inMonth(asOf));
  for (const game of shown) {
    if (!dividerDone && game.date > asOf) {
      rows.push(dividerRow());
      dividerDone = true;
    }
    rows.push(scheduleRow(game));
  }
  if (!dividerDone && shown.length) rows.push(dividerRow());
  if (!shown.length) {
    const kind = filter === "home" ? "home games" : filter === "road" ? "road games" : "games";
    rows.push(emptyLine(`No ${kind} this month.`));
  }
  fill(rowsBody, rows);
  renderMini();
}

prevBtn.addEventListener("click", () => {
  month = new Date(month.getFullYear(), month.getMonth() - 1, 1);
  renderMonth();
});
nextBtn.addEventListener("click", () => {
  month = new Date(month.getFullYear(), month.getMonth() + 1, 1);
  renderMonth();
});
for (const btn of segButtons) {
  btn.addEventListener("click", () => {
    filter = btn.dataset.filter;
    for (const b of segButtons) b.setAttribute("aria-pressed", String(b === btn));
    renderMonth();
  });
}

// ---- Mini month view --------------------------------------------------

function dayKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function renderMini() {
  document.getElementById("mini-title").textContent = month.toLocaleDateString("en-US", { month: "long" });
  const byDay = new Map(games.map((g) => [g.date, g]));
  const cells = [];
  for (let i = 0; i < month.getDay(); i++) cells.push(el("div", { class: "mini-day blank", "aria-hidden": "true" }));
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  for (let day = 1; day <= days; day++) {
    const key = dayKey(new Date(month.getFullYear(), month.getMonth(), day));
    const game = byDay.get(key);
    let mark = null;
    let label = formatDay(key);
    if (game && game.played) {
      mark = el("span", { class: `dot ${game.result === "W" ? "dot-win" : "dot-loss"}`, "aria-hidden": "true" });
      label += `, ${game.result === "W" ? "win" : "loss"} ${game.home ? "vs" : "at"} ${game.opponent.abbreviation}`;
    } else if (game) {
      mark = el("span", { class: "dot dot-upcoming", "aria-hidden": "true" });
      label += `, ${game.home ? "vs" : "at"} ${game.opponent.abbreviation}, scout this game`;
    }
    const cls = `mini-day${key === asOf ? " asof" : ""}`;
    const content = [el("span", { text: day }), el("span", { class: "mini-mark" }, mark)];
    let href = null;
    if (game && game.played) {
      href = `/game/${game.game_id}`;
      label += ", open box score";
    } else if (game) {
      href = scoutUrl(myTeam.abbreviation, game.opponent.abbreviation);
    }
    cells.push(href
      ? el("a", { class: cls, href, "aria-label": label }, content)
      : el("div", { class: cls }, content));
  }
  fill(document.getElementById("mini-body"),
    el("div", { class: "mini-head", "aria-hidden": "true" }, ["S", "M", "T", "W", "T", "F", "S"].map((d) => el("span", { text: d }))),
    el("div", { class: "mini-grid" }, cells));
}

// ---- Sidebar: next game and snapshot ---------------------------------

async function loadSide() {
  const team = myTeam;
  const nextBody = document.getElementById("next-body");
  const snapBody = document.getElementById("snapshot-body");
  const lastPlayed = [...games].reverse().find((g) => g.played);
  // The context endpoint needs an opponent. Use the next game, or the last
  // one when the season is over, so the snapshot still has data.
  const ref = nextGame || lastPlayed;
  if (!ref) {
    fill(nextBody, emptyLine("No games scheduled."));
    fill(snapBody, emptyLine("No games played yet."));
    return;
  }
  fill(nextBody, skeletonRows(3, [60, 120, 60]));
  fill(snapBody, skeletonRows(2, [60, 60, 60]));
  let ctx;
  try {
    const query = new URLSearchParams({ us: team.team_id, them: ref.opponent.team_id });
    ctx = await getJSON(`/api/games/context?${query}`);
    if (team !== myTeam) return;
  } catch (err) {
    fill(nextBody, errorLine(err.message, loadSide));
    fill(snapBody, errorLine("The snapshot could not load.", loadSide));
    return;
  }
  renderNext(ctx);
  renderSnapshot(ctx.us.standing);
}

function versusSide(side, alignRight) {
  const s = side.standing || {};
  return el("div", { style: alignRight ? "text-align: right" : null },
    el("div", { class: "versus-abbr", text: side.team.abbreviation }),
    el("div", { class: "muted", style: "margin-top: 2px", text: `${s.record || "–"} · ${seedText(s)}` }),
    el("div", { class: `strong ${streakClass(s.streak)}`, style: "margin-top: 4px", text: shortStreak(s.streak) }));
}

function meetingText(m, usAbbr) {
  if (!m) return "Not met this season or last";
  const venue = m.home ? usAbbr : m.opponent.abbreviation;
  const winner = m.result === "W" ? usAbbr : m.opponent.abbreviation;
  const hi = Math.max(m.team_pts, m.opp_pts);
  const lo = Math.min(m.team_pts, m.opp_pts);
  const date = formatDay(m.date, { month: "short", day: "numeric", year: "numeric" });
  const playoff = m.season_type === "playoffs" ? ", playoffs" : m.season_type === "play-in" ? ", play-in" : "";
  return `${winner} won ${hi}-${lo} · ${date} at ${venue}${playoff}`;
}

function renderNext(ctx) {
  const nextBody = document.getElementById("next-body");
  const note = document.getElementById("next-note");
  if (!nextGame) {
    note.textContent = "";
    fill(nextBody, emptyLine("No games left this season."));
    return;
  }
  const venue = nextGame.home ? myTeam.abbreviation : nextGame.opponent.abbreviation;
  note.textContent = `${formatDay(nextGame.date)} · at ${venue}`;
  fill(nextBody,
    el("div", { class: "versus" },
      versusSide(ctx.us, false),
      el("div", { class: "versus-vs", text: "VS" }),
      versusSide(ctx.them, true)),
    el("div", { class: "side-line" },
      el("span", { class: "muted", text: "Last meeting" }),
      el("span", { text: meetingText(ctx.last_meeting, myTeam.abbreviation) })),
    nextGame.season_type !== "regular-season"
      ? el("div", { class: "side-line" },
        el("span", { class: "muted", text: "Game type" }),
        el("span", { text: SEASON_TYPE_LABEL[nextGame.season_type] || nextGame.season_type }))
      : null,
    el("div", { class: "side-action" },
      el("a", { class: "btn btn-primary btn-block", href: scoutUrl(myTeam.abbreviation, nextGame.opponent.abbreviation), text: "Open scouting report" })));
}

function renderSnapshot(standing) {
  const body = document.getElementById("snapshot-body");
  if (!standing) {
    fill(body, emptyLine("No standings loaded for this team."));
    return;
  }
  const tile = (label, value, cls = "") =>
    el("div", { class: "tile" },
      el("div", { class: "label", text: label }),
      el("div", { class: `tile-value ${cls}`, text: value || "–" }));
  fill(body, el("div", { class: "tiles" },
    tile("Record", standing.record),
    tile("Seed", seedText(standing, { short: true })),
    tile("Streak", shortStreak(standing.streak), streakClass(standing.streak)),
    tile("Last 10", standing.last_ten),
    tile("Home", standing.home_record),
    tile("Road", standing.road_record)));
}

// ---- Schedule panel tabs: Schedule and Last game -----------------------

const tabSchedule = document.getElementById("tab-schedule");
const tabLast = document.getElementById("tab-last");
const schedulePane = document.getElementById("schedule-pane");
const lastPane = document.getElementById("last-pane");
const scheduleControls = document.getElementById("schedule-controls");
let lastBox = null;
const lastState = defaultState();

function showTab(which) {
  const last = which === "last";
  tabSchedule.setAttribute("aria-selected", String(!last));
  tabLast.setAttribute("aria-selected", String(last));
  schedulePane.hidden = last;
  scheduleControls.hidden = last;
  lastPane.hidden = !last;
  if (last) loadLastGame();
}

tabSchedule.addEventListener("click", () => showTab("schedule"));
tabLast.addEventListener("click", () => showTab("last"));
// Arrow keys move between the two tabs.
for (const tab of [tabSchedule, tabLast]) {
  tab.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const other = tab === tabSchedule ? tabLast : tabSchedule;
      other.focus();
      showTab(other === tabLast ? "last" : "schedule");
    }
  });
}

async function loadLastGame() {
  const team = myTeam;
  const last = [...games].reverse().find((g) => g.played);
  if (!last) {
    fill(lastPane, emptyLine(games.length ? "No games played yet this season." : "Waiting for the schedule."));
    return;
  }
  if (lastBox && lastBox.game.game_id === last.game_id) {
    renderLastGame();
    return;
  }
  fill(lastPane, skeletonRows(8, [180, 40, 40, 60, 40, 60]));
  try {
    const box = await getJSON(`/api/games/${last.game_id}/boxscore`);
    if (team !== myTeam) return;
    lastBox = box;
  } catch (err) {
    fill(lastPane, errorLine(err.message, loadLastGame));
    return;
  }
  renderLastGame();
}

function renderLastGame() {
  const box = lastBox;
  const ours = box.home.team.team_id === myTeam.team_id ? box.home : box.away;
  const theirs = ours === box.home ? box.away : box.home;
  const result = ours.pts > theirs.pts ? "W" : "L";
  const tableBox = el("div");
  fill(lastPane,
    el("div", { class: "score-line" },
      resultChip(result),
      el("span", { class: "final", text: `${ours.pts}-${theirs.pts}` }),
      el("span", { class: "text-2" }, `${ours.home ? "vs" : "at"} `, chip(theirs.team.abbreviation, { link: true }), ` ${theirs.team.name || ""}`),
      el("span", { class: "muted", text: formatDay(box.game.date) }),
      el("span", { class: "spacer" }),
      el("a", { class: "scout-link", href: `/game/${box.game.game_id}` }, "Full box score", chevron())),
    tableBox);
  renderBoxTable(tableBox, ours, lastState, {
    onSort: (key) => {
      nextSort(lastState, key);
      renderLastGame();
    },
  });
}

start();
