// The suggested matchups table, shared by the scouting page (live) and the
// saved report page (from its snapshot).

import { el, howLink, tag } from "./api.js";

// Lead with the effect against the scorer's norm: negative is good for us.
export function normEffect(m) {
  const v = m.vs_norm_per100;
  if (Math.abs(v) < 0.05) return el("span", { class: "text-2", text: "matches his norm" });
  return el("span", { class: `strong ${v < 0 ? "win" : "loss"}` },
    v < 0 ? `holds him ${Math.abs(v).toFixed(1)} below his norm` : `allows ${v.toFixed(1)} above his norm`);
}

function historyCell(m) {
  return el("span", { class: "history-cell" },
    el("span", { class: "text-2", text: `${Math.round(m.history_poss)} poss` }),
    m.small_history ? tag("Small sample", "gold") : null);
}

function statusTag(status) {
  if (!status || status === "Available") return null;
  return tag(status, status === "Out" ? "loss" : status === "Doubtful" || status === "Questionable" ? "gold" : "");
}

// The lineups line above the table. saved: true for a saved report, where
// "set in the Lineups tab" would not make sense.
export function lineupLine(data, usAbbr, themAbbr, { saved = false } = {}) {
  const line = (abbr, lineup, isDefault) => el("p", { class: "lineup-line" },
    el("span", { class: "label", text: `${abbr} ` }),
    lineup.map((p, i) => [i ? ", " : "", p.player_name, statusTag(p.status) ? [" ", statusTag(p.status)] : null]),
    isDefault ? el("span", { class: "muted", text: " (default: most common starters, Out and Doubtful players replaced)" })
      : saved ? null : el("span", { class: "muted", text: " (set in the Lineups tab)" }));
  return el("div", { class: "matchup-notes" },
    line(usAbbr, data.us_lineup, data.us_default),
    line(themAbbr, data.them_lineup, data.them_default));
}

// Who guarded this scorer most in the last meeting, from the matchup data.
// Saved reports made before this column existed have no last_meeting.
function lastMeetingCell(data, r) {
  const lm = data.last_meeting;
  if (!lm || !lm.game) return el("span", { class: "muted", text: lm ? "No meeting yet" : "–" });
  if (!lm.has_data) return el("span", { class: "muted", text: "No matchup data" });
  const g = r.last_meeting;
  if (!g) return el("span", { class: "muted", text: "Did not play" });
  return el("span", { class: "lm-cell", title: `${g.poss} of his ${g.scorer_poss} partial possessions; ${g.pts} points against him` },
    el("a", { class: "name-link", href: `/player/${g.defender_id}`, text: g.defender_name }),
    el("span", { class: "text-2", text: `${Math.round(g.poss)} poss` }),
    g.still_with_us ? null : tag("Not on roster"));
}

export function matchupTable(data) {
  const lmDate = data.last_meeting && data.last_meeting.game
    ? new Date(`${data.last_meeting.game.date}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null;
  const header = el("div", { class: "trow thead short-head cols-matchups" },
    el("span", { text: "Their player" }), el("span", { class: "num", text: "USG%" }),
    el("span", { text: "Our defender" }),
    el("span", { title: lmDate ? `Last meeting, ${lmDate}` : null, text: lmDate ? `Guarded most, ${lmDate}` : "Guarded most, last meeting" }),
    el("span", { text: "Effect vs his norm" }),
    el("span", { class: "num", text: "Exp / 100" }), el("span", { class: "num", text: "History" }));
  const rows = data.rows.map((r) => {
    const a = r.assigned;
    const options = r.top_three.map((o) => el("span", { class: "option" },
      el("a", { class: "name-link", href: `/player/${o.defender_id}`, text: o.defender_name }),
      el("span", { class: o.vs_norm_per100 < 0 ? "win" : "loss", text: ` ${o.vs_norm_per100 > 0 ? "+" : ""}${o.vs_norm_per100.toFixed(1)}` })));
    return el("div", { class: "matchup-block" },
      el("div", { class: "trow cols-matchups tall" },
        el("span", { class: "player-cell" },
          el("a", { class: "name-link", href: `/player/${r.scorer_id}`, text: r.scorer_name }),
          r.position ? el("span", { class: "muted", text: r.position }) : null),
        el("span", { class: "num strong", text: r.usg_pct.toFixed(1) }),
        el("span", { class: "player-cell" },
          el("a", { class: "name-link", href: `/player/${a.defender_id}`, text: a.defender_name }),
          a.position ? el("span", { class: "muted", text: a.position }) : null),
        el("span", {}, lastMeetingCell(data, r)),
        el("span", {}, normEffect(a)),
        el("span", { class: "num text-2", text: a.expected_per100.toFixed(1) }),
        el("span", { class: "num" }, historyCell(a))),
      el("div", { class: "matchup-detail" },
        el("p", { class: "muted", text: a.reason }),
        el("p", { class: "matchup-options" }, el("span", { class: "label", text: "Top three from our roster " }),
          options.length ? options : el("span", { class: "muted", text: "No eligible defenders." }))));
  });
  return el("div", { class: "table-scroll" }, el("div", { style: "min-width: 1080px" }, header, rows));
}

export function matchupNotes(data) {
  const size = data.size_fit;
  return el("div", { class: "panel-foot matchup-foot" },
    el("p", { text: data.notes.unit }),
    el("p", { text: `Effect vs his norm is the expected points minus his norm, per 100. Green means our defender holds him below what he usually scores. Guards and centers are not matched against each other without ${data.position_guard.min_history}+ possessions of history.` }),
    el("p", { text: `Size (height, weight, wingspan gaps) explains ${(size.share_of_leftover_explained * 100).toFixed(1)}% of what is left after his norm and the defender's effect, so it barely moves the numbers.` }),
    el("p", { class: "strong", text: data.notes.noise }),
    el("p", {}, howLink("matchups", "How the matchup model works")));
}
