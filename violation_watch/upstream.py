"""Upstream ordering heuristic.

True upstream/downstream relationships require NHDPlus flowline tracing.
As a documented proxy, we rank facilities by land-surface elevation from the
USGS Elevation Point Query Service (EPQS): higher elevation is treated as
"more upstream". This is a heuristic, NOT hydrologic tracing — see README
limitations.
"""

from __future__ import annotations

import time
from typing import Iterable

import requests

EPQS_URL = "https://epqs.nationalmap.gov/v1/json"


def get_elevation_m(
    lat: float, lon: float, timeout: int = 45, session: requests.Session | None = None
) -> float | None:
    """Return ground elevation in meters at (lat, lon), or None on failure.

    The EPQS service can be slow (20s+ per request under load); the generous
    default timeout keeps the upstream sort working. Callers parallelize.
    """
    s = session or requests.Session()
    try:
        resp = s.get(
            EPQS_URL,
            params={"x": lon, "y": lat, "units": "Meters"},
            timeout=timeout,
            headers={"User-Agent": "violation-watch/1.0 (owockibot #479)"},
        )
        if resp.status_code != 200:
            return None
        value = resp.json().get("value")
        return float(value) if value is not None else None
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return None


def sort_upstream_first(
    facilities: Iterable,
    elevation_fn=get_elevation_m,
    throttle: float = 0.2,
    parallel: int = 8,
) -> list:
    """Sort facilities upstream-first by elevation (descending).

    Sets ``elevation_m`` and ``upstream_rank`` (1 = most upstream) on each
    facility. Facilities whose elevation lookup fails keep their relative
    distance order at the end; if no elevations resolve at all, the input
    order (distance-sorted) is preserved and noted by the caller.

    Elevation lookups run in a small thread pool (``parallel`` workers) with
    a per-call ``throttle`` pause to stay polite to the public EPQS service.
    """
    from concurrent.futures import ThreadPoolExecutor

    facs = list(facilities)
    todo = [f for f in facs if f.lat is not None and f.lon is not None and f.elevation_m is None]

    def _lookup(fac):
        try:
            elev = elevation_fn(fac.lat, fac.lon)
        finally:
            time.sleep(throttle)
        return fac, elev

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
            for fac, elev in ex.map(_lookup, todo):
                fac.elevation_m = elev

    known = [f for f in facs if f.elevation_m is not None]
    unknown = [f for f in facs if f.elevation_m is None]
    known.sort(key=lambda f: f.elevation_m, reverse=True)  # type: ignore[operator]
    ordered = known + unknown
    for rank, fac in enumerate(ordered, start=1):
        fac.upstream_rank = rank
    return ordered
