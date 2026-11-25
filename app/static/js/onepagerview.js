// The player one-pager sheet, shared by /onepager/<id> (one player) and
// /onepagers (print all). renderSheet() draws the page data from
// GET /api/players/<id>/onepager; the "How to guard him" box loads its text
// separately, because writing it can take a few seconds.

import { ONOFF_NOTE, el, feetInches, fill, formatDay, injuryTag, pct1, postJSON, rankText, signed1, tag } from "./api.js";
import { flagLine, modelLine } from "./aireport.js";
import { normEffect } from "./matchtable.js";
import { drawShotChart } from "./shotchart.js";

const PLACEHOLDER = window.PLACEHOLDER_HEADSHOT;
const d1 = (v) => (v === null || v === undefined ? "–" : Number(v).toFixed(1));
const d2 = (v) => (v === null || v === undefined ? "–" : Number(v).toFixed(2));

// "us_status=1628969:Out,..." from the lineup editor, as a query string.
export function statusParam(overrides) {
  return (overrides || []).map((o) => `${o.player_id}:${o.status}`).join(",");
}

// The query for this page's API calls: our team, plus the lineup editor's
// statuses when the page was opened with them.
export function pageQuery(vs, overrides) {
  const q = new URLSearchParams({ vs });
  const st = statusParam(overrides);
  if (st) q.set("us_status", st);
  return q.toString();
}

function box(cls, title, note, ...body) {
  return el("section", { class: `panel sheet-box ${cls}`, "aria-label": title },
    el("div", { class: "panel-head sheet-box-head" },
      el("h2", { class: "panel-title", text: title }),
      note ? (note instanceof Node ? note : el("span", { class: "panel-note", text: note })) : null),
    body);
}

function headshot(p) {
  const img = el("img", { class: "headshot sheet-headshot", src: p.headshot_url || PLACEHOLDER, alt: `${p.player_name} headshot`, width: 96, height: 70 });
  img.addEventListener("error", () => {
    if (img.src !== new URL(PLACEHOLDER, window.location.href).href) img.src = PLACEHOLDER;
  }, { once: true });
  return img;
}

function measure(label, value, missing = "–") {
  return el("div", { class: "measure" },
    el("div", { class: "label", text: label }),
    el("div", { class: value ? "measure-value" : "measure-value muted", text: value || missing }));
}

// ---- Header -------------------------------------------------------------

function header(page) {
  const p = page.player;
  const team = page.team || { abbreviation: p.team_abbr, full_name: p.team_abbr };
  return el("header", { class: "sheet-head" },
    headshot(p),
    el("div", { class: "sheet-who" },
      el("div", { class: "label", text: `One-pager · for ${page.us.abbreviation} · data as of ${page.data_as_of ? formatDay(page.data_as_of, { month: "short", day: "numeric", year: "numeric" }) : "unknown"}` }),
      el("h1", { class: "sheet-name" }, el("a", { class: "name-link", href: `/player/${p.player_id}`, text: p.player_name })),
      el("div", { class: "band-sub sheet-sub" },
        el("span", { class: "chip", text: team.abbreviation }),
        el("span", { text: team.full_name }),
        p.position ? el("span", { class: "muted", text: `· ${p.position}` }) : null,
        injuryTag(page.injury) || tag("Available"))),
    el("div", { class: "measures sheet-measures" },
      measure("Height", p.height_inches ? feetInches(p.height_inches) : null),
      measure("Weight", p.weight_lbs ? `${p.weight_lbs} lb` : null),
      measure("Wingspan", p.wingspan_inches ? feetInches(p.wingspan_inches) : null, "No combine data")));
}

function seasonLine(page) {
  const s = page.season;
  const u = page.usage;
  if (!s) return el("p", { class: "state-line sheet-line", text: "No games played yet this season." });
  const tile = (label, value, extra) => el("div", { class: "tile" },
    el("div", { class: "label", text: label }), el("div", { class: "tile-value", text: value }), extra || null);
  const usage = u && u.usg_pct !== null
    ? tile("USG%", u.usg_pct.toFixed(1),
      el("div", { class: "tile-note" },
        u.rank ? `${rankText(u.rank)} of ${u.ranked_of}` : "not ranked",
        u.small_sample ? [" ", tag("Small sample", "gold")] : null))
    : tile("USG%", "–");
  return el("div", { class: "tiles sheet-line", "aria-label": `${page.season_label} season per game` },
    tile("GP", s.gp), tile("MIN", d1(s.min)), tile("PTS", d1(s.pts)), tile("REB", d1(s.reb)), tile("AST", d1(s.ast)),
    tile("TOV", d1(s.tov)), tile("FG%", pct1(s.fg_pct)), tile("3P%", pct1(s.fg3_pct)), tile("FT%", pct1(s.ft_pct)),
    tile("TS%", pct1(s.ts_pct)), usage);
}

