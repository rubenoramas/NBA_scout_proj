// Box score table for one team: sortable columns, starters tag, and a team
// totals row pinned to the bottom. Used by the box score page and by the
// "Last game" tab on the schedule.

import { el, emptyLine, tag } from "./api.js";

const dash = "–";
const fmtInt = (v) => (v === null || v === undefined ? dash : String(v));
const fmtPct = (v) => (v === null || v === undefined ? dash : (v * 100).toFixed(1));
const fmtDec = (v, d = 1) => (v === null || v === undefined ? dash : Number(v).toFixed(d));
const fmtPlus = (v) => (v === null || v === undefined ? dash : v > 0 ? `+${v}` : String(v));
const made = (m, a) => (line) => `${line[m]}-${line[a]}`;

// Each column: key to sort by, header label, how to show a player line,
// and how to show the totals row (null = blank).
export const COLUMNS = {
  basic: [
    { key: "min", label: "MIN", show: (l) => fmtInt(l.min), total: (t) => fmtInt(t.min) },
    { key: "pts", label: "PTS", show: (l) => fmtInt(l.pts), total: (t) => fmtInt(t.pts), strong: true },
    { key: "fgm", label: "FGM-FGA", show: made("fgm", "fga"), total: made("fgm", "fga"), wide: true },
    { key: "fg_pct", label: "FG%", show: (l) => fmtPct(l.fg_pct), total: (t) => fmtPct(t.fg_pct) },
    { key: "fg3m", label: "3PM-3PA", show: made("fg3m", "fg3a"), total: made("fg3m", "fg3a"), wide: true },
    { key: "fg3_pct", label: "3P%", show: (l) => fmtPct(l.fg3_pct), total: (t) => fmtPct(t.fg3_pct) },
    { key: "ftm", label: "FTM-FTA", show: made("ftm", "fta"), total: made("ftm", "fta"), wide: true },
    { key: "ft_pct", label: "FT%", show: (l) => fmtPct(l.ft_pct), total: (t) => fmtPct(t.ft_pct) },
    { key: "oreb", label: "OREB", show: (l) => fmtInt(l.oreb), total: (t) => fmtInt(t.oreb) },
    { key: "dreb", label: "DREB", show: (l) => fmtInt(l.dreb), total: (t) => fmtInt(t.dreb) },
    { key: "reb", label: "REB", show: (l) => fmtInt(l.reb), total: (t) => fmtInt(t.reb) },
    { key: "ast", label: "AST", show: (l) => fmtInt(l.ast), total: (t) => fmtInt(t.ast) },
    { key: "stl", label: "STL", show: (l) => fmtInt(l.stl), total: (t) => fmtInt(t.stl) },
    { key: "blk", label: "BLK", show: (l) => fmtInt(l.blk), total: (t) => fmtInt(t.blk) },
    { key: "tov", label: "TOV", show: (l) => fmtInt(l.tov), total: (t) => fmtInt(t.tov) },
    { key: "pf", label: "PF", show: (l) => fmtInt(l.pf), total: (t) => fmtInt(t.pf) },
    { key: "plus_minus", label: "+/-", show: (l) => fmtPlus(l.plus_minus), total: () => null },
  ],
  advanced: [
    { key: "min", label: "MIN", show: (l) => fmtInt(l.min), total: (t) => fmtInt(t.min) },
    { key: "pts", label: "PTS", show: (l) => fmtInt(l.pts), total: (t) => fmtInt(t.pts), strong: true },
    { key: "ts_pct", label: "TS%", show: (l) => fmtPct(l.ts_pct), total: (t) => fmtPct(t.ts_pct) },
    { key: "efg_pct", label: "eFG%", show: (l) => fmtPct(l.efg_pct), total: (t) => fmtPct(t.efg_pct) },
    { key: "usg_pct", label: "USG%", show: (l) => fmtDec(l.usg_pct), total: () => null },
    { key: "game_score", label: "GmSc", show: (l) => fmtDec(l.game_score), total: () => null, strong: true },
    { key: "ast_tov", label: "AST/TOV", show: (l) => fmtDec(l.ast_tov, 2), total: (t) => fmtDec(t.ast_tov, 2), wide: true },
  ],
};

