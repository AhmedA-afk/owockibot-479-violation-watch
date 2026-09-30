"""Tests for the Atom feed: parses examples/feed-sample.xml and validates
RFC 4287 required elements, entry structure, GeoRSS points, and upstream
ordering. Runnable directly (python tests/test_feed.py) or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from violation_watch.feed import ATOM_NS, GEORSS_NS, validate_atom  # noqa: E402

SAMPLE_FEED = ROOT / "examples" / "feed-sample.xml"
SAMPLE_JSON = ROOT / "examples" / "sample_facilities.json"


def load_feed():
    xml = SAMPLE_FEED.read_text(encoding="utf-8")
    problems = validate_atom(xml)
    assert not problems, f"feed validation problems: {problems}"
    return ET.fromstring(xml), xml


def test_feed_is_valid_atom():
    root, _ = load_feed()
    assert root.tag == f"{{{ATOM_NS}}}feed"


def test_feed_has_required_elements():
    root, _ = load_feed()
    ns = {"a": ATOM_NS}
    for tag in ("title", "id", "updated", "link", "subtitle", "author"):
        assert root.find(f"a:{tag}", ns) is not None, f"missing feed <{tag}>"


def test_entries_have_required_elements_and_georss():
    import json

    root, _ = load_feed()
    ns = {"a": ATOM_NS, "g": GEORSS_NS}
    entries = root.findall("a:entry", ns)
    expected = len(json.loads(SAMPLE_JSON.read_text())["facilities"])
    assert len(entries) == expected, f"{len(entries)} entries, expected {expected}"
    for e in entries:
        for tag in ("title", "id", "updated", "link", "summary"):
            assert e.find(f"a:{tag}", ns) is not None, f"entry missing <{tag}>"
        point = e.find("g:point", ns)
        assert point is not None and point.text, "entry missing georss:point"
        lat_s, lon_s = point.text.split()
        lat, lon = float(lat_s), float(lon_s)
        assert -90 <= lat <= 90 and -180 <= lon <= 180, f"bad coords {point.text}"


def test_entries_ordered_upstream_first():
    root, _ = load_feed()
    ns = {"a": ATOM_NS}
    titles = [e.find("a:title", ns).text for e in root.findall("a:entry", ns)]
    ranks = []
    for t in titles:
        assert t.startswith("[#"), f"title missing upstream rank: {t}"
        ranks.append(int(t[2:].split("]")[0].split()[0]))
    assert ranks == sorted(ranks), f"entries not upstream-sorted: {ranks}"
    assert ranks[0] == 1, "first entry should be upstream rank 1"


def test_summaries_contain_violation_details():
    root, _ = load_feed()
    ns = {"a": ATOM_NS}
    for e in root.findall("a:entry", ns):
        summary = e.find("a:summary", ns).text
        assert "NPDES permit" in summary, "summary missing permit id"
        assert "Violation summary" in summary, "summary missing violation details"


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
    print(f"{len(tests) - failed}/{len(tests)} feed tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