// One line: his on-off net this season, last season beside it.
function onoffLine(page) {
  const o = page.onoff;
  if (!o) return null;
  const team = (page.team || {}).abbreviation || page.player.team_abbr;
  const part = (s) => {
    if (s.empty) return `${s.season}: no games`;
    if (!s.shown) return `${s.season}: not enough minutes`;
    return `${s.season} ${signed1(s.on_off_net)} (${s.on.poss} on, ${s.off.poss} off${s.small_sample ? ", small sample" : ""})`;
  };
  const t = o.this_season;
  const lead = t.shown && !t.empty
    ? `${team} is ${Math.abs(t.on_off_net).toFixed(1)} per 100 ${t.on_off_net >= 0 ? "better" : "worse"} with him on the floor.`
    : "Not enough minutes for an on/off number this season.";
  return el("p", { class: "op-onoff" },
    el("span", { class: "label", text: "On/off net " }),
    el("span", { class: "strong", text: lead }),
    t.small_sample && t.shown ? [" ", tag("Small sample", "gold")] : null,
    el("span", { class: "muted", text: ` ${part(t)} · ${part(o.last_season)}. ${ONOFF_NOTE}` }));
}

// ---- How to guard him (AI) -----------------------------------------------

function guardBox(page) {
  const body = el("div", { class: "guard-body", "aria-live": "polite" });
  const node = box("sheet-guard", "How to guard him", "Written by Claude from the numbers on this page only", body);
  const n = page.note;
  if (n.cached) showNote(body, n.cached);
  else if (!n.key_set) fill(body, el("p", { class: "muted", text: n.no_key_message }));
  else node.dataset.needsNote = "1";
  return node;
}

function showNote(body, note) {
  fill(body,
    el("p", { class: "guard-text", text: note.text }),
    el("div", { class: "guard-meta no-print-flags" }, flagLine(note.flags, "text"), modelLine(note)));
  // Flags still print when there are any: the reader must know.
  if (note.flags && note.flags.length) body.querySelector(".guard-meta").classList.remove("no-print-flags");
}

// Ask the server for the text (from its cache, or written now). Returns a
// promise that settles when the box shows text or an error.
export async function loadNote(sheet, page) {
  const node = sheet.querySelector("[data-needs-note]");
  if (!node) return;
  const body = node.querySelector(".guard-body");
  const bar = (w) => el("span", { class: "skel", style: `width: ${w}%` });
  fill(body, el("p", { class: "muted", role: "status", text: "Writing the text. This usually takes 5 to 15 seconds." }),
    el("div", { class: "ai-skel", "aria-hidden": "true" }, bar(94), bar(88), bar(52)));
  try {
    const url = `/api/players/${page.player.player_id}/onepager/note?${pageQuery(page.us.team_id, page.defenders.overrides)}`;
    const data = await postJSON(url, {}, { timeoutMs: 120000 });
    showNote(body, data.note);
    delete node.dataset.needsNote;
  } catch (err) {
    fill(body, el("div", { class: "state-error", role: "alert" },
      el("span", { text: err.message }),
      el("button", { type: "button", class: "btn no-print", text: "Try again", onclick: () => loadNote(sheet, page) })));
  }
}

// ---- Ratings and badges ----------------------------------------------------

function ratingsBox(page) {
  const a = page.attributes;
  if (!a.qualified) {
    return box("sheet-ratings", "Ratings", "0 to 99 vs the league",
      el("p", { class: "state-line", text: "Not enough minutes for ratings yet (200 this season or 500 last season)." }),
      badgeList(a.badges));
  }
  const rows = a.ratings.map((r) => el("div", { class: "op-rating" },
    el("span", { class: "rating-label", text: r.label }),
    el("span", { class: "rating-bar", "aria-hidden": "true" }, el("span", { class: "rating-fill", style: `width: ${r.rating ?? 0}%` })),
    el("span", { class: "rating-num", text: r.rating ?? "–" }),
    el("span", { class: "rating-tags" },
      r.last_season_only ? tag("Last season only", "gold") : r.small_sample ? tag("Small sample", "gold") : null)));
  return box("sheet-ratings", "Ratings", "0 to 99, percentile among qualified players; 50 is typical",
    el("div", { class: "op-ratings" }, rows), badgeList(a.badges));
}

