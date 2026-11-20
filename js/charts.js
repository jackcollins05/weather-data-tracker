const NS = "http://www.w3.org/2000/svg";
const PALETTE = ["#acc6d6", "#c9b595", "#a9b9ff", "#bb9da9", "#a4bcaa", "#9acdec", "#dbb9f0", "#f0aa8b", "#b3d57b", "#d8b58e", "#8dc4c7", "#bcaee8"];

function svgNode(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}

function empty(container, message) {
  const note = document.createElement("p");
  note.className = "chart-empty";
  note.textContent = message;
  container.replaceChildren(note);
}

export function drawLineChart(container, series, unit = "") {
  const all = series.flatMap((item) => item.points.filter((point) => Number.isFinite(point.value)));
  if (!all.length) { empty(container, "No readings available for this chart yet."); return; }
  const dates = [...new Set(series.flatMap((item) => item.points.map((point) => point.date)))].sort();
  const values = all.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.12, 0.5);
  const low = min - pad;
  const high = max + pad;
  const width = Math.min(720, Math.max(365, container.clientWidth)), height = 235, left = 58, right = 18, top = 20, bottom = 42;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const x = (date) => left + (dates.length === 1 ? plotWidth / 2 : dates.indexOf(date) * plotWidth / (dates.length - 1));
  const y = (value) => top + (high - value) * plotHeight / (high - low);
  const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": `Time-series chart, ${unit}` });
  for (let tick = 0; tick < 4; tick += 1) {
    const value = low + (high - low) * tick / 3;
    const yy = y(value);
    svg.append(svgNode("line", { x1: left, x2: width - right, y1: yy, y2: yy, stroke: "#293742", "stroke-width": 1 }),
      svgNode("text", { x: left - 9, y: yy + 4, fill: "#9ab1c0", "font-size": 12, "text-anchor": "end" },
        Number(value.toFixed(1)).toString()));
  }
  const first = dates[0], last = dates.at(-1);
  svg.append(svgNode("text", { x: x(first), y: height - 14, fill: "#9ab1c0", "font-size": 12, "text-anchor": dates.length === 1 ? "middle" : "start" }, first));
  if (last !== first) svg.append(svgNode("text", { x: x(last), y: height - 14, fill: "#9ab1c0", "font-size": 12, "text-anchor": "end" }, last));
  series.forEach((item, index) => {
    const color = PALETTE[index % PALETTE.length];
    const points = new Map(item.points.map((point) => [point.date, point.value]));
    let path = "";
    let active = false;
    for (const date of dates) {
      const value = points.get(date);
      if (!Number.isFinite(value)) { active = false; continue; }
      path += `${active ? " L" : " M"}${x(date).toFixed(1)} ${y(value).toFixed(1)}`;
      active = true;
    }
    svg.append(svgNode("path", { d: path.trim(), fill: "none", stroke: color, "stroke-width": 2.5, "stroke-linecap": "round", "stroke-linejoin": "round" }));
    if (dates.length === 1) {
      const value = points.get(first);
      if (Number.isFinite(value)) svg.append(svgNode("circle", { cx: x(first), cy: y(value), r: 4, fill: color }));
    }
  });
  const legend = document.createElement("div");
  legend.className = "chart-legend";
  series.forEach((item, index) => {
    if (!item.points.some((point) => Number.isFinite(point.value))) return;
    const label = document.createElement("span");
    label.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = PALETTE[index % PALETTE.length];
    label.append(swatch, document.createTextNode(item.label));
    legend.append(label);
  });
  container.replaceChildren(svg, legend);
}

export function drawBarChart(container, entries, unit = "", highlight = null) {
  const valid = entries.filter((entry) => Number.isFinite(entry.value));
  if (!valid.length) { empty(container, "Not enough observations for this finding yet."); return; }
  const width = Math.min(720, Math.max(365, container.clientWidth)), left = Math.min(154, width * .26), right = 78, rowHeight = 30;
  const height = valid.length * rowHeight + 24;
  const max = Math.max(...valid.map((entry) => entry.value), 1);
  const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": `Comparison chart, ${unit}` });
  valid.forEach((entry, index) => {
    const y = index * rowHeight + 8;
    const barWidth = Math.max(2, entry.value / max * (width - left - right));
    svg.append(svgNode("text", { x: left - 10, y: y + 15, fill: "#b8cad6", "font-size": 12, "text-anchor": "end" }, entry.label),
      svgNode("rect", { x: left, y, width: barWidth, height: 19, rx: 1, fill: entry.id === highlight ? "#c9b595" : "#627785" }),
      svgNode("text", { x: left + barWidth + 7, y: y + 15, fill: "#d9e9ef", "font-size": 12 }, `${Number(entry.value.toFixed(1))}${unit}`));
  });
  container.replaceChildren(svg);
}
