"""Unit tests for the upstream (elevation-proxy) sort. Uses a stub elevation
function so no network is needed. Runnable directly or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from violation_watch.echo_client import Facility  # noqa: E402
from violation_watch.upstream import sort_upstream_first  # noqa: E402


def _fac(name: str, lat: float, lon: float) -> Facility:
    return Facility(name=name, lat=lat, lon=lon)


def test_higher_elevation_sorts_first():
    elev = {("A",): 50.0, ("B",): 10.0, ("C",): 30.0}
    facs = [_fac("A", 29.9, -90.0), _fac("B", 29.9, -90.1), _fac("C", 29.9, -90.2)]

    def stub(lat, lon):
        return {"A": 50.0, "B": 10.0, "C": 30.0}[
            next(f.name for f in facs if f.lat == lat and f.lon == lon)
        ]

    ordered = sort_upstream_first(facs, elevation_fn=stub, throttle=0)
    assert [f.name for f in ordered] == ["A", "C", "B"]
    assert [f.upstream_rank for f in ordered] == [1, 2, 3]
    assert ordered[0].elevation_m == 50.0


def test_failed_elevation_goes_last_and_keeps_order():
    facs = [_fac("A", 29.9, -90.0), _fac("B", 29.9, -90.1), _fac("C", 29.9, -90.2)]

    def stub(lat, lon):
        return 20.0 if lon == -90.0 else None

    ordered = sort_upstream_first(facs, elevation_fn=stub, throttle=0)
    assert ordered[0].name == "A"
    assert [f.name for f in ordered[1:]] == ["B", "C"]
    assert [f.upstream_rank for f in ordered] == [1, 2, 3]


def test_prefers_existing_elevation_without_lookup():
    facs = [_fac("A", 29.9, -90.0), _fac("B", 29.9, -90.1)]
    facs[0].elevation_m = 5.0
    facs[1].elevation_m = 40.0
    calls = []

    def stub(lat, lon):
        calls.append((lat, lon))
        return 999.0

    ordered = sort_upstream_first(facs, elevation_fn=stub, throttle=0)
    assert calls == [], "should not call elevation_fn when elevation already set"
    assert [f.name for f in ordered] == ["B", "A"]


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
    print(f"{len(tests) - failed}/{len(tests)} upstream tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
