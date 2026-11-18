// Player card: /player/<player_id>

import {
  MY_TEAM_KEY, chevron, chip, el, emptyLine, errorLine, feetInches, fill, formatDay, getJSON,
  injuryTag, pct1, resultChip, skeletonRows, store, tag,
} from "./api.js";
import { chartLegend, drawShotChart } from "./shotchart.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const band = document.getElementById("band-player");
const root = document.getElementById("player");
const playerId = window.location.pathname.split("/").filter(Boolean).pop();
const PLACEHOLDER = window.PLACEHOLDER_HEADSHOT;

let card = null;
const filters = { type: "", zone: "" };

function panel(span, title, note, ...body) {
  return el("section", { class: `panel ${span}`, "aria-label": title },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: title }),
      note ? (note instanceof Node ? note : el("span", { class: "panel-note", text: note })) : null),
    body);
}

function showLoading() {
  fill(band, el("div", { class: "band-side" }, skeletonRows(2, [60, 200])));
  fill(root,
    panel("span-12", "Season", null, skeletonRows(2, [60, 60, 60, 60, 60, 60])),
    panel("span-5", "Shot chart", null, skeletonRows(8, [300])),
    panel("span-7", "Shots by zone", null, skeletonRows(5, [140, 40, 40, 40, 60])));
}

function showProblem(message, retry) {
  fill(band, el("p", { class: "muted", text: "No player to show." }));
  fill(root, el("section", { class: "panel span-12" },
    retry ? errorLine(message, retry)
      : el("div", { class: "state-error", role: "alert" },
        el("span", { text: message }),
        el("a", { class: "btn", href: "/", text: "Back to schedule" }))));
}

async function load() {
  showLoading();
  loadTeams().then(({ teams }) => {
    setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null);
  }).catch(() => {});
  try {
    card = await getJSON(`/api/players/${encodeURIComponent(playerId)}`);
  } catch (err) {
    const permanent = /must be a number|No player has/.test(err.message);
    showProblem(err.message, permanent ? null : load);
    return;
  }
  document.title = `${card.player.player_name} | Opponent Scout`;
  render();
}

// ---- Band -------------------------------------------------------------

function headshot(p) {
  const img = el("img", {
    class: "headshot",
    src: p.headshot_url || PLACEHOLDER,
    alt: `${p.player_name} headshot`,
    width: 130,
    height: 95,
  });
  // If the photo cannot load, show our own placeholder instead.
  img.addEventListener("error", () => {
    if (img.src !== new URL(PLACEHOLDER, window.location.href).href) img.src = PLACEHOLDER;
  }, { once: true });
  return img;
}

function measure(label, value, missing) {
  return el("div", { class: "measure" },
    el("div", { class: "label", text: label }),
    el("div", { class: value ? "measure-value" : "measure-value muted", text: value || missing }));
}

function renderBand() {
  const p = card.player;
  const team = card.team || { abbreviation: p.team_abbr, full_name: p.team_abbr };
  const height = p.height_inches ? feetInches(p.height_inches) : null;
  fill(band,
    el("div", { class: "band-side" },
      headshot(p),
      el("div", {},
        el("div", { class: "label", text: card.season_label ? `${card.season_label} season` : "Player" }),
        el("h1", { class: "band-name", style: "font-size: 16px; margin: 0", text: p.player_name }),
        el("div", { class: "band-sub", style: "display: flex; gap: 8px; align-items: center; flex-wrap: wrap" },
          chip(team.abbreviation),
          el("span", { text: team.full_name }),
          p.position ? el("span", { class: "muted", text: `· ${p.position}` }) : null,
          injuryTag(card.injury)))),
    el("div", { class: "measures" },
      measure("Height", height, "–"),
      measure("Weight", p.weight_lbs ? `${p.weight_lbs} lb` : null, "–"),
      measure("Wingspan", p.wingspan_inches ? feetInches(p.wingspan_inches) : null, "No combine data"),
      measure("Age", p.age ? String(p.age) : null, "–")));
}

// ---- Panels -----------------------------------------------------------

const d1 = (v) => (v === null || v === undefined ? "–" : Number(v).toFixed(1));