function badgeList(badges) {
  return el("div", { class: "op-badges" },
    el("div", { class: "label", text: "Badges" }),
    badges.length
      ? badges.map((b) => el("div", { class: "op-badge" },
        el("span", { class: "tag tag-accent", text: b.name }),
        el("span", { class: "text-2", text: ` ${b.detail}` })))
      : el("span", { class: "muted", text: "None earned." }));
}

// ---- Best defenders ----------------------------------------------------------

function defendersBox(page) {
  const d = page.defenders;
  const opts = d.options;
  const norm = opts.length ? `His norm ${opts[0].norm_per100.toFixed(1)} per 100` : null;
  return box("sheet-defenders", `Our best defenders on him (${page.us.abbreviation})`, norm,
    opts.length
      ? [el("div", { class: "trow thead short-head cols-op-def" },
        el("span", { text: "#" }), el("span", { text: "Defender" }), el("span", { text: "Effect vs his norm" }),
        el("span", { class: "num", text: "Exp/100" }), el("span", { class: "num", text: "History" })),
      opts.map((o, i) => el("div", { class: "trow cols-op-def" },
        el("span", { class: "muted", text: i + 1 }),
        el("span", { class: "player-cell" }, el("a", { class: "name-link", href: `/player/${o.defender_id}`, text: o.defender_name }),
          o.position ? el("span", { class: "muted", text: o.position }) : null),
        el("span", {}, normEffect(o)),
        el("span", { class: "num text-2", text: o.expected_per100.toFixed(1) }),
        el("span", { class: "num history-cell" }, el("span", { class: "text-2", text: `${Math.round(o.history_poss)} poss` }),
          o.small_history ? tag("Small sample", "gold") : null)))]
      : el("p", { class: "state-line", text: `No healthy ${page.us.abbreviation} defender has enough minutes.` }),
    statusNote(d),
    el("p", { class: "panel-foot", text: `From the matchup model: points per 100 partial possessions (league about ${d.league_per100}). History under ${d.min_history} possessions is a small sample.` }));
}

// Which statuses decided who can guard him: the official injury report, or
// the statuses set in the lineup editor on the scouting page.
function statusNote(d) {
  const n = d.overrides.length;
  const text = d.status_source === "lineup"
    ? `Who can play: statuses set in the lineup editor (${n} change${n === 1 ? "" : "s"} from the official report). Out players are left out.`
    : "Who can play: the official injury report. Out players are left out.";
  return el("p", { class: "op-status" }, tag(d.status_source === "lineup" ? "Lineup editor" : "Official report", d.status_source === "lineup" ? "accent" : ""),
    el("span", { class: "muted", text: ` ${text}` }));
}

// ---- Shots ---------------------------------------------------------------------

function shotsBox(page) {
  const sh = page.shots;
  if (!sh.total_fga) return box("sheet-shots", "Favorite shots", null, el("p", { class: "state-line", text: "No shots this season." }));
  const levels = [["rim", "At the rim"], ["midrange", "Midrange"], ["three", "Three"]];
  return box("sheet-shots", "Favorite shots", `${page.season_label} · top three types at each level · made-att, FG%`,
    el("div", { class: "levels op-levels" }, levels.map(([key, label]) => {
      const lvl = sh.top_types[key];
      return el("div", { class: "level" },
        el("div", { class: "level-head" }, el("span", { class: "label", text: label }), el("span", { class: "muted", text: `${lvl.fga} shots` })),
        lvl.types.length
          ? lvl.types.map((t) => el("div", { class: "trow cols-types" },
            el("span", { class: "text-2", text: t.shot_type }),
            el("span", { class: "num text-2", text: `${t.fgm}-${t.fga}` }),
            el("span", { class: "num strong", text: pct1(t.fg_pct) })))
          : el("p", { class: "muted", text: "None." }));
    })));
}

function chartBox(page) {
  const sh = page.shots;
  return box("sheet-chart", "Shot chart", sh.total_fga ? `${sh.total_fga} shots, ${sh.made} made` : null,
    sh.total_fga
      ? el("div", { class: "op-chart" }, drawShotChart(sh.chart.map((s) => ({ ...s, shot_type: "shot", distance: "" })),
        { label: `Shot chart: ${sh.total_fga} shots, ${sh.made} made` }),
        el("p", { class: "muted op-legend", text: "Filled dots are makes, rings are misses." }))
      : el("p", { class: "state-line", text: "No shots this season." }));
}

// ---- How he gets his shots ---------------------------------------------------

