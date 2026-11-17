"""Rebuild observation history entirely from saved NWS HTML files."""

import csv
from dataclasses import dataclass
from datetime import date
import gzip
from pathlib import Path
import re
import zlib

from weather_tracker.parser import ObservationParseError, parse_observation
from weather_tracker.sources import STATIONS


SOURCE = "nws_obhistory"
COLUMNS = (
    "date",
    "item_id",
    "item",
    "source",
    "temperature_f",
    "dew_point_f",
    "relative_humidity_pct",
    "visibility_miles",
    "altimeter_inhg",
    "sea_level_pressure_mb",
)


@dataclass(frozen=True)
class HistoryBuildError:
    path: Path
    message: str


@dataclass
class HistoryBuildResult:
    rows: list[dict]
    errors: list[HistoryBuildError]


def _valid_utc_date(name: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", name):
        return False
    try:
        date.fromisoformat(name)
    except ValueError:
        return False
    return True


def build_history(raw_root: str | Path, output_path: str | Path) -> HistoryBuildResult:
    """Write a fresh, sorted CSV from configured station files under raw_root."""
    raw_root = Path(raw_root)
    rows = []
    errors = []

    if raw_root.is_dir():
        date_dirs = sorted(
            path for path in raw_root.iterdir()
            if path.is_dir() and _valid_utc_date(path.name)
        )
        for date_dir in date_dirs:
            for station_id, station_name in sorted(STATIONS.items()):
                path = date_dir / f"{station_id}.html.gz"
                if not path.is_file():
                    continue
                try:
                    with gzip.open(path, "rb") as file:
                        html = file.read().decode("utf-8-sig", errors="replace")
                    observation = parse_observation(html, station_id)
                except (OSError, EOFError, zlib.error, ObservationParseError, ValueError) as exc:
                    errors.append(HistoryBuildError(path=path, message=str(exc)))
                    continue

                rows.append({
                    "date": date_dir.name,
                    "item_id": station_id,
                    "item": station_name,
                    "source": SOURCE,
                    **{column: observation[column] for column in COLUMNS[4:]},
                })

    rows.sort(key=lambda row: (row["date"], row["item_id"]))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return HistoryBuildResult(rows=rows, errors=errors)
