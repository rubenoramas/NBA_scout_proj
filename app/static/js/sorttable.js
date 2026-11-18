// A small sortable table built on the design's CSS grid rows.
//
// columns: [{ key, label, value(row) for sorting, cell(row) -> node or text,
//             width ("54px"), align: "num" | "", className }]
// state:   { sortKey, sortDir }  (shared with the caller so it survives re-renders)

import { el } from "./api.js";

export function renderSortTable(container, { columns, rows, state, onSort, label, emptyNode }) {
  if (!rows.length) {
    container.replaceChildren(emptyNode || el("p", { class: "state-line", text: "Nothing to show." }));
    return;
  }
  const template = columns.map((c) => c.width || "minmax(0, 1fr)").join(" ");
  const minWidth = columns.reduce((sum, c) => sum + (parseInt(c.width, 10) || 180) + 8, 32);
  const col = columns.find((c) => c.key === state.sortKey) || columns[0];

  const sorted = [...rows].sort((a, b) => {
    const va = col.value(a);
    const vb = col.value(b);
    // Missing values always sort last, whichever direction.
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    const order = va < vb ? -1 : va > vb ? 1 : 0;
    return state.sortDir === "asc" ? order : -order;
  });

  const header = el("div", { class: "trow thead short-head", role: "row", style: `grid-template-columns: ${template}` },
    columns.map((c) => {
      const active = c.key === state.sortKey;
      return el("span", {
        role: "columnheader",
        class: c.align || "",
        "aria-sort": active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none",
      }, c.sortable === false ? c.label : el("button", {
        type: "button",
        class: `sort-btn${active ? " active" : ""}`,
        "aria-label": `Sort by ${c.label}`,
        onclick: () => {
          if (state.sortKey === c.key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
          else Object.assign(state, { sortKey: c.key, sortDir: c.firstDir || "desc" });
          onSort();
        },
      }, c.label, active ? el("span", { "aria-hidden": "true", text: state.sortDir === "asc" ? " ▲" : " ▼" }) : null));
    }));

  const body = sorted.map((row) =>
    el("div", { class: "trow", role: "row", style: `grid-template-columns: ${template}` },
      columns.map((c) => {
        const content = c.cell(row);
        return el("span", { role: "cell", class: `${c.align || ""} ${c.className || ""}`.trim() },
          content instanceof Node ? content : String(content ?? "–"));
      })));

  container.replaceChildren(el("div", { class: "table-scroll" },
    el("div", { role: "table", "aria-label": label, style: `min-width: ${minWidth}px` }, header, body)));
}