function seasonPanel() {
  const s = card.season;
  if (!s) {
    return panel("span-12", "Season", card.season_label,
      emptyLine(card.injury ? `No games played yet this season (${card.injury.status}).` : "No games played yet this season."));
  }
  const tile = (label, value) => el("div", { class: "tile" },
    el("div", { class: "label", text: label }), el("div", { class: "tile-value", text: value }));
  return panel("span-12", "Season", `${card.season_label} · per game`,
    el("div", { class: "tiles tiles-wide" },
      tile("GP", s.gp), tile("MIN", d1(s.min)), tile("PTS", d1(s.pts)), tile("REB", d1(s.reb)), tile("AST", d1(s.ast)),
      tile("STL", d1(s.stl)), tile("BLK", d1(s.blk)), tile("TOV", d1(s.tov)),
      tile("FG%", pct1(s.fg_pct)), tile("3P%", pct1(s.fg3_pct)), tile("FT%", pct1(s.ft_pct)), tile("TS%", pct1(s.ts_pct))));
}

function lastGamesPanel() {
  const games = card.last_games;
  if (!games.length) return panel("span-12", "Last five games", null, emptyLine("No games played yet this season."));
  const cols = "cols-last5";
  return panel("span-12", "Last five games", null,
    el("div", { class: "table-scroll" }, el("div", { style: "min-width: 760px" },
      el("div", { class: `trow thead short-head ${cols}` },
        ["Date", "Opponent", "Res"].map((t) => el("span", { text: t })),
        ["MIN", "PTS", "REB", "AST", "FG", "3P", "+/-"].map((t) => el("span", { class: "num", text: t })),
        el("span")),
      games.map((g) => el("div", { class: `trow ${cols}` },
        el("span", { class: "text-2", text: formatDay(g.date) }),
        el("span", { class: "opp" }, el("span", { class: "ha", text: g.home ? "vs" : "@" }), chip(g.opponent), g.starter ? tag("S") : null),
        el("span", {}, resultChip(g.result)),
        el("span", { class: "num text-2", text: g.min }),
        el("span", { class: "num strong", text: g.pts }),
        el("span", { class: "num text-2", text: g.reb }),
        el("span", { class: "num text-2", text: g.ast }),
        el("span", { class: "num text-2", text: `${g.fgm}-${g.fga}` }),
        el("span", { class: "num text-2", text: `${g.fg3m}-${g.fg3a}` }),
        el("span", { class: "num text-2", text: g.plus_minus > 0 ? `+${g.plus_minus}` : g.plus_minus }),
        el("a", { class: "scout-link", href: `/game/${g.game_id}`, "aria-label": `Box score, ${formatDay(g.date)}` }, "Box score", chevron()))))));
}

// Shot chart panel: filters, chart and counts. Reloads only the dots.
function chartPanel() {
  const body = el("div", { class: "chart-body" });
  const typeSelect = el("select", { class: "select", "aria-label": "Shot type" },
    el("option", { value: "", text: "All shot types" }));
  const zoneSelect = el("select", { class: "select", "aria-label": "Zone" },
    el("option", { value: "", text: "All zones" }),
    card.shots.zones.map((z) => el("option", { value: z.zone, text: z.label })));
  zoneSelect.value = filters.zone;
  const count = el("span", { class: "panel-note", "aria-live": "polite" });
  typeSelect.addEventListener("change", () => { filters.type = typeSelect.value; loadShots(body, count, typeSelect); });
  zoneSelect.addEventListener("change", () => { filters.zone = zoneSelect.value; loadShots(body, count, typeSelect); });
  const p = panel("span-5", "Shot chart", count,
    el("div", { class: "chart-filters" }, typeSelect, zoneSelect, chartLegend()),
    body);
  loadShots(body, count, typeSelect);
  return p;
}

