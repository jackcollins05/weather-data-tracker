"""Derive daily status from saved raw dates and rebuilt history rows."""

import json
from pathlib import Path

from weather_tracker.history import _valid_utc_date
from weather_tracker.sources import STATIONS


def _successful_raw_dates(raw_root: Path) -> list[str]:
    if not raw_root.is_dir():
        return []
    return sorted(
        directory.name
        for directory in raw_root.iterdir()
        if directory.is_dir()
        and _valid_utc_date(directory.name)
        and any((directory / f"{station_id}.html.gz").is_file() for station_id in STATIONS)
    )


def build_status(
    raw_root: str | Path,
    history_rows: list[dict],
    latest_date: str,
    run_time: str,
    sources: list[dict],
) -> dict:
    """Summarize this UTC day against the preceding date with saved raw files."""
    dates = _successful_raw_dates(Path(raw_root))
    previous_dates = [day for day in dates if day < latest_date]
    previous_date = previous_dates[-1] if previous_dates else None
    current_ids = {row["item_id"] for row in history_rows if row["date"] == latest_date}
    previous_ids = {
        row["item_id"] for row in history_rows if row["date"] == previous_date
    }

    return {
        "run_time": run_time,
        "first_run_date": dates[0] if dates else None,
        "days_with_success": len(dates),
        "items": sum(row["date"] == latest_date for row in history_rows),
        "new_today": len(current_ids - previous_ids),
        "gone_today": len(previous_ids - current_ids),
        "sources": sources,
    }


def write_status(status: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(status, file, indent=2)
        file.write("\n")
