"""Build deterministic daily GitHub issue content from history rows."""

from dataclasses import dataclass
from decimal import Decimal


ISSUE_MARKER = "<!-- weather-data-tracker:daily-report -->"


@dataclass(frozen=True)
class TemperatureMove:
    item_id: str
    item: str
    old: Decimal
    new: Decimal
    change: Decimal


@dataclass(frozen=True)
class IssueReport:
    title: str
    body: str
    latest_successful_date: str | None
    previous_successful_date: str | None
    moves: tuple[TemperatureMove, ...]
    appeared: tuple[str, ...]
    gone: tuple[str, ...]


def _temperature(row: dict) -> Decimal | None:
    value = row.get("temperature_f")
    return None if value is None or value == "" else Decimal(str(value))


def _station_list(rows: dict[str, dict]) -> list[str]:
    return [f"- {rows[item_id]['item']} ({item_id})" for item_id in sorted(rows)]


def build_issue_report(history_rows: list[dict], report_date: str | None = None) -> IssueReport:
    """Compare the report date with the preceding successful history date."""
    dates = sorted({row["date"] for row in history_rows})
    if report_date is None:
        if not dates:
            raise ValueError("report_date is required when history has no rows")
        report_date = dates[-1]
    eligible_dates = [day for day in dates if day <= report_date]
    latest_date = eligible_dates[-1] if eligible_dates else None
    earlier_dates = [day for day in eligible_dates if day < report_date]
    previous_date = earlier_dates[-1] if earlier_dates else None
    current = {row["item_id"]: row for row in history_rows if row["date"] == report_date}
    previous = {row["item_id"]: row for row in history_rows if row["date"] == previous_date}

    if not current:
        body = [ISSUE_MARKER, f"## Observations for {report_date}", "",
                "No successful observations for this UTC date."]
        if latest_date:
            body.append(f"Most recent successful observation date: {latest_date}.")
        return IssueReport(report_date, "\n".join(body) + "\n", latest_date,
                           previous_date, (), (), ())

    if previous_date is None:
        body = [ISSUE_MARKER, f"## Observations for {report_date}", "",
                f"First successful observation date: {report_date}.", "",
                "### Current stations", *_station_list(current)]
        return IssueReport(report_date, "\n".join(body) + "\n", report_date,
                           None, (), tuple(sorted(current)), ())

    moves = []
    for item_id in current.keys() & previous.keys():
        old = _temperature(previous[item_id])
        new = _temperature(current[item_id])
        if old is not None and new is not None:
            moves.append(TemperatureMove(item_id, current[item_id]["item"], old, new, new - old))
    moves.sort(key=lambda move: (-abs(move.change), move.item_id))
    moves = tuple(moves[:5])
    appeared = tuple(sorted(current.keys() - previous.keys()))
    gone = tuple(sorted(previous.keys() - current.keys()))

    body = [ISSUE_MARKER, f"## Observations for {report_date}", "",
            f"Compared with previous successful date: {previous_date}.", "",
            "### Largest temperature moves", "",
            "| Station | Old (°F) | New (°F) | Change (°F) |",
            "| --- | ---: | ---: | ---: |"]
    if moves:
        for move in moves:
            body.append(
                f"| {move.item} ({move.item_id}) | {move.old:g} | {move.new:g} | "
                f"{move.change:+g} |"
            )
    else:
        body.append("| No comparable temperatures | — | — | — |")
    body.extend(["", "### Appeared stations",
                 *(_station_list({item_id: current[item_id] for item_id in appeared}) or ["None."]),
                 "", "### Disappeared stations",
                 *(_station_list({item_id: previous[item_id] for item_id in gone}) or ["None."])])
    return IssueReport(report_date, "\n".join(body) + "\n", report_date,
                       previous_date, moves, appeared, gone)