function gridTemplate(columns) {
  return `minmax(190px, 1fr) ${columns.map((c) => (c.wide ? "76px" : "54px")).join(" ")}`;
}

function sortValue(line, key) {
  if (key === "player_name") return (line.player_name || "").toLowerCase();
  const v = line[key];
  return v === null || v === undefined ? -Infinity : v;
}

// Render one team's table into `container`. State (mode and sort) lives in
// `state` so the caller can share it, for example across both teams.
export function renderBoxTable(container, side, state, { onSort, starterNote = true } = {}) {
  const columns = COLUMNS[state.mode];
  const template = gridTemplate(columns);
  const minWidth = 190 + columns.reduce((sum, c) => sum + (c.wide ? 76 : 54) + 8, 0) + 32;

  if (!side.players.length) {
    container.replaceChildren(emptyLine("Player lines for this game are not in the data."));
    return;
  }

  const sorted = [...side.players].sort((a, b) => {
    const va = sortValue(a, state.sortKey);
    const vb = sortValue(b, state.sortKey);
    const order = va < vb ? -1 : va > vb ? 1 : 0;
    return state.sortDir === "asc" ? order : -order;
  });

  const headerCell = (key, label, alignRight) => {
    const active = state.sortKey === key;
    const ariaSort = active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none";
    return el("span", { role: "columnheader", "aria-sort": ariaSort, class: alignRight ? "num" : "" },
      el("button", {
        type: "button",
        class: `sort-btn${active ? " active" : ""}`,
        onclick: () => onSort && onSort(key),
        "aria-label": `Sort by ${label}`,
      }, label, active ? el("span", { "aria-hidden": "true", text: state.sortDir === "asc" ? " ▲" : " ▼" }) : null));
  };

  const header = el("div", { class: "trow thead short-head", role: "row", style: `grid-template-columns: ${template}` },
    headerCell("player_name", "Player", false),
    columns.map((c) => headerCell(c.key, c.label, true)));

  const rows = sorted.map((line) =>
    el("div", { class: "trow", role: "row", style: `grid-template-columns: ${template}` },
      el("span", { role: "cell", class: "player-cell" },
        el("a", { class: "name-link", href: `/player/${line.player_id}`, text: line.player_name }),
        line.starter ? tag("S") : null),
      columns.map((c) => el("span", { role: "cell", class: `num${c.strong ? " strong" : " text-2"}`, text: c.show(line) }))));

  const totals = side.totals
    ? el("div", { class: "trow totals-row", role: "row", style: `grid-template-columns: ${template}` },
      el("span", { role: "cell", class: "bold", text: "Team totals" }),
      columns.map((c) => el("span", { role: "cell", class: "num bold", text: c.total(side.totals) ?? "" })))
    : null;

  container.replaceChildren(
    el("div", { class: "table-scroll" },
      el("div", { role: "table", "aria-label": `${side.team.full_name || side.team.abbreviation} box score`, style: `min-width: ${minWidth}px` },
        header, rows, totals)),
    starterNote && side.players.some((l) => l.starter) ? el("p", { class: "panel-foot", text: "S = starter" }) : null);
}

// Default sort: points, high to low.
export function defaultState(mode = "basic") {
  return { mode, sortKey: "pts", sortDir: "desc" };
}

// Clicking a header sorts by it; clicking the same header again flips the
// direction. Names sort A to Z first, numbers high to low first.
export function nextSort(state, key) {
  if (state.sortKey === key) {
    state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  } else {
    state.sortKey = key;
    state.sortDir = key === "player_name" ? "asc" : "desc";
  }
  return state;
}
