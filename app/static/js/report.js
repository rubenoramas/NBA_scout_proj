// One saved report: /reports/<id>. Shows the snapshot exactly as saved,
// even if the data has changed since. Title and notes can be edited; the
// lineups and matchups are locked.

import { MY_TEAM_KEY, chip, el, errorLine, fill, formatDay, getJSON, sendJSON, skeletonRows, store, logError } from "./api.js";
import { aiSections, factsPanel, modelLine } from "./aireport.js";
import { lineupLine, matchupNotes, matchupTable } from "./matchtable.js";
import { loadTeams, setSwitcher } from "./topbar.js";

const root = document.getElementById("report");
const reportId = window.location.pathname.split("/").filter(Boolean).pop();

function when(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function panel(title, note, ...body) {
  return el("section", { class: "panel span-12", "aria-label": title },
    el("div", { class: "panel-head", style: "justify-content: space-between" },
      el("h2", { class: "panel-title", text: title }),
      note ? el("span", { class: "panel-note", text: note }) : null),
    body);
}

async function load() {
  loadTeams().then(({ teams }) => setSwitcher(teams.find((t) => t.abbreviation === store.get(MY_TEAM_KEY)) || null)).catch((err) => logError("Top bar team list", err));
  fill(root, panel("Saved report", null, skeletonRows(8, [220, 120, 160, 200])));
  let report;
  try {
    report = await getJSON(`/api/reports/${encodeURIComponent(reportId)}`);
  } catch (err) {
    const permanent = /not valid|No saved report/.test(err.message);
    fill(root, el("section", { class: "panel span-12" },
      permanent
        ? el("div", { class: "state-error", role: "alert" }, el("span", { text: err.message }),
          el("a", { class: "btn", href: "/reports", text: "All saved reports" }))
        : errorLine(err.message, load)));
    return;
  }
  render(report);
}

function render(r) {
  document.title = `${r.title} | Opponent Scout`;
  const title = el("input", { class: "input input-wide", type: "text", maxlength: "120", value: r.title, "aria-label": "Title" });
  const notes = el("textarea", { class: "textarea", rows: "10", maxlength: "10000", "aria-label": "Notes" });
  notes.value = r.notes || "";
  const message = el("p", { class: "side-message", role: "status" });
  const save = el("button", { type: "button", class: "btn btn-primary", text: "Save changes" });
  save.addEventListener("click", async () => {
    if (!title.value.trim()) { message.textContent = "Give the report a title."; message.className = "side-message loss"; title.focus(); return; }
    save.disabled = true; save.textContent = "Saving...";
    try {
      const payload = { title: title.value, notes: notes.value };
      if (r.ai_text) payload.ai_text = r.ai_text;
      const updated = await sendJSON("PUT", `/api/reports/${r.id}`, payload);
      r.title = updated.title; r.notes = updated.notes; r.updated_at = updated.updated_at;
      setMeta();
      document.title = `${r.title} | Opponent Scout`;
      message.textContent = `Saved at ${when(updated.updated_at)}.`;
      message.className = "side-message muted";
    } catch (err) {
      message.textContent = err.message;
      message.className = "side-message loss";
    }
    save.disabled = false; save.textContent = "Save changes";
  });

  const confirm = el("div", { class: "confirm-row", hidden: true });
  const del = el("button", { type: "button", class: "btn", text: "Delete report" });
  del.addEventListener("click", () => {
    const yes = el("button", { type: "button", class: "btn btn-danger", text: "Yes, delete" });
    const no = el("button", { type: "button", class: "btn", text: "Cancel" });
    fill(confirm, el("span", { text: "Delete this report? This cannot be undone." }), yes, no);
    confirm.hidden = false;
    no.addEventListener("click", () => { confirm.hidden = true; del.focus(); });
    yes.addEventListener("click", async () => {
      yes.disabled = true; yes.textContent = "Deleting...";
      try {
        await sendJSON("DELETE", `/api/reports/${r.id}`);
        window.location.href = "/reports";
      } catch (err) {
        fill(confirm, el("span", { text: err.message }), no);
      }
    });
    yes.focus();
  });

  const snap = r.matchup_snapshot;
  const metaLine = el("span", { class: "muted" });
  const setMeta = () => {
    metaLine.textContent = `Saved ${when(r.created_at)} with data through ${r.data_as_of ? formatDay(r.data_as_of) : "an unknown date"}. Last edited ${when(r.updated_at)}.`;
  };
  setMeta();
  fill(root,
    panel(r.title, null,
      el("div", { class: "report-meta" },
        el("span", { class: "opp" }, chip(r.us_abbr, { link: true }), el("span", { class: "muted", text: "vs" }), chip(r.them_abbr, { link: true })),
        el("span", { class: "text-2", text: r.game_date ? `Game ${formatDay(r.game_date, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}` : "No game linked" }),
        metaLine),
      el("div", { class: "form-body" },
        el("label", { class: "field" }, el("span", { class: "label", text: "Title" }), title),
        el("label", { class: "field" }, el("span", { class: "label", text: "Notes" }), notes),
        el("div", { class: "form-actions" }, save, del, message),
        confirm)),
    panel("Matchups as saved", "A snapshot from the moment of saving. It does not change when the data is refreshed.",
      snap ? [lineupLine(snap, r.us_abbr, r.them_abbr, { saved: true }), matchupTable(snap), matchupNotes(snap)]
        : el("p", { class: "state-line", text: "This report has no matchup snapshot." })),
    aiBlock(r));
}

// The saved AI text: editable sections (saved with "Save changes") and the
// facts it was written from.
function aiBlock(r) {
  const ai = r.ai_text;
  if (!ai || !ai.sections) return null;
  let meta = modelLine(ai);
  const sections = aiSections(ai, { onEdit: () => {
    const fresh = modelLine(ai);
    if (fresh.textContent !== meta.textContent) { meta.replaceWith(fresh); meta = fresh; }
  } });
  return [
    el("section", { class: "panel span-8", "aria-label": "AI scouting report" },
      el("div", { class: "panel-head", style: "justify-content: space-between" },
        el("h2", { class: "panel-title", text: "AI scouting report" }),
        el("span", { class: "panel-note", text: "Edit here, then Save changes above" })),
      sections, meta, el("div", { style: "height: 16px" })),
    ai.facts ? el("section", { class: "panel span-4", "aria-label": "Facts used" }, factsPanel(ai.facts)) : null,
  ];
}

load();
