import gzip
from urllib.error import HTTPError

from weather_tracker.fetch import (
    TIMEOUT_SECONDS,
    USER_AGENT,
    fetch_station,
    fetch_stations,
    save_raw_html,
    station_url,
)
from weather_tracker.sources import STATIONS


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body


def test_station_url():
    assert station_url("KXNA") == "https://forecast.weather.gov/data/obhistory/KXNA.html"


def test_successful_download_uses_request_headers_and_timeout():
    body = b"<html>\r\nNWS observation\r\n</html>"
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(body)

    result = fetch_station("KXNA", opener)
    assert result.success
    assert result.error is None
    assert result.html == body
    assert calls[0][0].full_url == station_url("KXNA")
    assert calls[0][0].get_header("User-agent") == USER_AGENT
    assert calls[0][1] == TIMEOUT_SECONDS


def test_one_station_failure_does_not_stop_others():
    def opener(request, timeout):
        if request.full_url.endswith("/KLIT.html"):
            raise HTTPError(request.full_url, 503, "Service Unavailable", {}, None)
        return FakeResponse(b"<html>ok</html>")

    results = fetch_stations(opener)
    assert set(results) == set(STATIONS)
    assert not results["KLIT"].success
    assert results["KLIT"].html is None
    assert "503" in results["KLIT"].error
    assert results["KXNA"].success
    assert results["KXNA"].html == b"<html>ok</html>"
    assert results["KDFW"].success


def test_raw_gzip_round_trip_preserves_exact_bytes(tmp_path):
    original = b"<html>\r\nNWS \xc2\xb0F &amp; data\n</html>\n"
    path = tmp_path / "data" / "raw" / "2026-11-17" / "KXNA.html.gz"

    save_raw_html(original, path)

    with gzip.open(path, "rb") as file:
        assert file.read() == original
