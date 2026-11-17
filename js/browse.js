import {
  STATIONS, create, formatMetric, formatRunTime, latestByStation, latestDates,
  loadData, registerServiceWorker, showDataMessage,
} from "./common.js";

registerServiceWorker();

const STAR_KEY = "weather-tracker-stars-v1";
const controls = {
  search: document.getElementById("station-search"),
  station: document.getElementById("station-filter"),
  temperature: document.getElementById("temperature-filter"),
  humidity: document.getElementById("humidity-filter"),
  sort: document.getElementById("sort-field"),
  direction: document.getElementById("sort-direction"),
  starredOnly: document.getElementById("starred-only"),
};
let latestRows = new Map();
let stars = loadStars();

function loadStars() {
  try {
    const saved = JSON.parse(localStorage.getItem(STAR_KEY) || "[]");
    return new Set(Array.isArray(saved) ? saved.filter((id) => STATIONS.some((station) => station.id === id)) : []);
  } catch { return new Set(); }
}

function toggleStar(id) {
  if (stars.has(id)) stars.delete(id); else stars.add(id);
  try { localStorage.setItem(STAR_KEY, JSON.stringify([...stars].sort())); }
  catch { /* Browsing still works if storage is unavailable. */ }
  render();
}

function matchesBand(value, band, cut1, cut2) {
  if (band === "all") return true;
  if (band === "missing") return value === null || value === undefined;
  if (value === null || value === undefined) return false;
  if (band === "cold" || band === "dry") return value < cut1;
  if (band === "mild" || band === "moderate") return value >= cut1 && value < cut2;
  return value >= cut2;
}

function filteredStations() {
  const query = controls.search.value.trim().toLowerCase();
  const key = controls.sort.value;
  const multiplier = controls.direction.dataset.direction === "asc" ? 1 : -1;
  return STATIONS.filter((station) => {
    const row = latestRows.get(station.id);
    return (!query || `${station.name} ${station.id}`.toLowerCase().includes(query))
      && (controls.station.value === "all" || station.id === controls.station.value)
      && (!controls.starredOnly.checked || stars.has(station.id))
      && matchesBand(row?.temperature_f, controls.temperature.value, 40, 80)
      && matchesBand(row?.relative_humidity_pct, controls.humidity.value, 40, 70);
  }).sort((a, b) => {
    const av = latestRows.get(a.id)?.[key];
    const bv = latestRows.get(b.id)?.[key];
    if (av == null && bv == null) return a.id.localeCompare(b.id);
    if (av == null) return 1;
    if (bv == null) return -1;
    return multiplier * (av - bv) || a.id.localeCompare(b.id);
  });
}

function render() {
  const body = document.getElementById("browse-table");
  const visible = filteredStations();
  document.getElementById("browse-count").textContent = `${visible.length} OF ${STATIONS.length} STATIONS`;
  document.getElementById("starred-count").textContent = `${stars.size} starred`;
  body.replaceChildren();
  if (!visible.length) {
    const row = create("tr");
    const cell = create("td", "empty-cell", "No stations match these controls.");
    cell.colSpan = 9;
    row.append(cell);
    body.append(row);
    return;
  }
  for (const station of visible) {
    const data = latestRows.get(station.id);
    const tr = create("tr");
    const starCell = create("td");
    const star = create("button", "star-button", stars.has(station.id) ? "★" : "☆");
    star.type = "button";
    star.setAttribute("aria-label", `${stars.has(station.id) ? "Remove" : "Add"} ${station.name} ${stars.has(station.id) ? "from" : "to"} starred shortlist`);
    star.setAttribute("aria-pressed", String(stars.has(station.id)));
    star.addEventListener("click", () => toggleStar(station.id));
    starCell.append(star);
    const name = create("td");
    name.append(create("span", "station-name", station.name), create("span", "station-id", station.id));
    tr.append(starCell, name, create("td", "", data?.date || "—"));
    for (const key of ["temperature_f", "dew_point_f", "relative_humidity_pct", "visibility_miles", "altimeter_inhg", "sea_level_pressure_mb"]) {
      const value = data ? formatMetric(data[key], key) : "—";
      tr.append(create("td", `num ${key === "temperature_f" ? "value-main" : ""}`,
        key === "relative_humidity_pct" && value !== "—" ? `${value}%` : value));
    }
    body.append(tr);
  }
}

for (const station of STATIONS) {
  const option = create("option", "", `${station.name} (${station.id})`);
  option.value = station.id;
  controls.station.append(option);
}
for (const control of [controls.search, controls.station, controls.temperature, controls.humidity, controls.sort, controls.starredOnly]) {
  control.addEventListener(control === controls.search ? "input" : "change", render);
}
controls.direction.addEventListener("click", () => {
  const asc = controls.direction.dataset.direction !== "asc";
  controls.direction.dataset.direction = asc ? "asc" : "desc";
  controls.direction.textContent = asc ? "Low → high" : "High → low";
  controls.direction.setAttribute("aria-label", asc ? "Sort ascending" : "Sort descending");
  render();
});

loadData().then((data) => {
  showDataMessage(data);
  latestRows = latestByStation(data.history);
  document.getElementById("browse-date").textContent = latestDates(data.history).latest || "Awaiting first run";
  document.getElementById("browse-run").textContent = formatRunTime(data.status?.run_time);
  render();
}).catch(() => {
  document.getElementById("data-message").textContent = "Observation data could not be loaded. Try again when a connection is available.";
  render();
});
