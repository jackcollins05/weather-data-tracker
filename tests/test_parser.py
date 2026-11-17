import pytest

from weather_tracker.parser import ObservationParseError, parse_observation
from weather_tracker.sources import STATIONS


HEADER = """
<thead>
  <tr>
    <th rowspan="2">Date</th><th rowspan="2">Time (cst)</th>
    <th rowspan="2">Vis. (mi.)</th>
    <th colspan="2">Temperature (ºF)</th>
    <th rowspan="2">Relative Humidity</th>
    <th colspan="2">Pressure</th>
  </tr>
  <tr>
    <th>Air</th><th>Dwpt</th>
    <th>altimeter (in)</th><th>sea level (mb)</th>
  </tr>
</thead>
"""


def page(*rows):
    return f'<table class="obs-history">{HEADER}<tbody>{"".join(rows)}</tbody></table>'


def test_first_observation_and_numeric_conversion():
    html = page(
        "<tr><td>17</td><td>08:53</td><td>10.00</td><td>41</td>"
        "<td>34</td><td>76%</td><td>30.47</td><td>1032.3</td></tr>",
        "<tr><td>17</td><td>07:53</td><td>8</td><td>35.1</td>"
        "<td>30</td><td>82%</td><td>30.45</td><td>1031.9</td></tr>",
    )
    assert parse_observation(html, "KXNA") == {
        "station_id": "KXNA",
        "temperature_f": 41,
        "dew_point_f": 34,
        "relative_humidity_pct": 76,
        "visibility_miles": 10.0,
        "altimeter_inhg": 30.47,
        "sea_level_pressure_mb": 1032.3,
    }


def test_blank_and_missing_numeric_cells_are_none():
    html = page(
        "<tr><td>17</td><td>08:53</td><td></td><td>35.1</td>"
        "<td>M</td><td> </td><td>30.47</td></tr>"
    )
    result = parse_observation(html, "KXNA")
    assert result["temperature_f"] == 35.1
    assert result["dew_point_f"] is None
    assert result["relative_humidity_pct"] is None
    assert result["visibility_miles"] is None
    assert result["sea_level_pressure_mb"] is None


def test_missing_table_has_clear_error():
    with pytest.raises(ObservationParseError, match="Observation-history table not found for KXNA"):
        parse_observation("<html><body>No observations</body></html>", "KXNA")


def test_no_usable_row_has_clear_error():
    html = page("<tr><td>17</td><td>08:53</td>" + "<td></td>" * 6 + "</tr>")
    with pytest.raises(ObservationParseError, match="No usable observation row found for KXNA"):
        parse_observation(html, "KXNA")


def test_locked_station_configuration():
    assert STATIONS == {
        "KXNA": "Northwest Arkansas",
        "KLIT": "Little Rock",
        "KDFW": "Dallas/Fort Worth",
        "KIAH": "Houston",
        "KORD": "Chicago O'Hare",
        "KJFK": "New York JFK",
        "KLAX": "Los Angeles",
        "KDEN": "Denver",
        "KMIA": "Miami",
        "KSEA": "Seattle",
        "KBOS": "Boston",
        "KATL": "Atlanta",
    }
