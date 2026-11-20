// Saved reports list: /reports. Newest first, with open and delete.
// Delete asks for confirmation inline, not with a browser pop-up.

import { MY_TEAM_KEY, chip, el, emptyLine, errorLine, fill, formatDay, getJSON, sendJSON, skeletonRows, store } from "./api.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const body = document.getElementById("reports-body");

function when(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

async function load() {
  loadTeams().then(({ teams }) => setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null)).catch(() => {});
  fill(body, skeletonRows(5, [220, 90, 80, 120, 120]));
  let data;
  try {
    data = await getJSON("/api/reports");
  } catch (err) {
    fill(body, errorLine(err.message, load));
    return;
  }
  render(data.reports);
}

function render(reports) {
  if (!reports.length) {
    fill(body, emptyLine("No saved reports yet. Save one from a scouting page's Report tab."));
    return;
  }
  const header = el("div", { class: "trow thead short-head cols-reports" },
    ["Title", "Teams", "Game", "Saved", "Last edited"].map((t) => el("span", { text: t })), el("span"));
  const rows = reports.map((r) => {
    const row = el("div", { class: "report-row" });
    const actions = el("span", { class: "row-actions" });
    const confirm = el("div", { class: "confirm-row", hidden: true });
    const open = el("a", { class: "btn", href: `/reports/${r.id}`, text: "Open" });
    const del = el("button", { type: "button", class: "btn", text: "Delete" });
    del.addEventListener("click", () => {
      const yes = el("button", { type: "button", class: "btn btn-danger", text: "Yes, delete" });
      const no = el("button", { type: "button", class: "btn", text: "Cancel" });
      fill(confirm, el("span", { text: `Delete "${r.title}"? This cannot be undone.` }), yes, no);
      confirm.hidden = false;
      no.addEventListener("click", () => { confirm.hidden = true; del.focus(); });
      yes.addEventListener("click", async () => {
        yes.disabled = true; yes.textContent = "Deleting...";
        try {
          await sendJSON("DELETE", `/api/reports/${r.id}`);
          reports = reports.filter((x) => x.id !== r.id);
          render(reports);
        } catch (err) {
          fill(confirm, el("span", { text: err.message }), no);
        }
      });
      yes.focus();
    });
    fill(actions, open, del);
    fill(row,
      el("div", { class: "trow cols-reports tall" },
        el("a", { class: "name-link", href: `/reports/${r.id}`, text: r.title }),
        el("span", { class: "opp" }, chip(r.us_abbr, { link: true }), el("span", { class: "muted", text: "vs" }), chip(r.them_abbr, { link: true })),
        el("span", { class: "text-2", text: r.game_date ? formatDay(r.game_date) : "No game" }),
        el("span", { class: "text-2", text: when(r.created_at) }),
        el("span", { class: "text-2", text: when(r.updated_at) }),
        actions),
      confirm);
    return row;
  });
  fill(body, el("div", { class: "table-scroll" }, el("div", { style: "min-width: 860px" }, header, rows)));
}

load();
