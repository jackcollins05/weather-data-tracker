"""Offline checks for the static GitHub Pages shell and its local assets."""

from html.parser import HTMLParser
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index.html", "browse.html", "trends.html")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])


def page(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_three_pages_share_navigation_and_manifest():
    for name in PAGES:
        text = page(name)
        links = Links()
        links.feed(text)
        assert {"./index.html", "./browse.html", "./trends.html"}.issubset(links.links)
        assert 'rel="manifest" href="./manifest.webmanifest"' in text
        assert './css/styles.css' in text
        assert "U.S. Weather Tracker" in text
        assert "data-message" in links.ids


def test_browse_has_search_filter_sort_and_star_hooks():
    links = Links()
    links.feed(page("browse.html"))
    assert {
        "station-search", "station-filter", "temperature-filter", "humidity-filter",
        "sort-field", "sort-direction", "starred-only", "browse-table",
    }.issubset(links.ids)
    script = (ROOT / "js/browse.js").read_text()
    assert "localStorage" in script
    assert '"dew_point_f"' in script
    assert '"sea_level_pressure_mb"' in script


def test_trends_has_six_charts_and_four_finding_hooks():
    links = Links()
    links.feed(page("trends.html"))
    assert {"station-selection", "metric-charts", "finding-sections",
            "finding-shift", "finding-spread", "finding-humidity",
            "finding-range"}.issubset(links.ids)
    script = (ROOT / "js/trends.js").read_text()
    assert "for (const metric of METRICS)" in script
    assert "drawLineChart" in script and "drawBarChart" in script


def test_local_assets_manifest_and_service_worker():
    for asset in ("js/common.js", "js/today.js", "js/browse.js", "js/trends.js",
                  "js/charts.js", "css/styles.css", "service-worker.js",
                  "manifest.webmanifest", "assets/icon.svg"):
        assert (ROOT / asset).is_file()
    manifest = json.loads((ROOT / "manifest.webmanifest").read_text())
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./index.html"
    assert {entry["sizes"] for entry in manifest["icons"]} == {"192x192", "512x512"}
    for entry in manifest["icons"]:
        icon = (ROOT / entry["src"]).read_bytes()
        assert icon[:8] == b"\x89PNG\r\n\x1a\n"
        size = int(entry["sizes"].split("x")[0])
        assert struct.unpack(">II", icon[16:24]) == (size, size)
    assert 'register("./service-worker.js")' in (ROOT / "js/common.js").read_text()
    worker = (ROOT / "service-worker.js").read_text()
    assert "cache.addAll(SHELL)" in worker
    assert "DATA_CACHE" in worker and "cache.put(request, response.clone())" in worker


def test_site_has_no_external_render_dependencies():
    for name in (*PAGES, "js/common.js", "js/today.js", "js/browse.js",
                 "js/trends.js", "js/charts.js", "css/styles.css"):
        text = page(name)
        assert "<script src=\"https://" not in text
        assert "fonts.googleapis.com" not in text
        assert "Chart.js" not in text
        assert "cdn." not in text
