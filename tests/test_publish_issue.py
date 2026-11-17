import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from weather_tracker.publish_issue import GitHubIssueError, publish_report
from weather_tracker.report import ISSUE_MARKER, build_issue_report


def row(day, station_id, temperature):
    return {"date": day, "item_id": station_id, "item": station_id,
            "temperature_f": temperature}


def test_existing_dated_issue_is_updated_and_only_previous_marked_issue_closes():
    report = build_issue_report([
        row("2026-11-17", "KXNA", "41"), row("2026-11-18", "KXNA", "45")
    ])
    calls = []
    bodies = []

    def runner(args, **kwargs):
        calls.append(args)
        if args[1:3] == ["issue", "list"]:
            day = args[args.index("--search") + 1].split()[0]
            issues = (
                [{"number": 12, "title": day, "body": ISSUE_MARKER, "state": "OPEN"},
                 {"number": 99, "title": day, "body": "unrelated", "state": "OPEN"}]
                if day == "2026-11-18" else
                [{"number": 11, "title": day, "body": ISSUE_MARKER, "state": "OPEN"},
                 {"number": 98, "title": day, "body": "unrelated", "state": "OPEN"}]
            )
            return CompletedProcess(args, 0, json.dumps(issues), "")
        if "--body-file" in args:
            bodies.append(Path(args[args.index("--body-file") + 1]).read_text())
        return CompletedProcess(args, 0, "", "")

    result = publish_report(report, runner)

    assert result == {"date": "2026-11-18", "action": "updated", "closed_previous": 11}
    assert bodies == [report.body]
    assert [call[1:3] for call in calls] == [
        ["issue", "list"], ["issue", "edit"],
        ["issue", "list"], ["issue", "close"],
    ]
    assert calls[1][3] == "12"
    assert calls[-1][3] == "11"


def test_create_issue_when_missing_and_keep_unrelated_issue_open():
    report = build_issue_report([row("2026-11-17", "KXNA", "41")])
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        if args[1:3] == ["issue", "list"]:
            return CompletedProcess(args, 0, json.dumps([
                {"number": 90, "title": report.title, "body": "unrelated", "state": "OPEN"}
            ]), "")
        return CompletedProcess(args, 0, "https://github.com/example/issues/1\n", "")

    result = publish_report(report, runner)
    assert result["action"] == "created"
    assert result["closed_previous"] is None
    assert any(call[1:3] == ["issue", "create"] for call in calls)
    assert not any(call[1:3] == ["issue", "close"] for call in calls)


def test_gh_error_includes_exit_code_and_redacts_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "secret-test-token")
    report = build_issue_report([row("2026-11-17", "KXNA", "41")])

    def runner(args, **kwargs):
        return CompletedProcess(args, 4, "", "authentication secret-test-token failed")

    with pytest.raises(GitHubIssueError, match="gh issue list exited 4") as error:
        publish_report(report, runner)
    assert "secret-test-token" not in str(error.value)
    assert "[redacted]" in str(error.value)
