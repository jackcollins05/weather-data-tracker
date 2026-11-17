"""Fetch today's NWS pages, then rebuild history and status."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from weather_tracker.fetch import FetchResult, fetch_stations, save_raw_html
from weather_tracker.history import HistoryBuildResult, build_history
from weather_tracker.sources import STATIONS
from weather_tracker.status import build_status, write_status


@dataclass
class DailyRunResult:
    source_results: dict[str, FetchResult]
    history: HistoryBuildResult
    status: dict

    def summary(self) -> dict:
        return {
            "successful_sources": [
                station_id for station_id, result in self.source_results.items()
                if result.success and result.html is not None
            ],
            "failed_sources": {
                station_id: result.error or "No response bytes"
                for station_id, result in self.source_results.items()
                if not result.success or result.html is None
            },
            "build_errors": [
                {"path": str(error.path), "message": error.message}
                for error in self.history.errors
            ],
        }


def run_daily(
    data_dir: str | Path = "data",
    *,
    now: datetime | None = None,
    fetcher=fetch_stations,
) -> DailyRunResult:
    """Run one UTC day's fetch and rebuild, with injectable time and fetcher."""
    run_at = now or datetime.now(timezone.utc)
    if run_at.tzinfo is None or run_at.utcoffset() is None:
        raise ValueError("now must have a timezone")
    run_at = run_at.astimezone(timezone.utc)
    latest_date = run_at.date().isoformat()
    run_time = run_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    data_dir = Path(data_dir)
    raw_root = data_dir / "raw"
    today_dir = raw_root / latest_date

    fetched = fetcher()
    today_dir.mkdir(parents=True, exist_ok=True)
    for station_id in STATIONS:
        (today_dir / f"{station_id}.html.gz").unlink(missing_ok=True)

    source_results = {}
    sources = []
    for station_id in STATIONS:
        result = fetched.get(station_id) or FetchResult(
            station_id=station_id, url="", error="No fetch result"
        )
        source_results[station_id] = result
        saved = result.success and result.html is not None
        if saved:
            save_raw_html(result.html, today_dir / f"{station_id}.html.gz")
        sources.append({"name": station_id, "ok": saved, "count": int(saved)})

    history = build_history(raw_root, data_dir / "history.csv")
    status = build_status(raw_root, history.rows, latest_date, run_time, sources)
    write_status(status, data_dir / "status.json")
    return DailyRunResult(source_results=source_results, history=history, status=status)


def main() -> None:
    print(json.dumps(run_daily().summary(), indent=2))


if __name__ == "__main__":
    main()
