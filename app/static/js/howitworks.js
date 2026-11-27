// How it works page: fills the live parts (data date, projection record,
// current model coefficients) from the API. The rest is static text written
// from docs/SPEC.md, docs/DATA_SOURCES.md and docs/NOTES.md.

import { MY_TEAM_KEY, el, errorLine, fill, formatDay, getJSON, store } from "./api.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const pct0 = (v) => `${Math.round(v * 100)}%`;
const signed = (v, d = 2) => `${v >= 0 ? "+ " : "- "}${Math.abs(v).toFixed(d)}`;

async function freshness() {
  const note = document.getElementById("live-freshness");
  try {
    const { teams, data_as_of: asOf, pulled_at: pulled } = await loadTeams();
    setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null);
    const when = pulled ? new Date(pulled).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "unknown";
    note.textContent = `Live: games through ${asOf ? formatDay(asOf) : "unknown"}, pulled ${when}`;
  } catch (err) {
    note.textContent = "The data date could not be loaded.";
  }
}

async function record() {
  const box = document.getElementById("live-record");
  let r;
  try {
    r = await getJSON("/api/projections/record");
  } catch (err) {
    fill(box, errorLine(err.message, record));
    return;
  }
  const s = r.saved;
  const b = r.backtest;
  const m = r.model;
  fill(box,
    el("div", { class: "trow thead short-head cols-how3n" }, el("span", { text: "Record" }),
      el("span", { class: "num", text: "Average miss" }), el("span", { class: "num", text: "Winners picked" })),
    el("div", { class: "trow cols-how3n" },
      el("span", { text: `Saved before games: ${s.games} graded` }),
      el("span", { class: "num", text: s.games ? s.avg_miss.toFixed(1) : "–" }),
      el("span", { class: "num", text: s.games ? pct0(s.picked) : "–" })),
    el("div", { class: "trow cols-how3n" },
      el("span", { text: `Backtest, this season: ${b.games || 0} games (not saved live)` }),
      el("span", { class: "num", text: b.games ? b.avg_miss.toFixed(1) : "–" }),
      el("span", { class: "num", text: b.games ? pct0(b.picked) : "–" })),
    s.games ? null : el("p", { class: "muted", style: "margin-top: 6px", text: "No saved projection has been graded yet: the record starts with the games played after the first pull that saved projections." }));
  // The coefficients as the app uses them now (trained on last season).
  const f = document.getElementById("live-formula");
  if (m && m.beta) {
    const x = m.beta;
    f.textContent = `margin = ${x.home_court.toFixed(2)} ${signed(x.net_diff, 3)} x (home net - away net) ${signed(x.rest_diff)} x (home rest - away rest) `
      + `${signed(x.b2b_home)} x home back-to-back ${signed(x.b2b_away)} x away back-to-back`;
    f.title = `Live: trained on ${m.train_season}, ${m.games} games, K = ${m.k}, average miss ${m.avg_miss}, standard deviation ${m.sigma}.`;
  }
}

freshness();
record();
