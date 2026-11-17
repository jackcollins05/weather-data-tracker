import csv
from datetime import datetime
import gzip
import json

from weather_tracker.daily import run_daily
from weather_tracker.fetch import FetchResult, station_url
from weather_tracker.sources import STATIONS


def html(temperature="41"):
    return f"""<table class="obs-history"><thead>
<tr><th rowspan="2">Date</th><th rowspan="2">Time (utc)</th>
<th rowspan="2">Vis. (mi.)</th><th colspan="2">Temperature (ºF)</th>
<th rowspan="2">Relative Humidity</th><th colspan="2">Pressure</th></tr>
<tr><th>Air</th><th>Dwpt</th><th>altimeter (in)</th><th>sea level (mb)</th></tr>
</thead><tbody><tr><td>17</td><td>08:53</td><td>10</td><td>{temperature}</td>
<td>34</td><td>76%</td><td>30.47</td><td>1032.3</td></tr></tbody></table>""".encode()


def fetcher(successes, *, temperature="41", malformed=None):
    malformed = malformed or set()

    def fetch():
        return {
            station_id: FetchResult(
                station_id=station_id,
                url=station_url(station_id),
                html=(b"<html>bad</html>" if station_id in malformed else html(temperature))
                if station_id in successes else None,
                error=None if station_id in successes else "HTTP 503",
            )
            for station_id in STATIONS
        }

    return fetch


def at(day):
    return datetime.fromisoformat(f"{day}T12:30:00+00:00")


def history_rows(data_dir):
    with (data_dir / "history.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_all_stations_succeed_on_first_day(tmp_path):
    data_dir = tmp_path / "data"
    result = run_daily(data_dir, now=at("2026-11-17"), fetcher=fetcher(set(STATIONS)))
    status = json.loads((data_dir / "status.json").read_text())

    assert status == result.status
    assert set(status) == {
        "run_time", "first_run_date", "days_with_success", "items",
        "new_today", "gone_today", "sources",
    }
    assert status["run_time"] == "2026-11-17T12:30:00Z"
    assert status["first_run_date"] == "2026-11-17"
    assert (status["days_with_success"], status["items"]) == (1, 12)
    assert (status["new_today"], status["gone_today"]) == (12, 0)
    assert status["sources"] == [
        {"name": station_id, "ok": True, "count": 1} for station_id in STATIONS
    ]
    assert len(history_rows(data_dir)) == 12
    for station_id in STATIONS:
        with gzip.open(data_dir / "raw" / "2026-11-17" / f"{station_id}.html.gz", "rb") as file:
            assert file.read() == html()
    assert len(result.summary()["successful_sources"]) == 12
    assert result.summary()["failed_sources"] == {}
    assert result.summary()["build_errors"] == []


def test_failure_does_not_stop_run_and_two_dates_show_new_and_gone(tmp_path):
    data_dir = tmp_path / "data"
    first = run_daily(data_dir, now=at("2026-11-17"), fetcher=fetcher({"KXNA", "KLIT"}))
    assert (first.status["new_today"], first.status["gone_today"]) == (2, 0)

    second = run_daily(data_dir, now=at("2026-11-18"), fetcher=fetcher({"KXNA", "KATL"}))
    assert second.status["first_run_date"] == "2026-11-17"
    assert (second.status["days_with_success"], second.status["items"]) == (2, 2)
    assert (second.status["new_today"], second.status["gone_today"]) == (1, 1)
    assert second.status["sources"][1] == {"name": "KLIT", "ok": False, "count": 0}
    assert second.summary()["failed_sources"]["KLIT"] == "HTTP 503"
    assert not (data_dir / "raw" / "2026-11-18" / "KLIT.html.gz").exists()
    assert [(row["date"], row["item_id"]) for row in history_rows(data_dir)] == [
        ("2026-11-17", "KLIT"), ("2026-11-17", "KXNA"),
        ("2026-11-18", "KATL"), ("2026-11-18", "KXNA"),
    ]


def test_same_day_rerun_removes_stale_station_only(tmp_path):
    data_dir = tmp_path / "data"
    raw_root = data_dir / "raw"
    run_daily(data_dir, now=at("2026-11-16"), fetcher=fetcher({"KATL"}))
    earlier = (raw_root / "2026-11-16" / "KATL.html.gz").read_bytes()
    run_daily(data_dir, now=at("2026-11-17"), fetcher=fetcher({"KXNA", "KLIT"}))
    unrelated = raw_root / "2026-11-17" / "notes.txt"
    unrelated.write_text("keep me")
    unknown = raw_root / "2026-11-17" / "XXXX.html.gz"
    unknown.write_bytes(b"keep me too")

    result = run_daily(
        data_dir, now=at("2026-11-17"), fetcher=fetcher({"KXNA"}, temperature="52")
    )

    assert result.status["days_with_success"] == 2
    assert result.status["items"] == 1
    assert (result.status["new_today"], result.status["gone_today"]) == (1, 1)
    assert not (raw_root / "2026-11-17" / "KLIT.html.gz").exists()
    assert (raw_root / "2026-11-16" / "KATL.html.gz").read_bytes() == earlier
    assert unrelated.read_text() == "keep me"
    assert unknown.read_bytes() == b"keep me too"
    rows = history_rows(data_dir)
    assert [(row["date"], row["item_id"]) for row in rows] == [
        ("2026-11-16", "KATL"), ("2026-11-17", "KXNA")
    ]
    assert rows[1]["temperature_f"] == "52"


def test_parse_error_is_reported_while_other_stations_build(tmp_path):
    data_dir = tmp_path / "data"
    result = run_daily(
        data_dir,
        now=at("2026-11-17"),
        fetcher=fetcher({"KXNA", "KLIT"}, malformed={"KLIT"}),
    )

    assert [row["item_id"] for row in history_rows(data_dir)] == ["KXNA"]
    assert result.status["items"] == 1
    assert result.status["days_with_success"] == 1
    assert len(result.history.errors) == 1
    assert result.history.errors[0].path.name == "KLIT.html.gz"
    assert "Observation-history table not found" in result.summary()["build_errors"][0]["message"]


def test_no_successful_fetch_has_empty_first_day(tmp_path):
    result = run_daily(tmp_path / "data", now=at("2026-11-17"), fetcher=fetcher(set()))
    assert result.status["first_run_date"] is None
    assert result.status["days_with_success"] == 0
    assert result.status["items"] == 0
    assert (result.status["new_today"], result.status["gone_today"]) == (0, 0)
    assert len(result.summary()["failed_sources"]) == 12
