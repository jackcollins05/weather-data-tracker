import {
  STATIONS, create, formatDelta, formatMetric, formatNumber, formatRunTime,
  latestByStation, latestDates, loadData, registerServiceWorker,
  rowsOn, showDataMessage, temperatureMoves,
} from "./common.js";

registerServiceWorker();

function renderCounts(status) {
  const values = {
    "count-items": status?.items,
    "count-new": status?.new_today,
    "count-gone": status?.gone_today,
    "count-days": status?.days_with_success,
  };
  for (const [id, value] of Object.entries(values)) {
    document.getElementById(id).textContent = value ?? "—";
  }
  document.getElementById("first-run").textContent = `First run: ${status?.first_run_date || "—"}`;
  document.getElementById("last-run").textContent = formatRunTime(status?.run_time);
}

function renderSources(status) {
  const container = document.getElementById("source-status");
  container.replaceChildren();
  const sourceMap = new Map((status?.sources || []).map((source) => [source.name, source]));
  for (const station of STATIONS) {
    const source = sourceMap.get(station.id);
    const chip = create("div", "source-chip");
    chip.title = `${station.name}: ${source ? source.ok ? "fetched" : "fetch failed" : "no run yet"}`;
    chip.append(create("span", `status-dot ${source ? source.ok ? "ok" : "bad" : ""}`),
      create("strong", "", station.id), create("span", "", station.name));
    container.append(chip);
  }
}

function renderMoves(history) {
  const container = document.getElementById("biggest-moves");
  const context = document.getElementById("moves-context");
  const { latest, previous } = latestDates(history);
  const moves = temperatureMoves(history).slice(0, 5);
  container.replaceChildren();
  container.classList.remove("empty-state");
  context.textContent = previous
    ? `Latest ${latest} compared with previous successful date ${previous}. Ranked by absolute temperature change.`
    : "Temperature moves appear after two successful observation dates.";
  if (!moves.length) {
    container.append(create("p", "empty-state", previous ? "No comparable temperature readings yet." : "Waiting for a second observation date."));
    return;
  }
  moves.forEach((move, index) => {
    const row = create("div", "move-row");
    const station = create("div");
    station.append(create("span", "move-name", move.name),
      create("span", "move-detail", `${move.id} · ${formatNumber(move.old)}°F → ${formatNumber(move.value)}°F`));
    row.append(create("span", "move-rank", String(index + 1)), station,
      create("span", "move-delta", formatDelta(move.change)));
    container.append(row);
  });
}

function renderTable(history) {
  const { latest, previous } = latestDates(history);
  const latestRows = latestByStation(history);
  const todayRows = rowsOn(history, latest);
  const priorRows = rowsOn(history, previous);
  const body = document.getElementById("today-table");
  document.getElementById("latest-date").textContent = latest ? `Latest observation date: ${latest}` : "No observation date yet";
  document.getElementById("table-date").textContent = latest ? `${latest} · UTC` : "NO DATA YET";
  body.replaceChildren();
  for (const station of STATIONS) {
    const row = latestRows.get(station.id);
    const current = todayRows.get(station.id);
    const previousRow = priorRows.get(station.id);
    const delta = current?.temperature_f != null && previousRow?.temperature_f != null
      ? current.temperature_f - previousRow.temperature_f : null;
    const tr = create("tr");
    const name = create("td");
    name.append(create("span", "station-name", station.name), create("span", "station-id", station.id));
    const asOf = create("td", "", row?.date || "—");
    if (row && row.date !== latest) asOf.append(create("span", "stale", "OLDER"));
    tr.append(name, asOf);
    const values = [
      row ? formatMetric(row.temperature_f, "temperature_f") : "—",
      formatDelta(delta),
      row ? formatMetric(row.dew_point_f, "dew_point_f") : "—",
      row?.relative_humidity_pct == null ? "—" : `${formatMetric(row.relative_humidity_pct, "relative_humidity_pct")}%`,
      row ? formatMetric(row.visibility_miles, "visibility_miles") : "—",
      row ? formatMetric(row.altimeter_inhg, "altimeter_inhg") : "—",
      row ? formatMetric(row.sea_level_pressure_mb, "sea_level_pressure_mb") : "—",
    ];
    values.forEach((value, index) => {
      const cell = create("td", `num ${index === 0 ? "value-main" : ""}`, value);
      if (index === 1 && delta !== null) cell.classList.add(delta > 0 ? "positive" : delta < 0 ? "negative" : "zero");
      tr.append(cell);
    });
    body.append(tr);
  }
}

loadData().then((data) => {
  showDataMessage(data);
  renderCounts(data.status);
  renderSources(data.status);
  renderMoves(data.history);
  renderTable(data.history);
}).catch(() => {
  document.getElementById("data-message").textContent = "Observation data could not be loaded. Try again when a connection is available.";
});
