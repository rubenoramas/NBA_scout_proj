// Landing page: team picker, month calendar of the team's schedule, and a
// search box to scout any team.

import { badge, el, emptyBox, errorBox, getJSON, parseDay, showAsOf, skeleton, store } from "./api.js";

const MY_TEAM_KEY = "opponentScout.myTeam";

const pickerSection = document.getElementById("picker");
const pickerBody = document.getElementById("picker-body");
const scheduleSection = document.getElementById("schedule");
const calendarBody = document.getElementById("calendar");
const monthLabel = document.getElementById("month-label");
const prevBtn = document.getElementById("prev-month");
const nextBtn = document.getElementById("next-month");

let teams = [];
let myTeam = null;
let games = [];
let month = null; // Date set to the first day of the shown month
let firstMonth = null;
let lastMonth = null;
let asOf = null;

function scoutUrl(us, them) {
  const params = new URLSearchParams({ us: us.abbreviation, them: them.abbreviation });
  return `/scout?${params}`;
}

// ---- Teams and picker -------------------------------------------------

async function loadTeams() {
  pickerBody.replaceChildren(skeleton(3, "Loading teams"));
  try {
    const data = await getJSON("/api/teams");
    teams = data.teams;
    asOf = data.data_as_of;
    showAsOf(asOf);
    if (teams.length === 0) {
      pickerBody.replaceChildren(emptyBox("No teams are loaded yet. Run the data pull and restart the app."));
      return;
    }
    const saved = store.get(MY_TEAM_KEY);
    const savedTeam = teams.find((t) => t.abbreviation === saved);
    if (savedTeam) {
      chooseTeam(savedTeam);
    } else {
      renderPicker();
    }
  } catch (err) {
    pickerBody.replaceChildren(errorBox(err.message, loadTeams));
  }
}

function renderPicker() {
  pickerSection.hidden = false;
  scheduleSection.hidden = true;
  const columns = ["East", "West"].map((conf) =>
    el("div", { class: "conf-col" },
      el("h3", { class: "conf-title", text: `${conf}ern Conference` }),
      el("div", { class: "team-grid" },
        teams
          .filter((t) => t.conference === conf)
          .map((t) =>
            el("button", { class: "team-tile", type: "button", onclick: () => chooseTeam(t) },
              badge(t.abbreviation, { conference: t.conference }),
              el("span", { class: "team-tile-name" },
                el("span", { class: "team-city", text: t.city }),
                el("span", { class: "team-name", text: t.name })))))));
  pickerBody.replaceChildren(el("div", { class: "conf-cols" }, columns));
}

function chooseTeam(team) {
  myTeam = team;
  store.set(MY_TEAM_KEY, team.abbreviation);
  pickerSection.hidden = true;
  scheduleSection.hidden = false;
  document.getElementById("my-badge").replaceChildren(badge(team.abbreviation, { conference: team.conference, size: "lg" }));
  document.getElementById("schedule-title").textContent = team.full_name;
  document.getElementById("schedule-sub").textContent = `${team.conference}ern Conference, ${team.division} Division`;
  loadSchedule();
}

document.getElementById("change-team").addEventListener("click", () => {
  store.remove(MY_TEAM_KEY);
  myTeam = null;
  renderPicker();
  pickerSection.scrollIntoView({ behavior: "smooth", block: "start" });
});

// ---- Schedule and calendar --------------------------------------------

async function loadSchedule() {
  const team = myTeam;
  monthLabel.textContent = "";
  calendarBody.replaceChildren(skeleton(5, "Loading schedule"));
  prevBtn.disabled = nextBtn.disabled = true;
  try {
    const data = await getJSON(`/api/teams/${team.team_id}/schedule`);
    if (team !== myTeam) return; // the user switched teams meanwhile
    games = data.games;
    const played = games.filter((g) => g.played);
    const wins = played.filter((g) => g.result === "W").length;
    document.getElementById("schedule-sub").textContent =
      `${data.season} season. ${wins}-${played.length - wins} so far, ${games.length - played.length} games to play.`;
    if (games.length === 0) {
      calendarBody.replaceChildren(emptyBox("No games are scheduled for this team."));
      return;
    }
    firstMonth = monthStart(parseDay(games[0].date));
    lastMonth = monthStart(parseDay(games[games.length - 1].date));
    // Open on the month of the "data as of" date, inside the season.
    let start = asOf ? monthStart(parseDay(asOf)) : firstMonth;
    if (start < firstMonth) start = firstMonth;
    if (start > lastMonth) start = lastMonth;
    month = start;
    renderCalendar();
  } catch (err) {
    calendarBody.replaceChildren(errorBox(err.message, loadSchedule));
  }
}

