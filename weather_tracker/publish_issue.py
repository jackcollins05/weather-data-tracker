"""Publish a dated report with GitHub CLI using the workflow's GH_TOKEN."""

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile

from weather_tracker.report import ISSUE_MARKER, IssueReport, build_issue_report


class GitHubIssueError(RuntimeError):
    """A GitHub CLI command failed."""


def _gh(args: list[str], runner=subprocess.run) -> str:
    try:
        result = runner(["gh", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise GitHubIssueError(f"Could not run gh {args[0]} {args[1]}: {exc}") from exc
    if result.returncode:
        stderr = result.stderr.strip()
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            secret = os.environ.get(name)
            if secret:
                stderr = stderr.replace(secret, "[redacted]")
        raise GitHubIssueError(
            f"gh {args[0]} {args[1]} exited {result.returncode}: "
            f"{stderr or 'no error details'}"
        )
    return result.stdout


def _find_report_issue(day: str, runner) -> dict | None:
    output = _gh([
        "issue", "list", "--state", "all", "--search", f"{day} in:title",
        "--limit", "100", "--json", "number,title,body,state",
    ], runner)
    matches = [
        issue for issue in json.loads(output)
        if issue["title"] == day and ISSUE_MARKER in (issue.get("body") or "")
    ]
    return max(matches, key=lambda issue: issue["number"], default=None)


def publish_report(report: IssueReport, runner=subprocess.run) -> dict:
    """Create or update today's marked issue and close the prior marked issue."""
    today = _find_report_issue(report.title, runner)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".md") as body_file:
        body_file.write(report.body)
        body_file.flush()
        if today:
            _gh(["issue", "edit", str(today["number"]), "--body-file", body_file.name], runner)
            if today["state"] == "CLOSED":
                _gh(["issue", "reopen", str(today["number"])], runner)
            action = "updated"
        else:
            _gh(["issue", "create", "--title", report.title,
                 "--body-file", body_file.name], runner)
            action = "created"

    closed_previous = None
    if report.previous_successful_date:
        previous = _find_report_issue(report.previous_successful_date, runner)
        if previous and previous["state"] == "OPEN":
            _gh(["issue", "close", str(previous["number"])], runner)
            closed_previous = previous["number"]
    return {"date": report.title, "action": action, "closed_previous": closed_previous}


def main() -> None:
    if not os.environ.get("GH_TOKEN"):
        raise GitHubIssueError("GH_TOKEN is required to publish the daily issue")
    with Path("data/history.csv").open(encoding="utf-8", newline="") as file:
        history_rows = list(csv.DictReader(file))
    status = json.loads(Path("data/status.json").read_text(encoding="utf-8"))
    run_at = datetime.fromisoformat(status["run_time"].replace("Z", "+00:00"))
    report_date = run_at.astimezone(timezone.utc).date().isoformat()
    report = build_issue_report(history_rows, report_date)
    print(json.dumps(publish_report(report)))


if __name__ == "__main__":
    main()
