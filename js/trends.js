import {
  METRICS, STATIONS, create, formatDelta, formatNumber, formatRunTime,
  latestDates, loadData, registerServiceWorker, showDataMessage,
} from "./common.js";
import { drawBarChart, drawLineChart } from "./charts.js";

registerServiceWorker();

let history = [];
const selected = new Set(STATIONS.map((station) => station.id));
const names = new Map(STATIONS.map((station) => [station.id, station.name]));

function stationName(id) { return names.get(id) || id; }
function shortName(id) { return id; }

function metricSeries(key, ids) {
  return ids.map((id) => ({
    label: shortName(id),
    points: history.filter((row) => row.item_id === id).sort((a, b) => a.date.localeCompare(b.date))
      .map((row) => ({ date: row.date, value: row[key] })),
  }));
}

function renderMetricCharts() {
  const container = document.getElementById("metric-charts");
  container.replaceChildren();
  const ids = STATIONS.filter((station) => selected.has(station.id)).map((station) => station.id);
  document.getElementById("selected-count").textContent = `${ids.length} SELECTED`;
  for (const metric of METRICS) {
    const card = create("article", "card chart-card");
    card.id = `chart-${metric.key}`;
    card.append(create("h3", "", metric.title), create("p", "chart-subtitle", `Daily observations · ${metric.unit}`));
    const chart = create("div", "chart-wrap");
    card.append(chart);
    container.append(card);
    drawLineChart(chart, metricSeries(metric.key, ids), metric.unit);
  }
}

function groupedByStation() {
  const grouped = new Map();
  for (const row of history) {
    if (!grouped.has(row.item_id)) grouped.set(row.item_id, []);
    grouped.get(row.item_id).push(row);
  }
  for (const rows of grouped.values()) rows.sort((a, b) => a.date.localeCompare(b.date));
  return grouped;
}

function finding(id, title, description, renderChart) {
  const card = document.getElementById(id);
  card.querySelector("h3").textContent = title;
  card.querySelector(".finding-description").textContent = description;
  renderChart(card.querySelector(".chart-wrap"));
}

function renderFindings() {
  const grouped = groupedByStation();
  const shifts = [];
  const averages = [];
  const ranges = [];
  for (const [id, rows] of grouped) {
    const temps = rows.filter((row) => Number.isFinite(row.temperature_f));
    if (temps.length >= 2) {
      const first = temps[0], last = temps.at(-1);
      shifts.push({ id, first, last, change: last.temperature_f - first.temperature_f });
      ranges.push({ id, value: Math.max(...temps.map((row) => row.temperature_f)) - Math.min(...temps.map((row) => row.temperature_f)), count: temps.length });
    }
    const humidities = rows.map((row) => row.relative_humidity_pct).filter(Number.isFinite);
    if (humidities.length) averages.push({ id, value: humidities.reduce((sum, value) => sum + value, 0) / humidities.length, count: humidities.length });
  }
  shifts.sort((a, b) => Math.abs(b.change) - Math.abs(a.change) || a.id.localeCompare(b.id));
  const shift = shifts[0];
  finding("finding-shift", shift ? `${stationName(shift.id)} has the largest first-to-latest shift` : "Largest first-to-latest temperature shift",
    shift ? `${stationName(shift.id)} moved from ${formatNumber(shift.first.temperature_f)}°F on ${shift.first.date} to ${formatNumber(shift.last.temperature_f)}°F on ${shift.last.date}: ${formatDelta(shift.change)} across ${grouped.get(shift.id).length} saved days.` : "Two non-missing temperature readings for one station are needed.",
    (chart) => drawLineChart(chart, shift ? metricSeries("temperature_f", [shift.id]) : [], "°F"));

  const daily = new Map();
  for (const row of history) {
    if (!Number.isFinite(row.temperature_f)) continue;
    if (!daily.has(row.date)) daily.set(row.date, []);
    daily.get(row.date).push(row.temperature_f);
  }
  const spreads = [...daily].filter(([, values]) => values.length >= 2)
    .map(([date, values]) => ({ id: date, label: date, value: Math.max(...values) - Math.min(...values), low: Math.min(...values), high: Math.max(...values), count: values.length }))
    .sort((a, b) => a.id.localeCompare(b.id));
  const widest = [...spreads].sort((a, b) => b.value - a.value || a.id.localeCompare(b.id))[0];
  finding("finding-spread", widest ? `${widest.id} has the widest station spread` : "Widest daily temperature spread",
    widest ? `${widest.count} stations ranged from ${formatNumber(widest.low)}°F to ${formatNumber(widest.high)}°F, a ${formatNumber(widest.value)}°F spread on ${widest.id}.` : "At least two stations with temperatures on one date are needed.",
    (chart) => drawBarChart(chart, spreads, "°F", widest?.id));

  averages.sort((a, b) => b.value - a.value || a.id.localeCompare(b.id));
  const humid = averages[0];
  finding("finding-humidity", humid ? `${stationName(humid.id)} has the highest average humidity` : "Highest average relative humidity",
    humid ? `Its mean is ${formatNumber(humid.value, 1)}% across ${humid.count} non-missing readings. Other station means are shown below.` : "A non-missing humidity reading is needed.",
    (chart) => drawBarChart(chart, averages.map((entry) => ({ ...entry, label: entry.id })), "%", humid?.id));

  ranges.sort((a, b) => b.value - a.value || a.id.localeCompare(b.id));
  const largestRange = ranges[0];
  finding("finding-range", largestRange ? `${stationName(largestRange.id)} has the greatest temperature range` : "Greatest temperature range",
    largestRange ? `Its maximum minus minimum is ${formatNumber(largestRange.value)}°F across ${largestRange.count} non-missing readings.` : "Two non-missing temperature readings for one station are needed.",
    (chart) => drawBarChart(chart, ranges.map((entry) => ({ ...entry, label: entry.id })), "°F", largestRange?.id));
}

const picker = document.getElementById("station-selection");
for (const station of STATIONS) {
  const label = create("label", "station-check");
  const checkbox = create("input");
  checkbox.type = "checkbox";
  checkbox.value = station.id;
  checkbox.checked = true;
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) selected.add(station.id); else selected.delete(station.id);
    renderMetricCharts();
  });
  label.append(checkbox, create("span", "", station.name), create("small", "", station.id));
  picker.append(label);
}
function chooseAll(checked) {
  selected.clear();
  picker.querySelectorAll("input").forEach((box) => {
    box.checked = checked;
    if (checked) selected.add(box.value);
  });
  renderMetricCharts();
}
document.getElementById("select-all").addEventListener("click", () => chooseAll(true));
document.getElementById("select-none").addEventListener("click", () => chooseAll(false));

loadData().then((data) => {
  showDataMessage(data);
  history = data.history;
  const dates = [...new Set(history.map((row) => row.date))].sort();
  document.getElementById("trend-window").textContent = dates.length ? `${dates[0]} → ${latestDates(history).latest}` : "Awaiting first run";
  document.getElementById("trend-run").textContent = formatRunTime(data.status?.run_time);
  renderMetricCharts();
  renderFindings();
}).catch(() => {
  document.getElementById("data-message").textContent = "Observation data could not be loaded. Try again when a connection is available.";
  renderMetricCharts();
  renderFindings();
});
