import csv

from weather_tracker.fetch import save_raw_html
from weather_tracker.history import COLUMNS, SOURCE, build_history


def html(temperature="41", dew_point="34", humidity="76%", visibility="10.00",
         altimeter="30.47", sea_level="1032.3"):
    return f"""<table class="obs-history">
<thead>
  <tr><th rowspan="2">Date</th><th rowspan="2">Time (cst)</th>
      <th rowspan="2">Vis. (mi.)</th><th colspan="2">Temperature (ºF)</th>
      <th rowspan="2">Relative Humidity</th><th colspan="2">Pressure</th></tr>
  <tr><th>Air</th><th>Dwpt</th><th>altimeter (in)</th><th>sea level (mb)</th></tr>
</thead>
<tbody><tr><td>17</td><td>08:53</td><td>{visibility}</td><td>{temperature}</td>
<td>{dew_point}</td><td>{humidity}</td><td>{altimeter}</td><td>{sea_level}</td></tr></tbody>
</table>""".encode("utf-8")


def save(raw_root, day, station_id, body):
    path = raw_root / day / f"{station_id}.html.gz"
    save_raw_html(body, path)
    return path


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames, list(reader)


def test_multiple_dates_stations_schema_sorting_and_missing_values(tmp_path):
    raw_root = tmp_path / "raw"
    output = tmp_path / "history.csv"
    save(raw_root, "2026-11-18", "KXNA", html(temperature="45"))
    save(raw_root, "2026-11-17", "KXNA", html(dew_point="", humidity="M"))
    save(raw_root, "2026-11-17", "KATL", html(temperature="70"))

    result = build_history(raw_root, output)
    headers, rows = read_csv(output)

    assert result.errors == []
    assert headers == list(COLUMNS) == [
        "date", "item_id", "item", "source", "temperature_f", "dew_point_f",
        "relative_humidity_pct", "visibility_miles", "altimeter_inhg",
        "sea_level_pressure_mb",
    ]
    assert [(row["date"], row["item_id"]) for row in rows] == [
        ("2026-11-17", "KATL"), ("2026-11-17", "KXNA"),
        ("2026-11-18", "KXNA"),
    ]
    assert rows[0]["item"] == "Atlanta"
    assert rows[1]["item"] == "Northwest Arkansas"
    assert all(row["source"] == SOURCE == "nws_obhistory" for row in rows)
    assert rows[1]["dew_point_f"] == ""
    assert rows[1]["relative_humidity_pct"] == ""
    assert rows[1]["temperature_f"] == "41"
    assert rows[2]["temperature_f"] == "45"
    assert len(result.rows) == 3


def test_missing_stations_and_unrelated_paths_are_ignored(tmp_path):
    raw_root = tmp_path / "raw"
    output = tmp_path / "history.csv"
    save(raw_root, "2026-11-17", "KXNA", html())
    save(raw_root, "2026-11-17", "XXXX", b"not an NWS page")
    save(raw_root, "2026-11-31", "KATL", html())
    save(raw_root, "misc", "KATL", html())
    (raw_root / "2026-11-17" / "KLIT.html").write_bytes(html())
    (raw_root / "2026-11-17" / "notes.txt").write_text("ignore")

    result = build_history(raw_root, output)
    _, rows = read_csv(output)

    assert result.errors == []
    assert [(row["date"], row["item_id"]) for row in rows] == [("2026-11-17", "KXNA")]


def test_malformed_raw_files_are_reported_without_stopping_valid_files(tmp_path):
    raw_root = tmp_path / "raw"
    output = tmp_path / "history.csv"
    good = save(raw_root, "2026-11-17", "KXNA", html())
    corrupt = raw_root / "2026-11-17" / "KATL.html.gz"
    corrupt.write_bytes(b"not gzip")
    bad_html = save(raw_root, "2026-11-17", "KLIT", b"<html>No table</html>")

    result = build_history(raw_root, output)
    _, rows = read_csv(output)

    assert good.is_file()
    assert [row["item_id"] for row in rows] == ["KXNA"]
    assert [error.path for error in result.errors] == [corrupt, bad_html]
    assert all(error.message for error in result.errors)
    assert "Observation-history table not found" in result.errors[1].message


def test_rebuild_is_identical_and_same_day_replacement_updates_one_row(tmp_path):
    raw_root = tmp_path / "raw"
    output = tmp_path / "history.csv"
    save(raw_root, "2026-11-17", "KXNA", html(temperature="41"))

    build_history(raw_root, output)
    first = output.read_bytes()
    build_history(raw_root, output)
    assert output.read_bytes() == first

    save(raw_root, "2026-11-17", "KXNA", html(temperature="52"))
    result = build_history(raw_root, output)
    _, rows = read_csv(output)
    assert result.errors == []
    assert len(rows) == 1
    assert rows[0]["temperature_f"] == "52"
    assert output.read_bytes() != first
