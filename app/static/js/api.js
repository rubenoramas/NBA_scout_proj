// Shared helpers: fetch JSON with plain-language errors, and build DOM nodes.

// Fetch JSON from our API. Throws an Error whose message is safe to show.
export async function getJSON(url) {
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(10000) });
  } catch (err) {
    if (err.name === "TimeoutError") {
      throw new Error("The server took too long to answer. Try again.");
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
// handlers (onclick). Children can be nodes or strings. Text is always set
// with textContent, so data can never inject HTML.
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
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// A team abbreviation badge. Conference sets the accent color.
export function badge(abbreviation, { conference, size = "md" } = {}) {
  const conf = conference ? conference.toLowerCase() : "none";
  return el("span", { class: `badge badge-${size} conf-${conf}`, text: abbreviation || "?" });
}

// Loading skeleton with a hidden label for screen readers.
export function skeleton(rows = 3, label = "Loading") {
  return el("div", { class: "skeleton-wrap", role: "status" },
    el("span", { class: "sr-only", text: label }),
    Array.from({ length: rows }, () => el("div", { class: "skeleton" })));
}

// Error box with an optional retry button.
export function errorBox(message, onRetry) {
  return el("div", { class: "state state-error", role: "alert" },
    el("p", { text: message }),
    onRetry ? el("button", { class: "btn", type: "button", text: "Try again", onclick: onRetry }) : null);
}

export function emptyBox(message) {
  return el("div", { class: "state state-empty" }, el("p", { text: message }));
}

// "2026-11-20" -> Date at local midnight (avoids time zone shifts).
export function parseDay(text) {
  const [y, m, d] = text.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDay(text, options = { weekday: "short", month: "short", day: "numeric" }) {
  return parseDay(text).toLocaleDateString("en-US", options);
}

export function showAsOf(dateText) {
  const node = document.getElementById("asof");
  if (!node || !dateText) return;
  node.textContent = `Data as of ${formatDay(dateText, { month: "short", day: "numeric", year: "numeric" })}`;
  node.hidden = false;
}

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
