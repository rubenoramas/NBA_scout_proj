// "Where they give up shots": a team's opponents' shots this season, as a
// zone table against the league and a shot chart. Shared by the team page
// (Team stats tab) and the scouting Overview.

import { el, emptyLine, errorLine, fill, getJSON, pct1, skeletonRows, tag } from "./api.js";
import { chartLegend, drawShotChart } from "./shotchart.js";

function panel(span, title, note, ...body) {
  return el("section", { class: `panel ${span}`, "aria-label": title },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: title }),
      note ? el("span", { class: "panel-note", text: note }) : null),
    body);
}

// Percentage points with a sign: 0.038 -> "+3.8".
const pts = (v) => (v === null || v === undefined ? "–" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)}`);

// Opponents' FG% against the league. Green when opponents shoot below the
// league average against this team (better for this defense), red above.
// Words carry the meaning too.
function fgGap(v) {
  if (v === null || v === undefined) return el("span", { class: "muted", text: "–" });
  const word = v <= -0.01 ? "below league" : v >= 0.01 ? "above league" : "near league";
  const cls = v <= -0.01 ? "win" : v >= 0.01 ? "loss" : "text-2";
  return el("span", { class: `strong ${cls}`, text: `${pts(v)} ${word}` });
}

function shareGap(v) {
  if (v === null || v === undefined) return el("span", { class: "muted", text: "–" });
  const word = v >= 0.01 ? "more often" : v <= -0.01 ? "less often" : "about as often";
  return el("span", { class: "text-2", text: `${pts(v)} ${word}` });
}

function zoneTable(d) {
  return [
    el("div", { class: "table-scroll" }, el("div", { style: "min-width: 760px" },
      el("div", { class: "trow thead short-head cols-defzones" },
        el("span", { text: "Zone" }),
        ["Opp FGA", "Per game", "Share", "League"].map((t) => el("span", { class: "num", text: t })),
        el("span", { text: "Share vs league" }),
        ["FG% allowed", "League"].map((t) => el("span", { class: "num", text: t })),
        el("span", { text: "FG% vs league" })),
      d.zones.map((z) => el("div", { class: "trow cols-defzones" },
        el("span", { class: "strong" }, z.label, z.small_sample ? [" ", tag("Small sample", "gold")] : null),
        el("span", { class: "num text-2", text: z.fga }),
        el("span", { class: "num text-2", text: z.fga_per_game === null ? "–" : z.fga_per_game.toFixed(1) }),
        el("span", { class: "num strong", text: pct1(z.share) }),
        el("span", { class: "num text-2", text: pct1(z.league_share) }),
        el("span", {}, shareGap(z.share_vs_league)),
        el("span", { class: "num strong", text: pct1(z.fg_pct) }),
        el("span", { class: "num text-2", text: pct1(z.league_fg_pct) }),
        el("span", {}, fgGap(z.fg_vs_league)))))),
    el("p", { class: "panel-foot", text: `Opponents' shots in this team's games, ${d.season}. Share is the part of all opponent attempts from that zone. `
      + "Gaps are in percentage points. FG% below league (green) means opponents shoot worse there than the league does; above league (red), better. Zones under "
      + `${d.small_sample_fga} attempts are a small sample.` }),
  ];
}

// Returns two panels (zone table, chart) that fill themselves.
export function defenseShotPanels(team, { title = "Where they give up shots" } = {}) {
  const tableBody = el("div", {}, skeletonRows(5, [140, 40, 40, 40, 40, 120, 50, 50, 120]));
  const chartBody = el("div", { class: "chart-body" }, skeletonRows(6, [260]));
  const tableNote = el("span", { class: "panel-note" });
  const tableHead = el("div", { class: "panel-head", style: "justify-content: space-between" },
    el("h2", { class: "panel-title", text: `${title}: ${team.abbreviation}` }), tableNote);
  const tablePanel = el("section", { class: "panel span-7", "aria-label": title }, tableHead, tableBody);
  const chartPanel = panel("span-5", `Opponent shots against ${team.abbreviation}`, null, chartBody);

  async function load() {
    fill(tableBody, skeletonRows(5, [140, 40, 40, 40, 40, 120, 50, 50, 120]));
    fill(chartBody, skeletonRows(6, [260]));
    let d;
    try {
      d = await getJSON(`/api/teams/${team.team_id}/defense-shots`);
    } catch (err) {
      fill(tableBody, errorLine(err.message, load));
      fill(chartBody, emptyLine("No chart until the shots load."));
      return;
    }
    if (!d.total_fga) {
      fill(tableBody, emptyLine("No opponent shots yet this season."));
      fill(chartBody, emptyLine("No opponent shots yet this season."));
      return;
    }
    tableNote.textContent = `${d.games} games · ${d.total_fga} attempts · opponents ${pct1(d.fg_pct)}% FG (league ${pct1(d.league_fg_pct)}%)`;
    fill(tableBody, zoneTable(d));
    const made = d.shots.filter((s) => s.made).length;
    fill(chartBody,
      el("div", { class: "chart-filters", style: "border: 0; padding: 0 4px 8px" }, chartLegend(),
        el("span", { class: "muted", text: `${d.shots.length} shots, ${made} made` })),
      drawShotChart(d.shots.map((s) => ({ ...s, shot_type: "opponent shot", distance: "" })),
        { label: `Opponent shots against ${team.abbreviation}: ${d.shots.length} shots, ${made} made` }));
  }
  load();
  return [tablePanel, chartPanel];
}
