// Top bar shared by every page: team switcher, main navigation, team
// search and the "data as of" date.

import { MY_TEAM_KEY, chip, el, fill, formatDay, getJSON, scoutUrl, store } from "./api.js";

let teamsPromise = null;
let teams = [];

// One /api/teams request per page, shared by the top bar and the page.
export function loadTeams() {
  if (!teamsPromise) {
    teamsPromise = getJSON("/api/teams").then((data) => {
      teams = data.teams;
      showFreshness(data.data_as_of, data.pulled_at);
      return data;
    });
    teamsPromise.catch(() => { teamsPromise = null; });
  }
  return teamsPromise;
}

export function myTeamAbbr() {
  return store.get(MY_TEAM_KEY);
}

// "My team" links to the chosen team's page, or is disabled with no team.
export function setMyTeamNav(abbr = myTeamAbbr()) {
  const old = document.getElementById("nav-myteam");
  if (!old) return;
  const onPage = window.location.pathname.toUpperCase() === `/TEAM/${(abbr || "").toUpperCase()}`;
  const node = abbr
    ? el("a", { id: "nav-myteam", href: `/team/${encodeURIComponent(abbr)}`, "aria-current": onPage ? "page" : null, text: "My team" })
    : el("span", { id: "nav-myteam", class: "nav-disabled", title: "Choose your team first", text: "My team" });
  old.replaceWith(node);
}
setMyTeamNav();

// How old a pull can be before the dot turns from green to amber.
const STALE_AFTER_HOURS = 48;

// Shows both facts: the latest game in the data, and when it was pulled.
// For example "Games through Tue, Nov 17 · pulled Nov 18, 9:02 AM".
export function showFreshness(gamesThrough, pulledAt) {
  if (!gamesThrough) return;
  const parts = [`Games through ${formatDay(gamesThrough)}`];
  const dot = document.getElementById("asof-dot");
  const pulled = pulledAt ? new Date(pulledAt) : null;
  let stale = false;
  if (pulled && !Number.isNaN(pulled.getTime())) {
    // Shown in the viewer's own time zone.
    const when = pulled.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    parts.push(`pulled ${when}`);
    stale = Date.now() - pulled.getTime() > STALE_AFTER_HOURS * 3600 * 1000;
  }
  document.getElementById("asof-text").textContent = parts.join(" · ");
  dot.className = `dot ${stale ? "dot-stale" : "dot-win"}`;
  const node = document.getElementById("asof");
  node.title = stale
    ? "The data was pulled more than 2 days ago. Run ./refresh.sh to update it."
    : "Latest game in the data, and when the data was pulled.";
  node.hidden = false;
}

// Show the chosen team in the switcher, with its record when known.
export function setSwitcher(team, record) {
  setMyTeamNav(team ? team.abbreviation : null);
  const node = document.getElementById("team-switcher");
  if (!team) {
    node.className = "switcher empty";
    node.textContent = "No team selected";
    node.setAttribute("aria-label", "Choose your team");
    return;
  }
  node.className = "switcher";
  node.setAttribute("aria-label", `Your team: ${team.full_name}. Change team`);
  fill(node,
    chip(team.abbreviation),
    el("span", { class: "switcher-name", text: team.full_name }),
    record ? el("span", { class: "muted", text: record }) : null,
    el("span", { class: "muted", "aria-hidden": "true", text: "▾" }));
}

// Point the Scouting nav item at a scouting page, or disable it.
export function setScoutNav(url, { current = false } = {}) {
  const old = document.getElementById("nav-scout");
  const node = url
    ? el("a", { id: "nav-scout", href: url, "aria-current": current ? "page" : null, text: "Scouting" })
    : el("span", { id: "nav-scout", class: "nav-disabled", title: "Pick a game to scout first", text: "Scouting" });
  old.replaceWith(node);
}

// ---- Search -------------------------------------------------------------

const input = document.getElementById("search-input");
const menu = document.getElementById("search-menu");

export function matchTeams(list, query) {
  const q = query.trim().toLowerCase();
  if (!q) return list;
  return list.filter((t) => {
    const fields = [t.abbreviation, t.city, t.name, t.full_name];
    // The data lists the Clippers' city as "LA", so also match the full name.
    if (t.city === "LA") fields.push("Los Angeles");
    return fields.some((v) => v && v.toLowerCase().includes(q));
  });
}

function note(text, warn = false) {
  fill(menu, el("li", { class: `search-note${warn ? " warn" : ""}`, text }));
  menu.hidden = false;
}

function goScout(them) {
  const mine = myTeamAbbr();
  if (!mine || !teams.some((t) => t.abbreviation === mine)) {
    note("Choose your team first, then search for an opponent.", true);
    return;
  }
  if (them.abbreviation === mine) {
    note("That is your own team. Pick an opponent.", true);
    return;
  }
  window.location.href = scoutUrl(mine, them.abbreviation);
}

async function renderMenu() {
  const query = input.value;
  if (!query.trim()) {
    menu.hidden = true;
    return;
  }
  if (!teams.length) {
    note("Loading teams...");
    try {
      await loadTeams();
    } catch (err) {
      note(err.message, true);
      return;
    }
  }
  const found = matchTeams(teams, query);
  if (!found.length) {
    note(`No team matches "${query.trim()}".`);
    return;
  }
  fill(menu, found.map((t) =>
    el("li", {},
      el("button", { type: "button", class: "search-item", onclick: () => goScout(t) },
        chip(t.abbreviation, { fixed: true }),
        el("span", { text: t.full_name })))));
  menu.hidden = false;
}

input.addEventListener("input", renderMenu);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const found = matchTeams(teams, input.value);
    if (input.value.trim() && found.length) goScout(found[0]);
  } else if (event.key === "Escape") {
    input.value = "";
    menu.hidden = true;
    input.blur();
  }
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".search")) menu.hidden = true;
});
// Press "/" anywhere (outside a text field) to jump to the search box.
document.addEventListener("keydown", (event) => {
  const typing = event.target.closest("input, textarea, select, [contenteditable]");
  if (event.key === "/" && !typing) {
    event.preventDefault();
    input.focus();
  }
});
