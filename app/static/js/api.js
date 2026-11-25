// Shared helpers: fetch JSON with plain-language errors, build DOM nodes,
// and the small components from docs/DESIGN.md.

// Fetch JSON from our API. Throws an Error whose message is safe to show.
export async function getJSON(url) {
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(10000) });
  } catch (err) {
    if (err.name === "TimeoutError") {
      throw new Error("The server took too long to answer.");
    }
    throw new Error("Could not reach the server. Check that the app is running.");
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON. Handled below.
  }
  if (!response.ok) {
    throw new Error((body && body.error) || `The server answered with an error (${response.status}).`);
  }
  if (body === null) {
    throw new Error("The server sent a reply that could not be read.");
  }
  return body;
}

// Create an element. attrs may include class, text, dataset and event
// handlers (onclick). Children can be nodes or strings; null and false are
// skipped. Text is always set with textContent, so data can never inject HTML.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Replace a container's content, skipping empty children.
export function fill(node, ...children) {
  node.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
}

// ---- Components ---------------------------------------------------------

// A team abbreviation chip. link: true makes it a link to the team page.
export function chip(abbreviation, { fixed = false, xl = false, link = false } = {}) {
  const cls = ["chip", fixed && "fixed", xl && "chip-xl", link && "chip-link"].filter(Boolean).join(" ");
  if (link && abbreviation) {
    return el("a", { class: cls, href: `/team/${encodeURIComponent(abbreviation)}`, text: abbreviation,
      "aria-label": `${abbreviation} team page` });
  }
  return el("span", { class: cls, text: abbreviation || "?" });
}

export function resultChip(result) {
  if (result !== "W" && result !== "L") return el("span", { class: "muted", text: "–" });
  return el("span", { class: `result ${result === "W" ? "w" : "l"}`, text: result });
}

export function tag(text, kind = "") {
  return el("span", { class: `tag${kind ? ` tag-${kind}` : ""}`, text });
}

export function chevron() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width", "9");
  svg.setAttribute("height", "9");
  svg.setAttribute("viewBox", "0 0 10 10");
  svg.setAttribute("fill", "none");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", "M3.5 2l3 3-3 3");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.5");
  svg.append(path);
  return svg;
}

// Skeleton rows shaped like table rows. widths are in px, one bar each.
export function skeletonRows(count = 5, widths = [96, 180, 32, 72, 48]) {
  const rows = [el("span", { class: "sr-only", role: "status", text: "Loading" })];
  for (let i = 0; i < count; i++) {
    rows.push(el("div", { class: "skel-row", "aria-hidden": "true" },
      widths.map((w) => el("span", { class: "skel", style: `width: ${w}px` }))));
  }
  return rows;
}

export function errorLine(message, onRetry) {
  return el("div", { class: "state-error", role: "alert" },
    el("span", { text: message }),
    onRetry ? el("button", { class: "btn", type: "button", text: "Try again", onclick: onRetry }) : null);
}

export function emptyLine(message) {
  return el("p", { class: "state-line", text: message });
}

// ---- Formatting ---------------------------------------------------------

// "2026-11-20" -> Date at local midnight (avoids time zone shifts).
export function parseDay(text) {
  const [y, m, d] = text.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDay(text, options = { weekday: "short", month: "short", day: "numeric" }) {
  return parseDay(text).toLocaleDateString("en-US", options);
}

export function ordinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

// "W 3" -> "W3"
export function shortStreak(streak) {
  return streak ? streak.replace(/\s+/g, "") : "–";
}

export function streakClass(streak) {
  if (!streak) return "";
  return streak.startsWith("W") ? "win" : streak.startsWith("L") ? "loss" : "";
}

// 2, "East" -> "2nd East"; short: "2nd E"
export function seedText(standing, { short = false } = {}) {
  if (!standing || !standing.seed) return "–";
  const conf = standing.conference || "";
  return `${ordinal(standing.seed)} ${short ? conf.charAt(0) : conf}`;
}

export const SEASON_TYPE_LABEL = {
  "regular-season": "Regular season",
  "nba-cup": "NBA Cup",
  "play-in": "Play-in",
  playoffs: "Playoffs",
};

// localStorage can throw in private windows. These never throw.
export const store = {
  get(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem(key, value); } catch { /* ignore */ }
  },
  remove(key) {
    try { localStorage.removeItem(key); } catch { /* ignore */ }
  },
};

export const MY_TEAM_KEY = "opponentScout.myTeam";

