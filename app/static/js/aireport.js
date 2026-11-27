// The AI report pieces shared by the Report tab and the saved report page:
// editable sections, the number-check flags, the model line and the
// collapsible "Facts used" panel.

import { el, fill, howLink } from "./api.js";

export const SECTION_TITLES = {
  opponent_identity: "Opponent identity",
  keys_to_the_game: "Three keys to the game",
  players_to_watch: "Players to watch",
  matchup_notes: "Matchup notes",
};

function autoGrow(area) {
  const grow = () => { area.style.height = "auto"; area.style.height = `${area.scrollHeight + 2}px`; };
  area.addEventListener("input", grow);
  requestAnimationFrame(grow);
}

// One editable text box. Writes back into obj[key] and calls onEdit.
function box(obj, key, label, onEdit, rows = 2) {
  const area = el("textarea", { class: "textarea ai-text", rows: String(rows), maxlength: "4000", "aria-label": label });
  area.value = obj[key] || "";
  area.addEventListener("input", () => { obj[key] = area.value; onEdit(); });
  autoGrow(area);
  return area;
}

export function flagLine(flags, what = "report") {
  if (!flags || !flags.length) {
    return el("p", { class: "ai-check ok", text: "Number check: every number in the text was found in the facts." });
  }
  const word = flags.length === 1 ? "number was" : "numbers were";
  return el("div", { class: "ai-check warn", role: "note" },
    el("span", { class: "tag tag-gold", text: "Check" }),
    el("span", { text: ` ${flags.length} ${word} not found in the facts. Verify or remove before using the ${what}.` }),
    el("ul", {}, flags.map((f) => el("li", {},
      el("strong", { text: f.number }),
      el("span", { class: "muted", text: ` in ${f.section}${f.item ? ` #${f.item}` : ""}: "${f.context}"` })))));
}

export function modelLine(ai) {
  const bits = [`Written by ${ai.model}`, `prompt ${ai.prompt_version}`];
  if (ai.generated_at) {
    const d = new Date(ai.generated_at);
    if (!Number.isNaN(d.getTime())) bits.push(d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }));
  }
  if (ai.edited) bits.push("edited by hand");
  return el("p", { class: "ai-meta muted", text: bits.join(" · ") });
}

// The four sections as editable boxes. ai.sections is changed in place and
// ai.edited is set on the first change.
export function aiSections(ai, { onEdit = () => {} } = {}) {
  const s = ai.sections;
  const edited = () => { ai.edited = true; onEdit(); };
  const head = (key) => el("h3", { class: "ai-head", text: SECTION_TITLES[key] });
  const item = (label, ...body) => el("div", { class: "ai-item" }, el("div", { class: "ai-label", text: label }), body);
  return el("div", { class: "ai-sections" },
    flagLine(ai.flags),
    el("section", {}, head("opponent_identity"), box(s, "opponent_identity", "Opponent identity", edited, 3)),
    el("section", {}, head("keys_to_the_game"),
      (s.keys_to_the_game || []).map((k, i) => item(`${i + 1}.`,
        box(k, "title", `Key ${i + 1} title`, edited, 1), box(k, "detail", `Key ${i + 1} detail`, edited, 2)))),
    el("section", {}, head("players_to_watch"),
      (s.players_to_watch || []).map((p) => item(p.player, box(p, "note", `Note on ${p.player}`, edited, 2)))),
    el("section", {}, head("matchup_notes"),
      (s.matchup_notes || []).map((m) => item(`${m.their_player} · guarded by ${m.our_defender}`,
        box(m, "note", `Matchup note on ${m.their_player}`, edited, 2)))));
}

// ---- Facts panel ----------------------------------------------------------

const FACT_GROUPS = [
  ["Game and standings", ["data_as_of", "season", "us", "them", "next_meeting", "last_meeting", "last_games"]],
  ["Who runs the offense", ["who_runs_the_offense"]],
  ["Last game standouts", ["last_game_standouts"]],
  ["Injuries", ["injuries"]],
  ["Lineups and matchups", ["lineups", "matchups"]],
  ["Key opposing players", ["key_opposing_players"]],
  ["Units", ["units"]],
];

const label = (key) => key.replace(/_/g, " ");
const LEAD_KEYS = ["player", "their_player", "attribute", "badge", "defender", "team"];

function scalar(v) {
  if (v === null || v === undefined) return "none";
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

// Render any facts value as a compact, readable tree.
function factNode(value) {
  if (Array.isArray(value)) {
    if (!value.length) return el("span", { class: "muted", text: "none" });
    if (value.every((v) => typeof v !== "object" || v === null)) return el("span", { text: value.map(scalar).join(", ") });
    return el("ul", { class: "fact-list" }, value.map((v) => el("li", {}, factNode(v))));
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    // A flat record (one player, one rating) reads best as one line.
    if (entries.every(([, v]) => v === null || typeof v !== "object")) {
      const lead = entries.find(([k]) => LEAD_KEYS.includes(k));
      const rest = entries.filter((e) => e !== lead).map(([k, v]) => `${label(k)} ${scalar(v)}`).join(" · ");
      return el("span", {}, lead ? el("strong", { text: `${scalar(lead[1])}: ` }) : null, rest);
    }
    return el("dl", { class: "fact-dl" }, entries.flatMap(([k, v]) => [
      el("dt", { text: label(k) }),
      el("dd", {}, (v && typeof v === "object") ? factNode(v) : scalar(v)),
    ]));
  }
  return el("span", { text: scalar(value) });
}

export function factsPanel(facts) {
  const groups = FACT_GROUPS.map(([title, keys]) => {
    const part = {};
    for (const k of keys) if (k in facts) part[k] = facts[k];
    return el("details", { class: "fact-group" }, el("summary", { text: title }), factNode(part));
  });
  return el("details", { class: "facts-panel", open: true },
    el("summary", {}, el("span", { class: "panel-title", text: "Facts used" }),
      el("span", { class: "panel-note", text: " The only numbers the model was given · " }), howLink("ai", "How the AI is checked")),
    el("div", { class: "facts-body" }, groups));
}

// Skeleton shown while the report is being written.
export function aiLoading() {
  const bar = (w) => el("span", { class: "skel", style: `width: ${w}%` });
  return el("div", { class: "ai-sections", "aria-busy": "true" },
    el("p", { class: "ai-check", role: "status", text: "Writing the report. This usually takes 10 to 30 seconds." }),
    Object.values(SECTION_TITLES).map((t) => el("section", {}, el("h3", { class: "ai-head", text: t }),
      el("div", { class: "ai-skel" }, bar(92), bar(84), bar(60)))));
}

export function clear(node) { fill(node); }
