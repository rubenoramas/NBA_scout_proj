// One player's one-pager: /onepager/<player_id>?vs=<our team id>
// "vs" is our team, the one whose player will guard him. Without it, the
// page uses the team chosen in the top bar, and the picker can change it.

import { MY_TEAM_KEY, el, errorLine, fill, getJSON, store } from "./api.js";
import { loadNote, renderSheet, sheetSkeleton } from "./onepagerview.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const toolbar = document.getElementById("toolbar");
const root = document.getElementById("sheets");
const playerId = window.location.pathname.split("/").filter(Boolean).pop();
let teams = [];

function vsFromUrl() {
  const v = new URLSearchParams(window.location.search).get("vs");
  if (v) return v;
  const mine = teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY));
  return mine ? String(mine.team_id) : "";
}

function drawToolbar(vs, page) {
  const select = el("select", { class: "select", id: "vs-team", "aria-label": "Team that will guard him" },
    el("option", { value: "", text: "Pick our team" }),
    teams.map((t) => el("option", { value: t.team_id, text: `${t.abbreviation} · ${t.full_name}` })));
  select.value = vs;
  select.addEventListener("change", () => {
    if (!select.value) return;
    const q = new URLSearchParams({ vs: select.value });
    window.history.replaceState({}, "", `${window.location.pathname}?${q}`);
    load();
  });
  const print = el("button", { type: "button", class: "btn btn-primary", text: "Print", disabled: !page,
    onclick: () => window.print() });
  fill(toolbar,
    el("a", { class: "btn", href: `/player/${encodeURIComponent(playerId)}`, text: "‹ Player card" }),
    el("label", { class: "sheet-pick" }, el("span", { class: "label", text: "Guarded by" }), select),
    el("span", { class: "spacer" }),
    el("span", { class: "muted", text: "Prints on one US letter page." }),
    print);
}

async function load() {
  fill(root, sheetSkeleton());
  try {
    teams = (await loadTeams()).teams;
  } catch (err) {
    fill(root, el("section", { class: "panel" }, errorLine(err.message, load)));
    return;
  }
  setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null);
  const vs = vsFromUrl();
  drawToolbar(vs, null);
  if (!vs) {
    fill(root, el("section", { class: "panel" },
      el("p", { class: "state-line", text: "Pick the team that will guard him, in Guarded by above." })));
    return;
  }
  let page;
  try {
    page = await getJSON(`/api/players/${encodeURIComponent(playerId)}/onepager?vs=${encodeURIComponent(vs)}`);
  } catch (err) {
    // A bad id or his own team will not fix itself: no Try again button.
    const permanent = /must be a number|No player has|No team has|plays for/.test(err.message);
    fill(root, el("section", { class: "panel" }, errorLine(err.message, permanent ? null : load)));
    return;
  }
  document.title = `${page.player.player_name} one-pager | Opponent Scout`;
  drawToolbar(vs, page);
  const sheet = renderSheet(page);
  fill(root, sheet);
  loadNote(sheet, page);
}

load();
