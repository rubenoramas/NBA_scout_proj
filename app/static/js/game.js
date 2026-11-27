// Box score page: /game/<game_id>

import { savedVersusResult } from "./projection.js";
import { MY_TEAM_KEY, SEASON_TYPE_LABEL, chip, el, emptyLine, errorLine, fill, formatDay, getJSON, howLink, skeletonRows, store, tag, logError } from "./api.js";
import { defaultState, nextSort, renderBoxTable } from "./boxtable.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const band = document.getElementById("band-teams");
const root = document.getElementById("game");
const gameId = window.location.pathname.split("/").filter(Boolean).pop();
const segButtons = [...document.querySelectorAll(".seg button")];
document.getElementById("tab-box").setAttribute("href", window.location.pathname);

let data = null;
const state = defaultState();

function panel(span, title, note, ...body) {
  return el("section", { class: `panel ${span}`, "aria-label": title },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: title }),
      note ? (note instanceof Node ? note : el("span", { class: "panel-note", text: note })) : null),
    body);
}

function showLoading() {
  fill(band, el("div", { class: "band-side" }, skeletonRows(2, [60, 160])));
  fill(root,
    panel("span-12", "Away", null, skeletonRows(8, [180, 40, 40, 60, 40, 60, 40])),
    panel("span-12", "Home", null, skeletonRows(8, [180, 40, 40, 60, 40, 60, 40])));
}

function showProblem(message, retry) {
  fill(band, el("p", { class: "muted", style: "padding-bottom: 4px", text: "No game to show." }));
  fill(root, el("section", { class: "panel span-12" },
    retry ? errorLine(message, retry)
      : el("div", { class: "state-error", role: "alert" },
        el("span", { text: message }),
        el("a", { class: "btn", href: "/", text: "Back to schedule" }))));
}

async function load() {
  showLoading();
  // The top bar team switcher does not depend on this game.
  loadTeams().then(({ teams }) => {
    setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null);
  }).catch((err) => logError("Top bar team list", err));
  try {
    data = await getJSON(`/api/games/${encodeURIComponent(gameId)}/boxscore`);
  } catch (err) {
    // 400 and 404 come with a message that explains the problem; a retry
    // will not help those, so offer the way back instead.
    const permanent = /10 digits|No game has|not been played/.test(err.message);
    showProblem(err.message, permanent ? null : load);
    return;
  }
  const away = data.away.team.abbreviation;
  const home = data.home.team.abbreviation;
  document.title = `${away} at ${home}, ${formatDay(data.game.date)} | Opponent Scout`;
  render();
  // The projection saved before this game, if a pull saved one.
  getJSON(`/api/games/${encodeURIComponent(gameId)}/projection`).then((p) => {
    const line = savedVersusResult(p.saved);
    if (line) document.querySelector(".band-mid").append(line);
  }).catch((err) => logError("Saved projection for this game", err));
}

// ---- Band -------------------------------------------------------------

function bandSide(side, label, right) {
  const won = side.pts > (side === data.away ? data.home.pts : data.away.pts);
  const info = el("div", {},
    el("div", { class: "label", text: label }),
    el("div", { class: "band-name", text: side.team.full_name || side.team.abbreviation }),
    el("div", { class: "band-sub" }, el("span", { class: `strong ${won ? "win" : "loss"}`, text: won ? "W" : "L" })));
  const abbr = chip(side.team.abbreviation, { xl: true, link: true });
  return el("div", { class: `band-side${right ? " right" : ""}` }, right ? [info, abbr] : [abbr, info]);
}

function renderBand() {
  const g = data.game;
  const type = g.season_type !== "regular-season"
    ? tag(SEASON_TYPE_LABEL[g.season_type] || g.season_type, g.season_type === "nba-cup" ? "gold" : "accent")
    : null;
  fill(band,
    bandSide(data.away, "AWAY", false),
    el("div", { class: "band-mid" },
      el("div", { class: "band-score" },
        el("span", { class: data.away.pts > data.home.pts ? "" : "muted", text: data.away.pts }),
        el("span", { class: "muted", text: " - " }),
        el("span", { class: data.home.pts > data.away.pts ? "" : "muted", text: data.home.pts })),
      el("div", { class: "muted", style: "margin-top: 2px" },
        `Final · ${formatDay(g.date, { weekday: "short", month: "short", day: "numeric", year: "numeric" })} · at ${g.venue} · ${g.season}`,
        type ? [" ", type] : null)),
    bandSide(data.home, "HOME", true));
}

// ---- Panels -----------------------------------------------------------

function teamPanel(side) {
  const body = el("div");
  const won = side.pts > (side === data.away ? data.home.pts : data.away.pts);
  const p = panel("span-12", `${side.team.full_name || side.team.abbreviation}`, `${side.home ? "Home" : "Away"} · ${won ? "W" : "L"} ${side.pts}`, body);
  renderBoxTable(body, side, state, {
    onSort: (key) => {
      nextSort(state, key);
      renderPanels();
    },
  });
  return p;
}

