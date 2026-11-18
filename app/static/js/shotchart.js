// Half court shot chart in SVG.
//
// Coordinates are the NBA's legacy units: tenths of a foot, basket at
// (0, 0), baseline at y = -47.5, half court at y = 422.5. SVG y grows
// downward, so the basket sits at the top of the drawing.
//
// Makes are filled accent dots; misses are hollow muted rings. Shape, not
// only color, tells them apart, so the chart works for color-blind viewers.

const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function courtLines() {
  const g = svgEl("g", { class: "court-lines", fill: "none" });
  const add = (tag, attrs) => g.append(svgEl(tag, attrs));
  add("rect", { x: -250, y: -47.5, width: 500, height: 470 });           // half court boundary
  add("rect", { x: -80, y: -47.5, width: 160, height: 190 });            // paint, 16 ft wide
  add("rect", { x: -60, y: -47.5, width: 120, height: 190 });            // inner lane lines
  add("path", { d: "M -60 142.5 A 60 60 0 0 0 60 142.5" });              // free throw circle, top half
  add("path", { d: "M -60 142.5 A 60 60 0 0 1 60 142.5", "stroke-dasharray": "5 5" });
  add("path", { d: "M -40 0 A 40 40 0 0 0 40 0" });                       // restricted area, 4 ft
  add("line", { x1: -30, y1: -7.5, x2: 30, y2: -7.5 });                   // backboard
  add("circle", { cx: 0, cy: 0, r: 7.5 });                                // rim
  // Three point line: straight in the corners (22 ft), then a 23.75 ft arc.
  add("path", { d: "M -220 -47.5 L -220 92.5 A 237.5 237.5 0 0 0 220 92.5 L 220 -47.5" });
  add("path", { d: "M -60 422.5 A 60 60 0 0 1 60 422.5" });               // center circle
  return g;
}

// shots: [{ x, y, made, shot_type, distance, game_date }]
export function drawShotChart(shots, { label = "Shot chart" } = {}) {
  const svg = svgEl("svg", {
    viewBox: "-252 -50 504 474",
    class: "shotchart",
    role: "img",
    "aria-label": label,
  });
  svg.append(courtLines());
  const dots = svgEl("g", {});
  // Misses first, so makes draw on top.
  const ordered = [...shots].sort((a, b) => Number(a.made) - Number(b.made));
  for (const s of ordered) {
    // Heaves from past half court are clipped to the drawing.
    const y = Math.min(s.y, 418);
    const dot = s.made
      ? svgEl("circle", { cx: s.x, cy: y, r: 4.5, class: "shot-make" })
      : svgEl("circle", { cx: s.x, cy: y, r: 4, class: "shot-miss" });
    const title = svgEl("title", {});
    title.textContent = `${s.made ? "Made" : "Missed"} ${s.shot_type}, ${s.distance} ft`;
    dot.append(title);
    dots.append(dot);
  }
  svg.append(dots);
  return svg;
}

// A small legend that shows both marks.
export function chartLegend() {
  const svg = svgEl("svg", { width: 150, height: 14, viewBox: "0 0 150 14", "aria-hidden": "true" });
  svg.append(svgEl("circle", { cx: 7, cy: 7, r: 4.5, class: "shot-make" }));
  const t1 = svgEl("text", { x: 16, y: 11, class: "legend-text" });
  t1.textContent = "Made";
  svg.append(t1);
  svg.append(svgEl("circle", { cx: 67, cy: 7, r: 4, class: "shot-miss" }));
  const t2 = svgEl("text", { x: 76, y: 11, class: "legend-text" });
  t2.textContent = "Missed";
  svg.append(t2);
  return svg;
}
