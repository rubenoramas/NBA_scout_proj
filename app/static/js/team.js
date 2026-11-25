// Team page: /team/<abbreviation>, with Roster and Team stats tabs.

import { defenseShotPanels } from "./defshots.js";
import {
  MY_TEAM_KEY, chip, el, emptyLine, errorLine, fill, getJSON, rankText, scoutUrl, seedText,
  shortStreak, skeletonRows, store, streakClass,
} from "./api.js";
import { newRosterState, renderRoster } from "./roster.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const band = document.getElementById("band-team");
const root = document.getElementById("team");
const actions = document.getElementById("team-actions");
const abbr = decodeURIComponent(window.location.pathname.split("/").filter(Boolean).pop() || "").toUpperCase();
const params = new URLSearchParams(window.location.search);
const activeTab = params.get("tab") === "stats" ? "stats" : "roster";
const rosterState = newRosterState();

for (const tab of ["roster", "stats"]) {
  const link = document.getElementById(`tab-${tab}`);
  link.setAttribute("href", tab === "roster" ? `/team/${abbr}` : `/team/${abbr}?tab=stats`);
  if (tab === activeTab) link.setAttribute("aria-current", "page");
}

function panel(span, title, note, ...body) {
  return el("section", { class: `panel ${span}`, "aria-label": title },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: title }),
      note ? el("span", { class: "panel-note", text: note }) : null),
    body);
}

function showProblem(message, retry) {
  fill(band, el("p", { class: "muted", style: "padding-bottom: 4px", text: "No team to show." }));
  fill(root, el("section", { class: "panel span-12" },
    retry ? errorLine(message, retry)
      : el("div", { class: "state-error", role: "alert" },
        el("span", { text: message }),
        el("a", { class: "btn", href: "/", text: "Back to schedule" }))));
}

async function load() {
  fill(band, el("div", { class: "band-side" }, skeletonRows(2, [60, 200])));
  fill(root, panel("span-12", activeTab === "roster" ? "Roster" : "Team stats", null,
    skeletonRows(10, [180, 40, 40, 50, 50, 50, 50])));
  let team;
  try {
    const { teams } = await loadTeams();
    const mine = teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY));
    setSwitcher(mine || null);
    team = teams.find((t) => t.abbreviation === abbr);
    if (!team) {
      showProblem(`No NBA team uses the abbreviation ${abbr || "(none)"}.`);
      return;
    }
    document.title = `${team.full_name} | Opponent Scout`;
    // A Scout link from your team to this one, when it is not your team.
    fill(actions, mine && mine.team_id !== team.team_id
      ? el("a", { class: "btn btn-primary", href: scoutUrl(mine.abbreviation, team.abbreviation), text: `Scout ${team.abbreviation}` })
      : null);
    const overview = await getJSON(`/api/teams/${team.team_id}`);
    renderBand(overview);
    if (activeTab === "stats") renderStats(overview);
    else await renderRosterTab(team);
  } catch (err) {
    showProblem(err.message, load);
  }
}

function renderBand(o) {
  const s = o.standing || {};
  fill(band,
    el("div", { class: "band-side" },
      chip(o.team.abbreviation, { xl: true }),
      el("div", {},
        el("div", { class: "label", text: `${o.team.conference}ern Conference · ${o.team.division}` }),
        el("h1", { class: "band-name", style: "font-size: 16px; margin: 0", text: o.team.full_name }),
        el("div", { class: "band-sub", text: o.season ? `${o.season} season` : "" }))),
    el("div", { class: "measures" },
      measure("Record", s.record),
      measure("Seed", seedText(s)),
      measure("Streak", shortStreak(s.streak), streakClass(s.streak)),
      measure("Last 10", s.last_ten),
      measure("Home", s.home_record),
      measure("Road", s.road_record)));
}

function measure(label, value, cls = "") {
  return el("div", { class: "measure" },
    el("div", { class: "label", text: label }),
    el("div", { class: `measure-value ${cls}`, text: value || "–" }));
}

async function renderRosterTab(team) {
  const body = el("div");
  fill(root, panel("span-12", `${team.full_name} roster`, "Per game · sorted by USG% · click a name for the player card", body));
  fill(body, skeletonRows(10, [180, 40, 40, 50, 50, 50, 50]));
  try {
    const data = await getJSON(`/api/teams/${team.team_id}/roster`);
    renderRoster(body, data.players, rosterState, `${team.full_name} roster`);
  } catch (err) {
    fill(body, errorLine(err.message, () => renderRosterTab(team)));
  }
}

function renderStats(o) {
  const ts = o.team_stats;
  if (!ts) {
    fill(root, panel("span-12", "Team stats", null, emptyLine("No team stats are loaded for this team.")));
    return;
  }
  const byKey = Object.fromEntries(ts.stats.map((s) => [s.key, s]));
  const fmt = (s) => {
    if (s.value === null || s.value === undefined) return "–";
    if (s.key.endsWith("_pct")) return (s.value * 100).toFixed(1);
    if (s.key.endsWith("fta_rate")) return s.value.toFixed(3);
    return s.value.toFixed(1);
  };
  const rankCls = (s) => (!s.rank || s.key === "pace" ? "text-2" : s.rank <= 5 ? "win" : s.rank > s.of - 5 ? "loss" : "text-2");
  const table = (keys) => [
    el("div", { class: "trow thead short-head cols-teamstats" },
      el("span", { text: "Stat" }), el("span", { class: "num", text: "Value" }), el("span", { class: "num", text: "Rank" }),
      el("span", { text: "What it means" })),
    keys.map((k) => {
      const s = byKey[k];
      return el("div", { class: "trow cols-teamstats" },
        el("span", { class: "strong", text: s.label }),
        el("span", { class: "num strong", text: fmt(s) }),
        el("span", { class: `num ${rankCls(s)}`, text: s.rank ? `${rankText(s.rank)} of ${s.of}` : "–" }),
        el("span", { class: "muted", text: s.help }));
    }),
  ];
  fill(root,
    panel("span-12", "Ratings and pace", `${ts.gp} games · ranks 1st = best, except pace (1st = fastest)`,
      table(["off_rating", "def_rating", "net_rating", "pace"])),
    panel("span-6", "Four factors: offense", null, table(["efg_pct", "tov_pct", "oreb_pct", "fta_rate"])),
    panel("span-6", "Four factors: defense", null, table(["opp_efg_pct", "opp_tov_pct", "opp_oreb_pct", "opp_fta_rate"])),
    el("p", { class: "muted span-12", text: "From the NBA's team stats files, regular season. Top five ranks in green, bottom five in red." }),
    defenseShotPanels(o.team));
}

load();
