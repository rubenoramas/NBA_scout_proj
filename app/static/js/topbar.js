// Top bar shared by every page: team switcher, main navigation, team
// search and the "data as of" date.

import { MY_TEAM_KEY, chip, el, fill, formatDay, getJSON, postJSON, scoutUrl, store } from "./api.js";

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
    ? "The data was pulled more than 2 days ago. Use Refresh data, or run ./refresh.sh."
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

// Mark "Saved reports" as the current page on /reports and /reports/<id>.
if (window.location.pathname.startsWith("/reports")) {
  const link = document.getElementById("nav-reports");
  if (link) link.setAttribute("aria-current", "page");
}

// ---- Refresh data button ---------------------------------------------------
// Starts a refresh job (R pulls in the optional refresher container, then a
// database reload), shows the current step, polls the status, and updates
// the freshness line and a row-count summary in place when it is done.

const POLL_MS = 2000;
const refreshBtn = document.getElementById("refresh-btn");
const refreshWrap = document.getElementById("refresh-wrap");
const refreshPanel = document.getElementById("refresh-panel");
const refreshHelp = document.getElementById("refresh-help");
let pollTimer = null;

function setRefreshHelp(text) {
  refreshWrap.title = text || "";
  refreshHelp.textContent = text || "";
}

function closeButton() {
  const b = el("button", { type: "button", class: "btn btn-small", text: "Close" });
  b.addEventListener("click", () => { refreshPanel.hidden = true; refreshBtn.focus(); });
  return b;
}

function showPanel(...children) {
  fill(refreshPanel, ...children);
  refreshPanel.hidden = false;
}

function runningState(step) {
  refreshBtn.disabled = true;
  refreshBtn.textContent = step || "Refreshing...";
  setRefreshHelp("A refresh is running. It usually takes a few minutes.");
}

function idleState() {
  refreshBtn.disabled = false;
  refreshBtn.textContent = "Refresh data";
  setRefreshHelp("Run the R pulls and reload the database. Takes a few minutes.");
}

function showDone(job) {
  idleState();
  if (job.freshness) showFreshness(job.freshness.data_as_of, job.freshness.pulled_at);
  const rows = job.changes || [];
  const sign = (n) => (n > 0 ? `+${n}` : String(n));
  showPanel(
    el("h3", { text: "Data refreshed" }),
    rows.length
      ? el("div", { class: "refresh-table" },
        ["Collection", "Before", "After", "Change"].map((t) => el("span", { class: "refresh-head", text: t })),
        rows.flatMap((r) => [el("span", { text: r.collection }), el("span", { text: r.before.toLocaleString() }),
          el("span", { text: r.after.toLocaleString() }), el("span", { class: r.change < 0 ? "loss" : "", text: sign(r.change) })]))
      : el("p", { text: "No row counts changed. The data was already up to date." }),
    el("p", { class: "muted", text: "Reload a page to see the new numbers. The seed files in data/seed/ changed; commit them only at milestones." }),
    el("div", { class: "actions" }, closeButton()));
}

function showFailed(message) {
  idleState();
  const retry = el("button", { type: "button", class: "btn btn-small", text: "Try again" });
  retry.addEventListener("click", startRefresh);
  showPanel(el("h3", { class: "loss", text: "Refresh failed" }), el("p", { text: message }),
    el("div", { class: "actions" }, retry, closeButton()));
}

async function poll(jobId) {
  clearTimeout(pollTimer);
  let job;
  try {
    job = await getJSON(`/api/refresh/${jobId}`);
  } catch (err) {
    // A slow answer is not a failed refresh: keep polling, say so quietly.
    runningState("Checking...");
    pollTimer = setTimeout(() => poll(jobId), POLL_MS * 2);
    return;
  }
  if (job.state === "done") { showDone(job); return; }
  if (job.state === "failed") { showFailed(job.error); return; }
  runningState(job.step_note || job.step);
  pollTimer = setTimeout(() => poll(jobId), POLL_MS);
}

async function startRefresh() {
  refreshPanel.hidden = true;
  runningState("Starting...");
  try {
    const job = await postJSON("/api/refresh", {});
    poll(job.job_id);
  } catch (err) {
    // Already running, for example from another tab: follow that job.
    const status = await getJSON("/api/refresh/status").catch(() => null);
    if (status && status.job) { poll(status.job.job_id); return; }
    showFailed(err.message);
  }
}

async function initRefresh() {
  if (!refreshBtn) return;
  refreshBtn.addEventListener("click", startRefresh);
  let status;
  try {
    status = await getJSON("/api/refresh/status");
  } catch {
    setRefreshHelp("Could not check whether the refresher is running.");
    return;
  }
  if (status.job) { poll(status.job.job_id); return; } // resume a job started earlier
  if (!status.refresher) {
    refreshBtn.disabled = true;
    setRefreshHelp(status.how_to_start);
    return;
  }
  idleState();
}
initRefresh();
