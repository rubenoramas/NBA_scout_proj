// Schedule spot tags: rest and travel facts for one team around one game,
// from the "spots" the API computes from the schedule. Facts only.

import { el, tag } from "./api.js";

function withTitle(node, title) {
  node.title = title;
  return node;
}

// spots: { rest_days, back_to_back, three_in_four, four_in_six,
//          games_in_4_nights, games_in_6_nights, stretch: { kind, game, games } }
export function spotTags(spots) {
  if (!spots) return [];
  const out = [];
  if (spots.rest_days === null || spots.rest_days === undefined) {
    out.push(withTitle(tag("First game"), "No earlier game this season."));
  } else if (spots.back_to_back) {
    out.push(withTitle(tag("Back-to-back"), "Played the day before."));
  } else {
    out.push(withTitle(tag(`${spots.rest_days} day${spots.rest_days === 1 ? "" : "s"} rest`),
      "Full days without a game before this one."));
  }
  if (spots.four_in_six) {
    out.push(withTitle(tag(`${spots.games_in_6_nights} in 6 nights`), "Games in the 6 nights ending with this one."));
  } else if (spots.three_in_four) {
    out.push(withTitle(tag(`${spots.games_in_4_nights} in 4 nights`), "Games in the 4 nights ending with this one."));
  }
  const s = spots.stretch;
  if (s && s.games > 1) {
    const name = s.kind === "road trip" ? "Road trip" : "Home stand";
    out.push(withTitle(tag(`${name} ${s.game} of ${s.games}`), `Game ${s.game} of ${s.games} in a row ${s.kind === "road trip" ? "away" : "at home"}.`));
  } else if (s) {
    out.push(withTitle(tag(s.kind === "road trip" ? "Single road game" : "Single home game"), "The games before and after are at the other venue."));
  }
  return out;
}

// A labeled row of tags, for the band and the schedule table.
export function spotLine(label, spots) {
  const tags = spotTags(spots);
  if (!tags.length) return null;
  return el("span", { class: "spot-line" }, label ? el("span", { class: "label", text: label }) : null, tags);
}