function playTypesBox(page) {
  const pt = page.play_types;
  if (!pt.rows.length) {
    return box("sheet-plays", "How his possessions end", null, el("p", { class: "state-line", text: "No play type data for him yet." }));
  }
  const note = `${pt.season}${pt.last_season_only ? " (last season: none yet this season)" : ""} · ${pt.total_poss} possessions`;
  return box("sheet-plays", "How his possessions end", note,
    el("div", { class: "trow thead short-head cols-op-plays" },
      el("span", { text: "Play type" }), el("span", { class: "num", text: "Poss" }), el("span", { class: "num", text: "Share" }),
      el("span", { class: "num", text: "PPP" }), el("span", { class: "num", text: "League" }),
      el("span", { text: "vs League" }), el("span")),
    pt.rows.slice(0, 6).map((r) => {
      // Same meaning as the player card: green is above league average for
      // him, red below. Words carry the meaning too, not only color.
      const gap = r.league_ppp === null ? null : r.ppp - r.league_ppp;
      const word = gap === null ? "–" : gap >= 0.05 ? "above league" : gap <= -0.05 ? "below league" : "near league";
      const cls = gap === null ? "muted" : gap >= 0.05 ? "win" : gap <= -0.05 ? "loss" : "text-2";
      return el("div", { class: "trow cols-op-plays" },
        el("span", { class: "text-2", text: r.label }),
        el("span", { class: "num text-2", text: r.poss }),
        el("span", { class: "num strong", text: pct1(r.share) }),
        el("span", { class: `num strong ${cls}`, text: d2(r.ppp) }),
        el("span", { class: "num text-2", text: d2(r.league_ppp) }),
        el("span", { class: `strong ${cls}`, text: word }),
        el("span", { class: "num" }, r.small_sample ? tag("Small sample", "gold") : null));
    }),
    el("p", { class: "panel-foot", text: "PPP is points per possession that ends in that play type. Above or below league compares his PPP with the league's on that play type (within 0.05 is near league), the same way the player card compares FG%. Play types describe how possessions end, not called plays." }));
}

function feedersBox(page) {
  const f = page.feeders;
  const note = f.fgm ? `${f.assisted_fgm} of his ${f.fgm} made shots were assisted (${pct1(f.assisted_share)}%)` : null;
  return box("sheet-feeders", "Who feeds him", note,
    f.small_sample && f.fgm ? el("p", { class: "op-small" }, tag("Small sample", "gold"), el("span", { class: "muted", text: ` Under ${f.min_fgm} made shots.` })) : null,
    f.passers.length
      ? [el("div", { class: "trow thead short-head cols-op-feed" },
        el("span", { text: "Passer" }), el("span", { class: "num", text: "AST" }), el("span", { class: "num", text: "On 3s" }),
        el("span", { class: "num", text: "Share" })),
      f.passers.map((x) => el("div", { class: "trow cols-op-feed" },
        el("span", { class: "player-cell" }, el("a", { class: "name-link", href: `/player/${x.player_id}`, text: x.player_name }),
          x.now_with ? tag(`Now ${x.now_with}`) : null),
        el("span", { class: "num strong", text: x.ast }),
        el("span", { class: "num text-2", text: x.ast_fg3 }),
        el("span", { class: "num text-2", text: pct1(x.share_of_assisted) })))]
      : el("p", { class: "state-line", text: "No assisted shots on record this season." }),
    el("p", { class: "panel-foot", text: "From play-by-play: the passer named on each assisted make. Share is of his assisted makes." }));
}

// ---- The whole sheet -----------------------------------------------------------

export function renderSheet(page) {
  return el("article", { class: "sheet", "aria-label": `One-pager: ${page.player.player_name}` },
    header(page),
    seasonLine(page),
    onoffLine(page),
    el("div", { class: "sheet-grid" },
      guardBox(page),
      ratingsBox(page),
      defendersBox(page),
      shotsBox(page),
      chartBox(page),
      playTypesBox(page),
      feedersBox(page)));
}

export function sheetSkeleton() {
  const bar = (w) => el("span", { class: "skel", style: `width: ${w}px` });
  return el("article", { class: "sheet", "aria-busy": "true" },
    el("span", { class: "sr-only", role: "status", text: "Loading" }),
    el("div", { class: "sheet-head", "aria-hidden": "true" }, el("div", { class: "skel", style: "width: 96px; height: 70px" }),
      el("div", { class: "ai-skel" }, bar(160), bar(220), bar(180))),
    el("div", { class: "sheet-grid", "aria-hidden": "true" },
      ["sheet-guard", "sheet-ratings", "sheet-defenders", "sheet-shots", "sheet-chart"].map((c) =>
        el("section", { class: `panel sheet-box ${c}` }, el("div", { class: "ai-skel", style: "padding: 12px 16px" }, bar(240), bar(200), bar(140))))));
}
