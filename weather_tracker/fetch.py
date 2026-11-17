"""Download and preserve raw NWS observation-history pages."""

from dataclasses import dataclass
import gzip
from http.client import HTTPException
from pathlib import Path
from urllib.request import Request, urlopen

from weather_tracker.sources import STATIONS


BASE_URL = "https://forecast.weather.gov/data/obhistory"
USER_AGENT = "WeatherDataTracker/0.1 (course project; public NWS observations)"
TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class FetchResult:
    station_id: str
    url: str
    html: bytes | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def station_url(station_id: str) -> str:
    """Build the public imperial observation-history URL."""
    return f"{BASE_URL}/{station_id}.html"


def fetch_station(station_id: str, opener=urlopen) -> FetchResult:
    """Download one station, returning an error instead of raising for HTTP failures."""
    url = station_url(station_id)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            html = response.read()
    except (OSError, HTTPException) as exc:
        return FetchResult(station_id=station_id, url=url, error=str(exc))
    return FetchResult(station_id=station_id, url=url, html=html)


def fetch_stations(opener=urlopen) -> dict[str, FetchResult]:
    """Fetch every configured station independently, in configuration order."""
    return {station_id: fetch_station(station_id, opener) for station_id in STATIONS}


def save_raw_html(html: bytes, path: str | Path) -> None:
    """Write the exact response bytes to a caller-chosen gzip file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destination, "wb") as file:
        file.write(html)
