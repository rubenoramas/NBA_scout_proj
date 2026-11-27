// Player card: /player/<player_id>

import {
  MY_TEAM_KEY, ONOFF_NOTE, howLink, signed1, badgeTip, badgeWithTip, chevron, chip, el, emptyLine, errorLine, feetInches, fill, formatDay, getJSON,
  injuryTag, pct1, rankText, resultChip, skeletonRows, store, tag, logError
} from "./api.js";
import { chartLegend, drawShotChart } from "./shotchart.js";
import { loadTeams, setSwitcher } from "./topbar.js";
import { currentForm, formControl, withForm } from "./form.js";

const band = document.getElementById("band-player");
const root = document.getElementById("player");
const playerId = window.location.pathname.split("/").filter(Boolean).pop();
const PLACEHOLDER = window.PLACEHOLDER_HEADSHOT;

let card = null;
let myTeam = null; // the team chosen in the top bar, for the one-pager link
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
    myTeam = teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null;
    setSwitcher(myTeam);
    if (card) renderBand();
  }).catch((err) => logError("Top bar team list", err));
  try {
    card = await getJSON(withForm(`/api/players/${encodeURIComponent(playerId)}`));
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

// One-pager for our team's defenders. Written for the team in the top bar;
// for one of our own players (or no team chosen), the one-pager page asks
// which team will guard him.
function onepagerLink() {
  const vs = myTeam && myTeam.team_id !== card.player.team_id ? `?vs=${myTeam.team_id}` : "";
  return el("a", { class: "scout-link op-link", href: `/onepager/${card.player.player_id}${vs}`,
    title: vs ? `Printable page for ${myTeam.abbreviation} defenders` : "Printable page for the team that will guard him" },
  "One-pager", chevron());
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
          chip(team.abbreviation, { link: true }),
          el("span", { text: team.full_name }),
          p.position ? el("span", { class: "muted", text: `· ${p.position}` }) : null,
          injuryTag(card.injury)),
        badgesRow())),
    el("div", { class: "measures" },
      formControl(() => load()),
      onepagerLink(),
      measure("Height", height, "–"),
      measure("Weight", p.weight_lbs ? `${p.weight_lbs} lb` : null, "–"),
      measure("Wingspan", p.wingspan_inches ? feetInches(p.wingspan_inches) : null, "No combine data"),
      measure("Age", p.age ? String(p.age) : null, "–")));
}

// ---- Panels -----------------------------------------------------------

const d1 = (v) => (v === null || v === undefined ? "–" : Number(v).toFixed(1));

// USG% describes role, not skill, so it gets a league rank, not a rating.
function usageLine() {
  const u = card.usage;
  if (!u || u.usg_pct === null) return null;
  const last10 = card.form && card.form.form === "last10";
  const rank = last10
    ? (u.rank ? `${rankText(u.rank)} of ${u.ranked_of} players with 100+ minutes in their team's last 10` : `not ranked (${u.minutes} minutes in the last 10, ranks start at 100)`)
    : (u.rank ? `${rankText(u.rank)} of ${u.ranked_of} players with 200+ minutes` : `not ranked (${u.minutes} minutes, ranks start at 200)`);
  return el("div", { class: "usage-line" },
    el("span", { class: "label", text: "USG%" }),
    el("span", { class: "usage-value", text: u.usg_pct.toFixed(1) }),
    el("span", { class: "text-2", text: rank }),
    u.small_sample ? tag("Small sample", "gold") : null,
    el("span", { class: "muted", text: u.last_season_usg_pct !== null ? `Last season ${u.last_season_usg_pct.toFixed(1)}` : "No last season" }),
    el("span", { class: "muted usage-note", text: "Share of his team's plays (FGA + 0.44 x FTA + TOV) he uses while on the floor, same meaning as in the box score." }));
}

