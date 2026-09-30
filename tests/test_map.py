"""Tests for the map page: checks examples/map-sample.html embeds Leaflet,
one marker per sample facility, and popup fields. Runnable directly or
under pytest.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_MAP = ROOT / "examples" / "map-sample.html"
SAMPLE_JSON = ROOT / "examples" / "sample_facilities.json"


def load():
    html = SAMPLE_MAP.read_text(encoding="utf-8")
    facs = json.loads(SAMPLE_JSON.read_text())["facilities"]
    return html, facs


def test_leaflet_included():
    html, _ = load()
    assert "unpkg.com/leaflet@1.9.4/dist/leaflet.js" in html, "Leaflet JS CDN missing"
    assert "unpkg.com/leaflet@1.9.4/dist/leaflet.css" in html, "Leaflet CSS CDN missing"
    assert "L.map(" in html, "L.map init missing"


def test_marker_code_per_facility():
    html, facs = load()
    # one FACILITIES JSON entry per facility, and one L.marker call site fed by
    # the forEach loop over FACILITIES
    m = re.search(r"var FACILITIES = (\[.*?\]);", html, re.S)
    assert m, "embedded FACILITIES JSON missing"
    embedded = json.loads(m.group(1).replace("<\\/", "</"))
    assert len(embedded) == len(facs), (
        f"embedded {len(embedded)} facilities, sample has {len(facs)}"
    )
    assert "L.marker(" in html, "L.marker call missing"
    assert "forEach" in html, "marker loop missing"


def test_popup_fields():
    html, facs = load()
    for label in ("Permit (NPDES)", "Status", "Distance", "Upstream rank", "Elevation"):
        assert label in html, f"popup field {label!r} missing"
    # every facility name appears in the embedded data
    for f in facs:
        assert f["name"] in html, f"facility {f['name']} missing from map"


def test_deep_link_anchors():
    html, facs = load()
    assert "location.hash" in html, "hash deep-link handler missing"
    for f in facs:
        if f["npdes_id"]:
            assert f'id="{f["npdes_id"]}"' in html, f"anchor for {f['npdes_id']} missing"


def test_query_point_and_bounds():
    html, _ = load()
    assert "circleMarker" in html, "query point marker missing"
    assert "fitBounds" in html, "fitBounds missing"


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} map tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