export function scoutUrl(usAbbr, themAbbr) {
  return `/scout?${new URLSearchParams({ us: usAbbr, them: themAbbr })}`;
}

// Injury status as a tag: Out in red, Doubtful and Questionable in gold
// (warning), Probable and Available muted.
export function injuryTag(injury) {
  if (!injury || !injury.status) return null;
  const s = injury.status;
  const kind = s === "Out" ? "loss" : s === "Doubtful" || s === "Questionable" ? "gold" : "";
  const node = tag(s, kind);
  if (injury.reason) node.title = injury.reason.replace(/^Injury\/Illness - /, "");
  return node;
}

// 77 -> 6'5"   78.75 -> 6'6.75"
export function feetInches(inches) {
  if (inches === null || inches === undefined) return null;
  const ft = Math.floor(inches / 12);
  const rest = Math.round((inches - ft * 12) * 100) / 100;
  return `${ft}'${rest}"`;
}

export function pct1(v) {
  return v === null || v === undefined ? "–" : (v * 100).toFixed(1);
}

// A badge tag with a tooltip that opens on hover and on keyboard focus.
// tipLines: lines of plain text shown in the tooltip.
let tipCount = 0;
export function badgeWithTip(label, tipLines, kind = "accent") {
  tipCount += 1;
  const id = `tip-${tipCount}`;
  return el("span", { class: "tip-wrap" },
    el("button", { type: "button", class: `tag tag-${kind} tag-button`, "aria-describedby": id }, label),
    el("span", { class: "tip", role: "tooltip", id },
      tipLines.filter(Boolean).map((line, i) => el("span", { class: i === 0 ? "tip-title" : "tip-line", text: line }))));
}

export function badgeTip(b) {
  return badgeWithTip(b.name, [b.name, b.meaning, `His numbers: ${b.detail}`, `Rule: ${b.rule}`, b.caveat]);
}

// Tooltips use fixed positioning so a scrolling table cannot clip them.
// This places each one under its trigger, kept inside the window.
function placeTip(wrap) {
  const tip = wrap.querySelector(":scope > .tip");
  if (!tip) return;
  const r = wrap.getBoundingClientRect();
  const width = Math.min(340, window.innerWidth - 16);
  const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8));
  tip.style.left = `${left}px`;
  tip.style.width = `${width}px`;
  tip.style.top = `${r.bottom + 6}px`;
}
document.addEventListener("mouseover", (e) => {
  const wrap = e.target.closest && e.target.closest(".tip-wrap");
  if (wrap) placeTip(wrap);
});
document.addEventListener("focusin", (e) => {
  const wrap = e.target.closest && e.target.closest(".tip-wrap");
  if (wrap) placeTip(wrap);
});
// Escape closes an open tooltip by moving focus away from it.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.activeElement && document.activeElement.closest(".tip-wrap")) {
    document.activeElement.blur();
  }
});

// On/off: signed per-100 value, and the note shown wherever it appears.
export const ONOFF_NOTE = "On/off is noisy and depends on who a player shares the floor with, so read it alongside the other numbers.";
export function signed1(v) {
  return v === null || v === undefined ? "–" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
}

// "1" -> "1st", "22" -> "22nd"
export function rankText(rank) {
  if (!rank) return null;
  const sfx = ["th", "st", "nd", "rd"];
  const v = rank % 100;
  return rank + (sfx[(v - 20) % 10] || sfx[v] || sfx[0]);
}

// POST JSON to our API with the same plain-language errors as getJSON.
export async function postJSON(url, payload, { timeoutMs = 20000 } = {}) {
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    if (err.name === "TimeoutError") throw new Error("The server took too long to answer.");
    throw new Error("Could not reach the server. Check that the app is running.");
  }
  let body = null;
  try { body = await response.json(); } catch { /* handled below */ }
  if (!response.ok) throw new Error((body && body.error) || `The server answered with an error (${response.status}).`);
  if (body === null) throw new Error("The server sent a reply that could not be read.");
  return body;
}

// PUT or DELETE with the same plain-language errors. DELETE answers 204 with no body.
export async function sendJSON(method, url, payload) {
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: payload === undefined ? {} : { "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: AbortSignal.timeout(20000),
    });
  } catch (err) {
    if (err.name === "TimeoutError") throw new Error("The server took too long to answer.");
    throw new Error("Could not reach the server. Check that the app is running.");
  }
  if (response.status === 204) return null;
  let body = null;
  try { body = await response.json(); } catch { /* handled below */ }
  if (!response.ok) throw new Error((body && body.error) || `The server answered with an error (${response.status}).`);
  return body;
}