function seasonPanel() {
  const s = card.season;
  const last10 = card.form && card.form.form === "last10";
  const title = last10 ? "Last 10 games" : "Season";
  if (!s) {
    return panel("span-12", title, card.season_label,
      emptyLine(last10 ? "He has not played in his team's last 10 games."
        : card.injury ? `No games played yet this season (${card.injury.status}).` : "No games played yet this season."));
  }
  const tile = (label, value) => el("div", { class: "tile" },
    el("div", { class: "label", text: label }), el("div", { class: "tile-value", text: value }));
  return panel("span-12", title, last10
    ? `Per game · played ${card.form.played} of his team's last ${card.form.team_games} games`
    : `${card.season_label} · per game`,
    usageLine(),
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
  if (currentForm() === "last10") query.set("form", "last10");
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
  const last10 = card.form && card.form.form === "last10";
  if (!z.total_fga) return panel("span-7", "Shots by zone", last10 ? "Last 10 games" : "This season", emptyLine(last10 ? "No shots in his team's last 10 games." : "No shots this season."));
  const gap = (v) => {
    if (v === null || v === undefined) return el("span", { class: "muted", text: "–" });
    const pts = v * 100;
    const text = `${pts > 0 ? "+" : ""}${pts.toFixed(1)}`;
    return el("span", { class: `strong ${pts > 0 ? "win" : pts < 0 ? "loss" : ""}`, text });
  };
  return panel("span-7", "Shots by zone", `${last10 ? "Last 10 games" : "This season"} · ${z.total_fga} shots`,
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
    el("p", { class: "panel-foot", text: `vs Lg is his FG% minus the league FG% in that zone, in percentage points. Zones under ${z.small_sample_fga} attempts are a small sample. Last FGA and Last FG% are last season. ` }, howLink("zones", "How zones are drawn")));
}

function topTypesPanel() {
  const levels = [["rim", "At the rim"], ["midrange", "Midrange"], ["three", "Three"]];
  const t = card.shots.top_types;
  if (!card.shots.total_fga) return null;
  return panel("span-12", "Favorite shots", `Top three shot types at each level, ${card.form && card.form.form === "last10" ? "last 10 games" : "this season"}`,
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

// ---- Badges and ratings -------------------------------------------------

function badgesRow() {
  const a = card.attributes;
  if (!a) return null;
  const items = a.badges.map(badgeTip);
  const t = a.streaky_test;
  if (t && !t.passed) {
    // Shown even when not earned: the test result itself is informative.
    items.push(badgeWithTip("Tested: not streaky", [
      "Streaky Shooter test",
      `${pct1(t.after_make_pct)}% after a make (${t.after_make_fga} shots) vs ${pct1(t.after_miss_pct)}% after a miss (${t.after_miss_fga} shots).`,
      `z = ${t.z.toFixed(2)}, p = ${t.p_value.toPrecision(2)}. Needed p below ${t.alpha.toPrecision(2)} (0.05 split across ${t.players_tested} players tested).`,
      "Comparing make rates after makes and misses within games is biased slightly against finding streakiness (Miller and Sanjurjo, 2018), so this test is conservative.",
    ], "muted"));
  }
  if (!items.length) return null;
  return el("div", { class: "badges-row", "aria-label": "Badges" }, el("span", { class: "label", text: "Badges" }), items);
}

// Show his real rate, with the adjusted (shrunk) value used for ranking
// beside it, for example "13.0 per 36 (adjusted 10.9)".
function fmtNumber(label, v) {
  if (v === null || v === undefined) return null;
  if (label.includes("%")) return `${(v * 100).toFixed(1)}%`;
  if (label.includes("/36")) return `${v.toFixed(1)} per 36`;
  return v.toFixed(2);
}

function fmtComponent(c) {
  const real = fmtNumber(c.label, c.raw ?? c.value);
  if (real === null) return "no data";
  if (!c.shrunk || c.value === null || c.value === undefined) return real;
  const adjusted = fmtNumber(c.label, c.value).replace(" per 36", "");
  return `${real} (adjusted ${adjusted})`;
}

function ratingsPanel() {
  const a = card.attributes;
  const note = card.form && card.form.form === "last10"
    ? "Season ratings (Last 10 does not apply) · 0 to 99, percentile among qualified players"
    : "0 to 99, percentile among qualified players";
  if (!a || !a.qualified) {
    return panel("span-12", "Ratings", note,
      emptyLine("Not enough minutes for ratings yet. A player needs 200 minutes this season or 500 last season."));
  }
  const rows = a.ratings.map((r) => {
    const tags = [];
    if (r.last_season_only) tags.push(tag("Last season only", "gold"));
    else if (r.small_sample) tags.push(tag("Small sample", "gold"));
    const breakdown = r.components.map((c) =>
      `${c.label} (weight ${c.weight}${c.lower_is_better ? ", lower is better" : ""}): ${fmtComponent(c)}, `
      + `${c.percentile === null || c.percentile === undefined ? "no percentile" : `${Math.round(c.percentile * 100)}th percentile`}`);
    const tipLines = [r.label, ...breakdown, `Sample: ${r.sample.n} ${r.sample.label} (small below ${r.sample.min}).`];
    tipCount += 1;
    const id = `rtip-${tipCount}`;
    const value = r.rating ?? 0;
    return el("div", { class: "rating-row tip-wrap", tabindex: "0", "aria-describedby": id },
      el("span", { class: "rating-label", text: r.label }),
      el("span", { class: "rating-bar", "aria-hidden": "true" }, el("span", { class: "rating-fill", style: `width: ${value}%` })),
      el("span", { class: "rating-num", text: r.rating ?? "–" }),
      el("span", { class: "rating-tags" }, tags),
      el("span", { class: "tip", role: "tooltip", id },
        tipLines.map((line, i) => el("span", { class: i === 0 ? "tip-title" : "tip-line", text: line }))));
  });
  const w = Math.round(a.blend_weight * 100);
  return panel("span-12", "Ratings", note,
    el("div", { class: "ratings-grid" }, rows),
    el("p", { class: "panel-foot",
      text: `This season counts ${w}% and last season ${100 - w}% (${Math.round(a.min_this)} minutes this season; last season fades as minutes grow). `
        + "Players are ranked on adjusted values: rates are pulled toward the league average until the sample is large. Hover or focus a rating to see his real rates and the adjusted ones. " },
      howLink("ratings", "How ratings and badges work")));
}
let tipCount = 0;

// On/off: team ratings per 100 possessions with him on the floor and off it,
// this season with last season beside it.
function onoffPanel() {
  const o = card.onoff;
  const rows = [o.this_season, o.last_season].map((s) => {
    const label = el("span", { class: "strong", text: s.season || "–" });
    if (s.empty || !s.shown) {
      return el("div", { class: "trow cols-onoff" }, label,
        el("span", { class: "muted onoff-span", text: s.empty ? "No games played." : `Not enough minutes (${s.on.poss} possessions on; ${o.rules.show_min_poss} needed).` }));
    }
    const num = (v, cls = "text-2") => el("span", { class: `num ${cls}`, text: v === null ? "–" : Number(v).toFixed(1) });
    const net = (v) => el("span", { class: `num strong ${v > 0 ? "win" : v < 0 ? "loss" : ""}`, text: signed1(v) });
    return el("div", { class: "trow cols-onoff" }, label,
      num(s.on.off_rating), num(s.on.def_rating), net(s.on.net_rating), el("span", { class: "num muted", text: s.on.poss }),
      num(s.off.off_rating), num(s.off.def_rating), net(s.off.net_rating), el("span", { class: "num muted", text: s.off.poss }),
      net(s.on_off_net),
      el("span", { class: "num" }, s.small_sample ? tag("Small sample", "gold") : null),
      s.teams ? el("span", { class: "muted onoff-teams", text: `${s.teams.length} teams combined` }) : el("span"));
  });
  return panel("span-12", "On/off", "Team per 100 possessions with him on the floor and off it, in games he played",
    el("div", { class: "table-scroll" }, el("div", { style: "min-width: 960px" },
      el("div", { class: "trow thead short-head cols-onoff" },
        el("span", { text: "Season" }),
        ["On ORtg", "On DRtg", "On net", "Poss", "Off ORtg", "Off DRtg", "Off net", "Poss", "On-off"].map((t) => el("span", { class: "num", text: t })),
        el("span"), el("span")),
      rows)),
    el("p", { class: "panel-foot", text: `ORtg is points his team scores per 100 possessions, DRtg points it allows, net the difference. On-off is the net with him on minus the net with him off. `
      + `Free throws count for the players on the floor at the foul. Small sample: under ${o.rules.small_poss.toLocaleString("en-US")} possessions on or off. ${ONOFF_NOTE} ` },
      howLink("onoff", "How on/off is counted")));
}

function render() {
  renderBand();
  fill(root, seasonPanel(), ratingsPanel(), onoffPanel(), chartPanel(), zonePanel(), topTypesPanel(), lastGamesPanel());
}

load();
