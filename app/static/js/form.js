// "Season / Last 10" recent form toggle, shared by the scouting page, the
// team page and the player card. The choice lives in the address
// (?form=last10), so a refresh or a bookmark keeps it.

import { el } from "./api.js";

export const FORMS = { season: "Season", last10: "Last 10" };
export const SEASON_ONLY_NOTE = "Last 10 changes team stats, per-game stats, TS%, USG% and shot profiles. "
  + "Ratings, badges, matchups, on/off and the projection stay season numbers, because they have their own sample rules.";

export function currentForm() {
  const f = new URLSearchParams(window.location.search).get("form");
  return f === "last10" ? "last10" : "season";
}

// Add ?form=last10 to a URL (API call or page link) when Last 10 is on.
export function withForm(url, form = currentForm()) {
  if (form === "season") return url;
  return `${url}${url.includes("?") ? "&" : "?"}form=${form}`;
}

// Segmented control. onChange(form) runs after the address is updated.
export function formControl(onChange) {
  const now = currentForm();
  const buttons = Object.entries(FORMS).map(([key, label]) => el("button", {
    type: "button", "aria-pressed": String(key === now), dataset: { form: key }, text: label,
  }));
  const seg = el("div", { class: "seg form-seg", role: "group", "aria-label": "Season or last 10 games" }, buttons);
  for (const b of buttons) {
    b.addEventListener("click", () => {
      const form = b.dataset.form;
      if (form === currentForm()) return;
      const q = new URLSearchParams(window.location.search);
      if (form === "season") q.delete("form");
      else q.set("form", form);
      const qs = q.toString();
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
      for (const x of buttons) x.setAttribute("aria-pressed", String(x === b));
      onChange(form);
    });
  }
  return seg;
}

// "season" label for numbers the toggle does not change, shown only while
// Last 10 is on so the difference is clear.
export function seasonLabel(text = "Season") {
  return currentForm() === "last10" ? el("span", { class: "tag", title: SEASON_ONLY_NOTE, text }) : null;
}
