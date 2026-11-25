// Game preview pieces: the projection line, its note, and the running
// record of saved projections. A projection, not a promise: no wagering
// language, and the average miss is always shown beside it.

import { el, formatDay, getJSON, tag } from "./api.js";

export const PROJECTION_NOTE = "A projection from net ratings, home court and rest, not a certainty: "
  + "single games swing a lot, and the model misses the final margin by about 11 points on average.";

const pct0 = (v) => `${Math.round(v * 100)}%`;

// "Projected: BOS by 5.1 · 64% win probability · average miss 11 points"
export function projectionText(p) {
  return `Projected: ${p.favorite} by ${p.by.toFixed(1)} · ${pct0(p.favorite_win_prob)} win probability · average miss ${p.avg_miss} points`;
}

export function projectionLine(p, { cls = "proj-line" } = {}) {
  if (!p) return null;
  const tip = `${p.home} net ${p.inputs.home_net > 0 ? "+" : ""}${p.inputs.home_net} (${p.inputs.home_games} games), `
    + `${p.away} net ${p.inputs.away_net > 0 ? "+" : ""}${p.inputs.away_net} (${p.inputs.away_games} games). `
    + `Rest: ${p.home} ${p.inputs.home_rest}${p.inputs.home_b2b ? " (back-to-back)" : ""} day(s), ${p.away} ${p.inputs.away_rest}${p.inputs.away_b2b ? " (back-to-back)" : ""}. `
    + `The win probability uses the typical size of the model's misses (standard deviation ${p.sigma} points). ${PROJECTION_NOTE}`;
  return el("div", { class: cls, title: tip }, projectionText(p));
}

// Saved projection beside the real result, for a played game.
export function savedVersusResult(s) {
  if (!s || !s.final) return null;
  const actual = s.actual_home_margin;
  const winner = actual > 0 ? s.home : s.away;
  const projMargin = s.home_margin;
  const miss = Math.abs(actual - projMargin);
  const right = (projMargin >= 0) === (actual > 0);
  return el("div", { class: "proj-line" },
    `Projected before the game: ${s.favorite} by ${s.by.toFixed(1)} (${pct0(s.favorite_win_prob)}). `,
    `Result: ${winner} by ${Math.abs(actual)}. Missed by ${miss.toFixed(1)}. `,
    tag(right ? "Winner picked" : "Winner missed", right ? "accent" : ""));
}

// The record panel body: saved projections (all games), the team's latest
// graded games, and the backtest, clearly labeled.
export async function fillRecord(body, teamId) {
  const r = await getJSON(`/api/projections/record?team=${teamId}`);
  const s = r.saved;
  const b = r.backtest;
  const rows = [
    el("div", { class: "side-line" },
      el("span", { class: "muted", text: "Saved before games" }),
      el("span", { text: s.games
        ? `${s.games} games · average miss ${s.avg_miss} · winner picked ${pct0(s.picked)}`
        : "None graded yet. Each data pull saves projections, and they are graded once the games are played." })),
  ];
  for (const g of r.team_recent || []) {
    rows.push(el("div", { class: "side-line" },
      el("span", { class: "muted", text: `${formatDay(g.date, { month: "short", day: "numeric" })} ${g.away} at ${g.home}` }),
      el("span", {}, `${g.favorite} by ${g.by.toFixed(1)} · ${g.winner} won ${Math.max(g.home_pts, g.away_pts)}-${Math.min(g.home_pts, g.away_pts)} · miss ${g.miss}`)));
  }
  if (b && b.games) {
    rows.push(el("div", { class: "side-line" },
      el("span", { class: "muted" }, "Backtest ", tag("Not saved live")),
      el("span", { text: `${b.games} games this season · average miss ${b.avg_miss} · winner picked ${pct0(b.picked)}` })));
  }
  rows.push(el("p", { class: "panel-foot", text: `The backtest runs the model on this season's played games using only data from before each game; it was not saved ahead of time. ${PROJECTION_NOTE}` }));
  body.replaceChildren(...rows);
}
