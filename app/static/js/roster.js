// The sortable roster table, shared by the scouting Players tab and the
// team page: USG%, per-game line, shooting, badges and injury tags.

import { badgeTip, chevron, el, emptyLine, injuryTag, pct1, rankText } from "./api.js";
import { renderSortTable } from "./sorttable.js";

// USG% for sorting: small samples (under 100 minutes) sort last.
const usgSortValue = (r) => (r.usage && r.usage.usg_pct !== null && !r.usage.small_sample ? r.usage.usg_pct : null);
const usgCell = (r) => {
  if (!r.usage || r.usage.usg_pct === null) return "–";
  const node = el("span", { title: r.usage.rank ? `${rankText(r.usage.rank)} of ${r.usage.ranked_of}` : "Not ranked (under 200 minutes)" },
    r.usage.usg_pct.toFixed(1));
  if (r.usage.small_sample) node.classList.add("muted");
  return node;
};

// state: { sortKey, sortDir }, kept by the caller. Sorted by USG% by default
// so the main options are at the top.
export function newRosterState() {
  return { sortKey: "usg", sortDir: "desc" };
}

// onepagerVs: our team id. When given, each row links to the player's
// one-pager written for that team.
export function renderRoster(body, players, state, label, { onepagerVs = null } = {}) {
  const s = (key) => (r) => (r.season ? r.season[key] : null);
  const num = (key, digits = 1) => (r) => (r.season ? Number(r.season[key]).toFixed(digits) : "–");
  const columns = [
    { key: "name", label: "Player", width: "minmax(200px, 1fr)", firstDir: "asc", value: (r) => r.player_name.toLowerCase(),
      cell: (r) => el("span", { class: "player-cell" },
        el("a", { class: "name-link", href: `/player/${r.player_id}`, text: r.player_name }),
        r.has_stats ? null : el("span", { class: "muted", text: "No stats yet" })) },
    { key: "pos", label: "Pos", width: "48px", firstDir: "asc", value: (r) => r.position, cell: (r) => r.position || "–", className: "text-2" },
    { key: "gp", label: "GP", width: "44px", align: "num", value: s("gp"), cell: (r) => (r.season ? r.season.gp : "–"), className: "text-2" },
    { key: "usg", label: "USG%", width: "60px", align: "num", value: usgSortValue, cell: usgCell, className: "strong" },
    { key: "min", label: "MIN", width: "56px", align: "num", value: s("min"), cell: num("min"), className: "text-2" },
    { key: "pts", label: "PTS", width: "56px", align: "num", value: s("pts"), cell: num("pts"), className: "strong" },
    { key: "reb", label: "REB", width: "56px", align: "num", value: s("reb"), cell: num("reb"), className: "text-2" },
    { key: "ast", label: "AST", width: "56px", align: "num", value: s("ast"), cell: num("ast"), className: "text-2" },
    { key: "fg", label: "FG%", width: "60px", align: "num", value: s("fg_pct"), cell: (r) => pct1(r.season && r.season.fg_pct), className: "text-2" },
    { key: "fg3", label: "3P%", width: "60px", align: "num", value: s("fg3_pct"), cell: (r) => pct1(r.season && r.season.fg3_pct), className: "text-2" },
    { key: "ts", label: "TS%", width: "60px", align: "num", value: s("ts_pct"), cell: (r) => pct1(r.season && r.season.ts_pct), className: "text-2" },
    { key: "badges", label: "Badges", width: "190px", value: (r) => r.badges.length || null,
      cell: (r) => (r.badges.length ? el("span", { class: "badge-cell" }, r.badges.map(badgeTip)) : el("span", { class: "muted", text: "" })) },
    { key: "status", label: "Status", width: "120px", align: "num", firstDir: "asc",
      value: (r) => (r.injury ? r.injury.status : null), cell: (r) => injuryTag(r.injury) || el("span", { class: "muted", text: "" }) },
  ];
  if (onepagerVs) {
    columns.push({ key: "onepager", label: "", width: "116px", sortable: false, value: () => null,
      cell: (r) => el("a", { class: "scout-link", href: `/onepager/${r.player_id}?vs=${onepagerVs}`,
        "aria-label": `One-pager on ${r.player_name}` }, "One-pager", chevron()) });
  }
  const draw = () => renderSortTable(body, {
    columns, rows: players, state, onSort: draw,
    label, emptyNode: emptyLine("No players are loaded for this team."),
  });
  draw();
}