function factorsPanel() {
  const rows = [
    ["eFG%", "efg_pct", "Higher is better"],
    ["TOV%", "tov_pct", "Lower is better"],
    ["OREB%", "oreb_pct", "Higher is better"],
    ["FT rate", "ft_rate", "Higher is better"],
  ];
  const a = data.away.four_factors;
  const h = data.home.four_factors;
  if (!a || !h) return panel("span-5", "Four factors", "This game", emptyLine("No player lines, so no four factors."));
  const fmt = (v, key) => (v === null || v === undefined ? "–" : key === "ft_rate" ? v.toFixed(3) : (v * 100).toFixed(1));
  const better = (key, va, vh) => {
    if (va === null || vh === null || va === vh) return ["", ""];
    const awayBetter = key === "tov_pct" ? va < vh : va > vh;
    return awayBetter ? ["win", ""] : ["", "win"];
  };
  return panel("span-5", "Four factors", "This game",
    el("div", { class: "trow thead cols-factors short-head" },
      el("span"), el("span", { class: "num", text: data.away.team.abbreviation }), el("span", { class: "num", text: data.home.team.abbreviation }),
      el("span", { class: "num", text: "" })),
    rows.map(([label, key, hint]) => {
      const [ca, ch] = better(key, a[key], h[key]);
      return el("div", { class: "trow cols-factors", style: "min-height: 34px" },
        el("span", { class: "muted", text: label }),
        el("span", { class: `num strong ${ca}`, text: fmt(a[key], key) }),
        el("span", { class: `num strong ${ch}`, text: fmt(h[key], key) }),
        el("span", { class: "num muted", text: hint }));
    }));
}

function howPanel() {
  const formulas = [
    ["TS%", "PTS / (2 x (FGA + 0.44 x FTA))"],
    ["eFG%", "(FGM + 0.5 x 3PM) / FGA"],
    ["USG%", "100 x (FGA + 0.44 x FTA + TOV) x (team MIN / 5) / (MIN x (team FGA + 0.44 x team FTA + team TOV))"],
    ["GmSc", "PTS + 0.4 FGM - 0.7 FGA - 0.4 (FTA - FTM) + 0.7 OREB + 0.3 DREB + STL + 0.7 AST + 0.7 BLK - 0.4 PF - TOV"],
    ["AST/TOV", "AST / TOV, left empty when TOV is 0"],
    ["TOV%", "TOV / (FGA + 0.44 x FTA + TOV)"],
    ["OREB%", "OREB / (OREB + opponent DREB)"],
    ["FT rate", "FTA / FGA"],
  ];
  const notes = [
    "Minutes in the data are whole numbers, so USG% is slightly rounded.",
    "USG% means the same thing on player cards: his share of the team's plays while on the floor. The season value there is the NBA's own, which counts team plays actually on the floor; this formula estimates them from minutes and runs about 0.7 points higher on average.",
    "OREB% counts player rebounds only. Team rebounds are not in the player lines.",
    data.starters_known ? "Starters (S) are the five players on the floor at the first play of the game."
      : "Starters could not be identified for this game.",
  ];
  return panel("span-7", "How these are calculated", howLink("data", "All methods"),
    formulas.map(([name, f]) => el("div", { class: "trow cols-formula", style: "min-height: 32px" },
      el("span", { class: "strong", text: name }),
      el("code", { class: "formula", text: f }))),
    el("ul", { class: "panel-notes" }, notes.map((n) => el("li", { text: n }))));
}

function renderPanels() {
  if (!data.has_lines) {
    fill(root, panel("span-12", "Box score", null,
      emptyLine("Player lines for this game are not in the data. The NBA stats game log file does not include play-in games or the NBA Cup final, so only the final score is shown.")));
    return;
  }
  const panels = [teamPanel(data.away), teamPanel(data.home)];
  if (state.mode === "advanced") panels.push(factorsPanel(), howPanel());
  fill(root, panels);
}

function render() {
  renderBand();
  renderPanels();
}

for (const btn of segButtons) {
  btn.addEventListener("click", () => {
    state.mode = btn.dataset.mode;
    for (const b of segButtons) b.setAttribute("aria-pressed", String(b === btn));
    // Keep the sort if the column exists in the new view, else go back to points.
    const keys = ["player_name", "min", "pts", ...(state.mode === "basic"
      ? ["fgm", "fg_pct", "fg3m", "fg3_pct", "ftm", "ft_pct", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "plus_minus"]
      : ["ts_pct", "efg_pct", "usg_pct", "game_score", "ast_tov"])];
    if (!keys.includes(state.sortKey)) Object.assign(state, { sortKey: "pts", sortDir: "desc" });
    if (data) renderPanels();
  });
}

load();
