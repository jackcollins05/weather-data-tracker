export const STATIONS = [
  { id: "KXNA", name: "Northwest Arkansas" },
  { id: "KLIT", name: "Little Rock" },
  { id: "KDFW", name: "Dallas/Fort Worth" },
  { id: "KIAH", name: "Houston" },
  { id: "KORD", name: "Chicago O'Hare" },
  { id: "KJFK", name: "New York JFK" },
  { id: "KLAX", name: "Los Angeles" },
  { id: "KDEN", name: "Denver" },
  { id: "KMIA", name: "Miami" },
  { id: "KSEA", name: "Seattle" },
  { id: "KBOS", name: "Boston" },
  { id: "KATL", name: "Atlanta" },
];

export const METRICS = [
  { key: "temperature_f", title: "Temperature", unit: "°F", digits: 1 },
  { key: "dew_point_f", title: "Dew point", unit: "°F", digits: 1 },
  { key: "relative_humidity_pct", title: "Relative humidity", unit: "%", digits: 0 },
  { key: "visibility_miles", title: "Visibility", unit: "mi", digits: 2 },
  { key: "altimeter_inhg", title: "Altimeter", unit: "inHg", digits: 2 },
  { key: "sea_level_pressure_mb", title: "Sea level pressure", unit: "mb", digits: 1 },
];

const DATA_CACHE = "weather-data-v1";
const numericKeys = METRICS.map((metric) => metric.key);

export function parseCSV(text) {
  const records = [];
  let record = [];
  let field = "";
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') { field += '"'; index += 1; }
      else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") { record.push(field); field = ""; }
    else if (char === "\n") {
      record.push(field.replace(/\r$/, ""));
      if (record.some((value) => value !== "")) records.push(record);
      record = []; field = "";
    } else field += char;
  }
  if (field !== "" || record.length) { record.push(field.replace(/\r$/, "")); records.push(record); }
  const [headers = [], ...values] = records;
  return values.map((cells) => {
    const row = {};
    headers.forEach((header, index) => { row[header] = cells[index] ?? ""; });
    numericKeys.forEach((key) => {
      const raw = row[key];
      row[key] = raw === "" || raw === undefined || !Number.isFinite(Number(raw)) ? null : Number(raw);
    });
    return row;
  }).filter((row) => row.date && row.item_id);
}

async function loadText(path) {
  const url = new URL(path, document.baseURI);
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if ("caches" in window) {
      try { const cache = await caches.open(DATA_CACHE); await cache.put(url, response.clone()); }
      catch { /* Cache storage is optional; the fetched response still works. */ }
    }
    return await response.text();
  } catch (error) {
    if ("caches" in window) {
      const cached = await caches.match(url).catch(() => null);
      if (cached) return await cached.text();
    }
    throw error;
  }
}

export async function loadData() {
  const [statusResult, historyResult] = await Promise.allSettled([
    loadText("./data/status.json"), loadText("./data/history.csv"),
  ]);
  let status = null;
  let history = [];
  const problems = [];
  if (statusResult.status === "fulfilled") {
    try { status = JSON.parse(statusResult.value); }
    catch { problems.push("status.json could not be read"); }
  } else problems.push("status.json is not available yet");
  if (historyResult.status === "fulfilled") {
    try { history = parseCSV(historyResult.value); }
    catch { problems.push("history.csv could not be read"); }
  } else problems.push("history.csv is not available yet");
  return { status, history, problems };
}

export function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./service-worker.js").catch(() => {});
  }
}

export function showDataMessage(data) {
  const target = document.querySelector("#data-message");
  if (!target) return;
  if (data.problems.length) {
    target.dataset.kind = "warning";
    target.textContent = `${data.problems.join("; ")}. Available observations remain visible, and saved offline copies are used when available.`;
  } else if (!data.history.length) {
    target.dataset.kind = "warning";
    target.textContent = "No observations have been recorded yet. Check back after the first successful daily run.";
  } else {
    target.dataset.kind = "ready";
    target.textContent = "Observation data loaded.";
  }
}

export function latestDates(history) {
  const dates = [...new Set(history.map((row) => row.date))].sort();
  return { latest: dates.at(-1) ?? null, previous: dates.at(-2) ?? null };
}

export function rowsOn(history, date) {
  return new Map(history.filter((row) => row.date === date).map((row) => [row.item_id, row]));
}

export function latestByStation(history) {
  const rows = new Map();
  for (const row of history) {
    if (!rows.has(row.item_id) || rows.get(row.item_id).date < row.date) rows.set(row.item_id, row);
  }
  return rows;
}

export function temperatureMoves(history) {
  const { latest, previous } = latestDates(history);
  if (!latest || !previous) return [];
  const current = rowsOn(history, latest);
  const prior = rowsOn(history, previous);
  return [...current].flatMap(([id, row]) => {
    const before = prior.get(id);
    if (!before || row.temperature_f === null || before.temperature_f === null) return [];
    return [{ id, name: row.item || STATIONS.find((station) => station.id === id)?.name || id,
      old: before.temperature_f, value: row.temperature_f, change: row.temperature_f - before.temperature_f }];
  }).sort((a, b) => Math.abs(b.change) - Math.abs(a.change) || a.id.localeCompare(b.id));
}

export function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

export function formatMetric(value, key) {
  const metric = METRICS.find((item) => item.key === key);
  return formatNumber(value, metric?.digits ?? 1);
}

export function formatDelta(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatNumber(Math.abs(value), 1)}°F`;
}

export function formatRunTime(value) {
  if (!value) return "Awaiting first run";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(date)} UTC`;
}

export function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
