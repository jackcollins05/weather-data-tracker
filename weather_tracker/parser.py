"""Parse the imperial NWS observation-history HTML table without network access."""

from html.parser import HTMLParser
import re


class ObservationParseError(ValueError):
    """The page does not contain a usable NWS observation."""


class _TableReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.section = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and self.table is None:
            classes = dict(attrs).get("class", "").split()
            self.table = {"classes": classes, "thead": [], "tbody": []}
        elif self.table is not None:
            if tag in ("thead", "tbody"):
                self.section = tag
            elif tag == "tr" and self.section in ("thead", "tbody"):
                self.row = []
            elif tag in ("th", "td") and self.row is not None:
                attributes = dict(attrs)
                self.cell = {
                    "text": "",
                    "rowspan": int(attributes.get("rowspan", 1)),
                    "colspan": int(attributes.get("colspan", 1)),
                }

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if self.table is None:
            return
        if tag in ("th", "td") and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table[self.section].append(self.row)
            self.row = None
        elif tag in ("thead", "tbody"):
            self.section = None
        elif tag == "table":
            self.tables.append(self.table)
            self.table = None


def _header_paths(rows):
    """Expand HTML row and column spans into a label path for each column."""
    grid = {}
    for row_number, row in enumerate(rows):
        column = 0
        for cell in row:
            while (row_number, column) in grid:
                column += 1
            for r in range(row_number, row_number + cell["rowspan"]):
                for c in range(column, column + cell["colspan"]):
                    grid[r, c] = cell["text"].lower()
            column += cell["colspan"]

    width = max((column for _, column in grid), default=-1) + 1
    paths = []
    for column in range(width):
        labels = []
        for row_number in range(len(rows)):
            label = grid.get((row_number, column), "")
            if label and (not labels or label != labels[-1]):
                labels.append(label)
        paths.append(" ".join(labels))
    return paths


def _column(paths, *terms):
    matches = [
        i for i, path in enumerate(paths)
        if all(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", path) for term in terms)
    ]
    if len(matches) != 1:
        raise ObservationParseError(f"Missing or ambiguous observation header: {' / '.join(terms)}")
    return matches[0]


def _number(text, field):
    value = text.strip().replace(",", "")
    if value.upper() in ("", "M", "N/A", "NA", "--"):
        return None
    if field == "relative_humidity_pct":
        value = value.removesuffix("%")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value):
        raise ObservationParseError(f"Invalid {field} value: {text!r}")
    number = float(value)
    if field in ("temperature_f", "dew_point_f", "relative_humidity_pct") and number.is_integer():
        return int(number)
    return number


def parse_observation(html: str, station_id: str) -> dict:
    """Return the first usable observation from an imperial NWS history page."""
    reader = _TableReader()
    reader.feed(html)
    table = next((t for t in reader.tables if "obs-history" in t["classes"]), None)
    if table is None:
        raise ObservationParseError(f"Observation-history table not found for {station_id}")

    paths = _header_paths(table["thead"])
    columns = {
        "temperature_f": _column(paths, "temperature", "air"),
        "dew_point_f": _column(paths, "temperature", "dwpt"),
        "relative_humidity_pct": _column(paths, "relative humidity"),
        "visibility_miles": _column(paths, "vis."),
        "altimeter_inhg": _column(paths, "pressure", "altimeter"),
        "sea_level_pressure_mb": _column(paths, "pressure", "sea level"),
    }
    date_column = _column(paths, "date")
    time_column = _column(paths, "time")

    for row in table["tbody"]:
        values = [cell["text"] for cell in row]
        if len(values) <= max(date_column, time_column) or not values[date_column] or not values[time_column]:
            continue
        result = {"station_id": station_id}
        for field, column in columns.items():
            result[field] = _number(values[column] if column < len(values) else "", field)
        if any(result[field] is not None for field in columns):
            return result

    raise ObservationParseError(f"No usable observation row found for {station_id}")
