// Print all one-pagers: /onepagers?vs=<our team id>&ids=<id>,<id>,...
// Opened by "Print one-pagers" on the scouting page with their five plus
// anyone at 25% USG or higher. Each sheet prints on its own page.

import { MY_TEAM_KEY, el, errorLine, fill, getJSON, store } from "./api.js";
import { loadNote, renderSheet, sheetSkeleton } from "./onepagerview.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const toolbar = document.getElementById("toolbar");
const root = document.getElementById("sheets");
const params = new URLSearchParams(window.location.search);
const vs = (params.get("vs") || "").trim();
// Statuses for our players from the lineup editor, passed on as they came.
const usStatus = (params.get("us_status") || "").trim();
const ids = [...new Set((params.get("ids") || "").split(",").map((s) => s.trim()).filter(Boolean))];
// Writing several texts at once is fine for the API, but two at a time
// keeps the rate limit comfortable.
const NOTE_CONCURRENCY = 2;

const status = el("span", { class: "muted", role: "status", "aria-live": "polite" });
const print = el("button", { type: "button", class: "btn btn-primary", text: "Print all", disabled: true, onclick: () => window.print() });

function drawToolbar() {
  fill(toolbar,
    el("span", { class: "strong", text: `${ids.length} one-pager${ids.length === 1 ? "" : "s"}` }),
    status,
    el("span", { class: "spacer" }),
    el("span", { class: "muted", text: "One US letter page per player." }),
    print);
}

function problem(message) {
  fill(root, el("section", { class: "panel" }, el("p", { class: "state-error", role: "alert", text: message })));
}

async function runLimited(tasks, limit) {
  let next = 0;
  const worker = async () => {
    while (next < tasks.length) await tasks[next++]();
  };
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker));
}

async function load() {
  drawToolbar();
  loadTeams().then(({ teams }) => setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null)).catch(() => {});
  if (!/^\d+$/.test(vs)) { problem("This link is missing our team. Open Print one-pagers from a scouting page."); return; }
  if (!ids.length) { problem("This link names no players. Open Print one-pagers from a scouting page."); return; }
  if (ids.some((id) => !/^\d+$/.test(id))) { problem("A player id in this link is not a number."); return; }

  // One slot per player, in order, so pages print in the same order.
  const slots = ids.map(() => el("div", { class: "sheet-slot" }, sheetSkeleton()));
  fill(root, slots);
  let loaded = 0;
  let failed = 0;
  let noKey = false;
  const written = () => root.querySelectorAll(".guard-text").length;
  const say = () => {
    const parts = [`Loaded ${loaded} of ${ids.length}`];
    if (noKey) parts.push("no API key, so the sheets print without How to guard him");
    else if (loaded === ids.length) parts.push(`How to guard him ready for ${written()} of ${ids.length - failed}`);
    status.textContent = parts.join(" · ");
  };
  say();
  const ready = [];
  await Promise.all(ids.map(async (id, i) => {
    try {
      const q = new URLSearchParams({ vs });
      if (usStatus) q.set("us_status", usStatus);
      const page = await getJSON(`/api/players/${id}/onepager?${q}`);
      if (!page.note.key_set && !page.note.cached) noKey = true;
      const sheet = renderSheet(page);
      fill(slots[i], sheet);
      ready.push({ sheet, page });
    } catch (err) {
      failed += 1;
      fill(slots[i], el("section", { class: "panel no-print" }, errorLine(`Player ${id}: ${err.message}`, null)));
    }
    loaded += 1;
    say();
  }));
  // Texts already cached need no request.
  const pending = ready.filter((r) => r.sheet.querySelector("[data-needs-note]"));
  say();
  if (pending.length) {
    await runLimited(pending.map((r) => async () => {
      await loadNote(r.sheet, r.page);
      say();
    }), NOTE_CONCURRENCY);
  }
  print.disabled = ready.length === 0;
  if (!noKey && written() < ready.length) {
    status.textContent += ". Some texts could not be written (see the sheets); those sheets print without them.";
  }
}

load();
