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

export function chip(abbreviation, { fixed = false, xl = false } = {}) {
  const cls = ["chip", fixed && "fixed", xl && "chip-xl"].filter(Boolean).join(" ");
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
