from decimal import Decimal

from weather_tracker.report import ISSUE_MARKER, build_issue_report


def row(day, station_id, temperature):
    return {
        "date": day,
        "item_id": station_id,
        "item": f"Station {station_id}",
        "temperature_f": temperature,
    }


def test_first_successful_date_lists_current_stations_without_moves():
    rows = [row("2026-11-17", "KXNA", "41"), row("2026-11-17", "KATL", "70")]
    report = build_issue_report(rows)

    assert report.title == "2026-11-17"
    assert report.latest_successful_date == "2026-11-17"
    assert report.previous_successful_date is None
    assert report.moves == ()
    assert report.appeared == ("KATL", "KXNA")
    assert report.gone == ()
    assert "First successful observation date: 2026-11-17." in report.body
    assert "- Station KATL (KATL)" in report.body
    assert ISSUE_MARKER in report.body


def test_top_five_absolute_moves_keep_sign_and_skip_missing_values():
    old = "2026-11-17"
    new = "2026-11-18"
    rows = [
        row(old, "A", "10"), row(new, "A", "19"),
        row(old, "B", "10"), row(new, "B", "2"),
        row(old, "C", "10"), row(new, "C", "17"),
        row(old, "D", "10"), row(new, "D", "4"),
        row(old, "E", "10"), row(new, "E", "15"),
        row(old, "F", "10"), row(new, "F", "6"),
        row(old, "G", "10"), row(new, "G", ""),
        row(old, "H", ""), row(new, "H", "30"),
        row(old, "I", "10"), row(new, "I", "13"),
        row(old, "GONE", "40"), row(new, "NEW", "50"),
    ]

    report = build_issue_report(rows, new)

    assert report.title == new
    assert report.latest_successful_date == new
    assert report.previous_successful_date == old
    assert [move.item_id for move in report.moves] == ["A", "B", "C", "D", "E"]
    assert [move.change for move in report.moves] == [
        Decimal("9"), Decimal("-8"), Decimal("7"), Decimal("-6"), Decimal("5")
    ]
    assert report.appeared == ("NEW",)
    assert report.gone == ("GONE",)
    assert "| Station B (B) | 10 | 2 | -8 |" in report.body
    assert "| Station A (A) | 10 | 19 | +9 |" in report.body
    assert "- Station NEW (NEW)" in report.body
    assert "- Station GONE (GONE)" in report.body
    assert "Station G (G) |" not in report.body
    assert report.body == build_issue_report(list(reversed(rows)), new).body


def test_report_for_date_without_success_still_has_utc_date_title():
    report = build_issue_report([row("2026-11-17", "KXNA", 41)], "2026-11-18")

    assert report.title == "2026-11-18"
    assert report.latest_successful_date == "2026-11-17"
    assert report.moves == ()
    assert "No successful observations for this UTC date." in report.body
    assert "Most recent successful observation date: 2026-11-17." in report.body