async function loadShots(body, count, typeSelect) {
  fill(body, skeletonRows(6, [300]));
  count.textContent = "";
  const query = new URLSearchParams();
  if (filters.type) query.set("type", filters.type);
  if (filters.zone) query.set("zone", filters.zone);
  let data;
  try {
    data = await getJSON(`/api/players/${playerId}/shots?${query}`);
  } catch (err) {
    fill(body, errorLine(err.message, () => loadShots(body, count, typeSelect)));
    return;
  }
  // Fill the shot type list once, from the types he actually took.
  if (typeSelect.options.length === 1) {
    for (const t of data.shot_types) typeSelect.append(el("option", { value: t, text: t }));
    typeSelect.value = filters.type;
  }
  count.textContent = `${data.count} shots, ${data.made} made`;
  if (!data.count) {
    fill(body, emptyLine(filters.type || filters.zone ? "No shots match these filters." : "No shots this season."));
    return;
  }
  fill(body, drawShotChart(data.shots, { label: `Shot chart: ${data.count} shots, ${data.made} made` }));
}

function zonePanel() {
  const z = card.shots;
  if (!z.total_fga) return panel("span-7", "Shots by zone", "This season", emptyLine("No shots this season."));
  const gap = (v) => {
    if (v === null || v === undefined) return el("span", { class: "muted", text: "–" });
    const pts = v * 100;
    const text = `${pts > 0 ? "+" : ""}${pts.toFixed(1)}`;
    return el("span", { class: `strong ${pts > 0 ? "win" : pts < 0 ? "loss" : ""}`, text });
  };
  return panel("span-7", "Shots by zone", `This season · ${z.total_fga} shots`,
    el("div", { class: "table-scroll" }, el("div", { style: "min-width: 640px" },
      el("div", { class: "trow thead short-head cols-zones" },
        el("span", { text: "Zone" }),
        ["FGA", "Share", "FG%", "League", "vs Lg", "Last FGA", "Last FG%"].map((t) => el("span", { class: "num", text: t })),
        el("span")),
      z.zones.map((r) => el("div", { class: "trow cols-zones" },
        el("span", { class: "strong", text: r.label }),
        el("span", { class: "num text-2", text: r.fga }),
        el("span", { class: "num text-2", text: pct1(r.share) }),
        el("span", { class: "num strong", text: pct1(r.fg_pct) }),
        el("span", { class: "num text-2", text: pct1(r.league_fg_pct) }),
        el("span", { class: "num" }, gap(r.vs_league)),
        el("span", { class: "num text-2", text: r.last_season ? r.last_season.fga : "–" }),
        el("span", { class: "num text-2", text: r.last_season ? pct1(r.last_season.fg_pct) : "–" }),
        el("span", { class: "num" }, r.small_sample && r.fga > 0 ? tag("Small sample", "gold") : null))))),
    el("p", { class: "panel-foot", text: `vs Lg is his FG% minus the league FG% in that zone, in percentage points. Zones under ${z.small_sample_fga} attempts are a small sample. Last FGA and Last FG% are last season.` }));
}

function topTypesPanel() {
  const levels = [["rim", "At the rim"], ["midrange", "Midrange"], ["three", "Three"]];
  const t = card.shots.top_types;
  if (!card.shots.total_fga) return null;
  return panel("span-12", "Favorite shots", "Top three shot types at each level, this season",
    el("div", { class: "levels" }, levels.map(([key, label]) => {
      const lvl = t[key];
      return el("div", { class: "level" },
        el("div", { class: "level-head" },
          el("span", { class: "label", text: label }),
          el("span", { class: "muted", text: `${lvl.fga} shots` })),
        lvl.types.length
          ? lvl.types.map((s) => el("div", { class: "trow cols-types" },
            el("span", { class: "text-2", text: s.shot_type }),
            el("span", { class: "num text-2", text: `${s.fgm}-${s.fga}` }),
            el("span", { class: "num strong", text: pct1(s.fg_pct) })))
          : el("p", { class: "state-line", text: "No shots at this level." }));
    })),
    el("p", { class: "panel-foot", text: "At the rim is the restricted area. Midrange is the rest of the paint plus midrange. Columns: made-attempted, FG%." }));
}

function render() {
  renderBand();
  fill(root, seasonPanel(), chartPanel(), zonePanel(), topTypesPanel(), lastGamesPanel());
}

load();