function monthStart(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function dayKey(date) {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

function renderCalendar() {
  monthLabel.textContent = month.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  prevBtn.disabled = month <= firstMonth;
  nextBtn.disabled = month >= lastMonth;

  const byDay = new Map(games.map((g) => [g.date, g]));
  const year = month.getFullYear();
  const mon = month.getMonth();
  const daysInMonth = new Date(year, mon + 1, 0).getDate();
  const leadingBlanks = month.getDay(); // 0 = Sunday

  const cells = [];
  for (let i = 0; i < leadingBlanks; i++) cells.push(el("div", { class: "cal-cell blank", "aria-hidden": "true" }));

  let gamesThisMonth = 0;
  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(year, mon, day);
    const key = dayKey(date);
    const game = byDay.get(key);
    if (game) gamesThisMonth++;
    const isAsOf = key === asOf;
    cells.push(el("div", { class: `cal-cell${game ? " has-game" : ""}${isAsOf ? " is-asof" : ""}` },
      el("span", { class: "cal-day", text: day }),
      game ? gameChip(game) : null));
  }

  const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) =>
    el("div", { class: "cal-weekday", text: d }));

  const grid = el("div", { class: "cal-grid" }, weekdays, cells);
  if (gamesThisMonth === 0) {
    calendarBody.replaceChildren(grid, emptyBox("No games this month."));
  } else {
    calendarBody.replaceChildren(grid);
  }
}

function gameChip(game) {
  const opp = teams.find((t) => t.team_id === game.opponent.team_id) || { abbreviation: game.opponent.abbreviation };
  const where = game.home ? "vs" : "@";
  const cup = game.season_type === "nba-cup" ? el("span", { class: "tag tag-cup", text: "Cup" }) : null;
  if (game.played) {
    const win = game.result === "W";
    return el("div", { class: `chip ${win ? "chip-win" : "chip-loss"}` },
      el("span", { class: "chip-opp" }, el("span", { class: "chip-where", text: where }), badge(opp.abbreviation, { conference: opp.conference, size: "sm" })),
      el("span", { class: "chip-score" },
        el("strong", { text: game.result }), ` ${game.team_pts}-${game.opp_pts}`),
      cup);
  }
  return el("a", {
    class: "chip chip-upcoming",
    href: scoutUrl(myTeam, opp),
    "aria-label": `Scout ${opp.city || ""} ${opp.name || opp.abbreviation} on ${game.date}`,
  },
    el("span", { class: "chip-opp" }, el("span", { class: "chip-where", text: where }), badge(opp.abbreviation, { conference: opp.conference, size: "sm" })),
    el("span", { class: "chip-cta", text: "Scout" }),
    cup);
}

prevBtn.addEventListener("click", () => {
  month = new Date(month.getFullYear(), month.getMonth() - 1, 1);
  renderCalendar();
});
nextBtn.addEventListener("click", () => {
  month = new Date(month.getFullYear(), month.getMonth() + 1, 1);
  renderCalendar();
});

// ---- Search -----------------------------------------------------------

const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
const searchHelp = document.getElementById("search-help");

function matches(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return teams.filter((t) => {
    const fields = [t.abbreviation, t.city, t.name, t.full_name];
    // The data lists the Clippers' city as "LA", so also match the full name.
    if (t.city === "LA") fields.push("Los Angeles");
    return fields.some((v) => v && v.toLowerCase().includes(q));
  });
}

function goScout(them) {
  if (!myTeam) {
    searchHelp.textContent = "Choose your team first, then pick who to scout.";
    searchHelp.hidden = false;
    pickerSection.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (them.team_id === myTeam.team_id) {
    searchHelp.textContent = "That is your own team. Pick an opponent.";
    searchHelp.hidden = false;
    return;
  }
  window.location.href = scoutUrl(myTeam, them);
}

function renderResults() {
  searchHelp.hidden = true;
  const query = searchInput.value;
  if (!query.trim()) {
    searchResults.hidden = true;
    return;
  }
  if (teams.length === 0) {
    searchResults.replaceChildren(el("li", { class: "search-empty", text: "Teams are still loading." }));
    searchResults.hidden = false;
    return;
  }
  const found = matches(query);
  searchResults.replaceChildren(
    ...(found.length
      ? found.map((t) =>
          el("li", { role: "option" },
            el("button", { type: "button", class: "search-item", onclick: () => goScout(t) },
              badge(t.abbreviation, { conference: t.conference, size: "sm" }),
              el("span", { text: t.full_name }))))
      : [el("li", { class: "search-empty", text: `No team matches "${query.trim()}".` })]));
  searchResults.hidden = false;
}

searchInput.addEventListener("input", renderResults);
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const found = matches(searchInput.value);
    if (found.length) goScout(found[0]);
    else renderResults();
  } else if (event.key === "Escape") {
    searchInput.value = "";
    searchResults.hidden = true;
  }
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".search")) searchResults.hidden = true;
});

loadTeams();
