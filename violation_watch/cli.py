"""CLI: violation-watch.

Live mode queries EPA ECHO CWA web services for violating facilities near a
point, sorts them upstream-first, and writes feed.xml + map.html.

Sample mode (--sample) regenerates both outputs from the bundled real-data
sample (examples/sample_facilities.json) — usable offline.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .echo_client import EchoClient, EchoUnavailableError
from .feed import build_feed, validate_atom
from .mapview import build_map_html
from .samples import SAMPLE_PATH, load_sample_facilities
from .upstream import sort_upstream_first

DEFAULT_RADIUS_MILES = 10


def print_table(facilities: list, lat: float, lon: float, radius: float) -> None:
    print(f"\nUpstream permit violations within {radius:g} mi of {lat:.4f}, {lon:.4f}")
    print(f"{'#':>3}  {'NPDES':<10}  {'Name':<42}  {'Status':<34}  {'Dist':>7}  {'Elev':>7}")
    print("-" * 115)
    for fac in facilities:
        status = "SNC" if fac.snc else "VIOL"
        dist = f"{fac.dist_mi:.1f} mi" if fac.dist_mi is not None else "?"
        elev = f"{fac.elevation_m:.0f} m" if fac.elevation_m is not None else "?"
        rank = fac.upstream_rank or 0
        print(f"{rank:>3}  {fac.npdes_id:<10}  {fac.name[:42]:<42}  {status:<34}  {dist:>7}  {elev:>7}")
    known = sum(1 for f in facilities if f.elevation_m is not None)
    if known == 0 and facilities:
        print("\nNOTE: elevation lookups failed (USGS EPQS unreachable); "
              "order below falls back to distance from the query point.")
    else:
        print(f"\n{len(facilities)} facilities. Higher elevation = treated as more upstream (proxy).")


def write_outputs(
    facilities: list,
    lat: float,
    lon: float,
    radius: float,
    out_dir: Path,
    source_note: str,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    feed_xml = build_feed(facilities, lat, lon, radius, source_note=source_note)
    problems = validate_atom(feed_xml)
    if problems:
        raise RuntimeError("generated feed failed Atom validation: " + "; ".join(problems))
    map_html = build_map_html(facilities, lat, lon, radius, source_note=source_note)
    feed_path = out_dir / "feed.xml"
    map_path = out_dir / "map.html"
    feed_path.write_text(feed_xml, encoding="utf-8")
    map_path.write_text(map_html, encoding="utf-8")
    return feed_path, map_path


def run_live(args: argparse.Namespace) -> int:
    client = EchoClient()
    try:
        facilities = client.search_cwa_facilities(args.lat, args.lon, args.radius)
    except EchoUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Hint: ECHO is unreachable right now. You can still demo the tool with "
            "the bundled real-data sample: violation-watch --sample",
            file=sys.stderr,
        )
        return 2
    if not facilities:
        print(
            f"No CWA facilities with violation flags found within {args.radius:g} mi "
            f"of {args.lat:.4f}, {args.lon:.4f} (live ECHO data)."
        )
        return 0
    facilities = sort_upstream_first(facilities)
    out = Path(args.out)
    feed_path, map_path = write_outputs(
        facilities, args.lat, args.lon, args.radius, out, "EPA ECHO CWA web services (live)"
    )
    print_table(facilities, args.lat, args.lon, args.radius)
    print(f"\nWrote {feed_path} (Atom 1.0, validated) and {map_path} (Leaflet map).")
    return 0


def run_sample(args: argparse.Namespace) -> int:
    try:
        facilities, meta = load_sample_facilities()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    sp = meta.get("source_point", {})
    lat = sp.get("lat", 29.95)
    lon = sp.get("lon", -90.07)
    radius = sp.get("radius_miles", DEFAULT_RADIUS_MILES)
    generated = meta.get("generated", "unknown date")
    facilities = sorted(facilities, key=lambda f: f.upstream_rank or 999)
    out = Path(args.out)
    feed_path, map_path = write_outputs(
        facilities,
        lat,
        lon,
        radius,
        out,
        f"bundled sample (EPA ECHO ICIS-NPDES snapshot, {generated})",
    )
    print(f"Sample mode: regenerating from {SAMPLE_PATH.name} (real EPA data, {generated}).")
    print_table(facilities, lat, lon, radius)
    print(f"\nWrote {feed_path} (Atom 1.0, validated) and {map_path} (Leaflet map).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="violation-watch",
        description=(
            "Surface Clean Water Act permit violations upstream of a point as an "
            "Atom feed + live Leaflet map, from EPA ECHO web services."
        ),
    )
    p.add_argument("--lat", type=float, help="query latitude (required unless --sample)")
    p.add_argument("--lon", type=float, help="query longitude (required unless --sample)")
    p.add_argument("--radius", type=float, default=DEFAULT_RADIUS_MILES,
                   help=f"search radius in miles (default {DEFAULT_RADIUS_MILES})")
    p.add_argument("--out", default="output",
                   help="output directory for feed.xml and map.html (default: ./output)")
    p.add_argument("--sample", action="store_true",
                   help="regenerate feed.xml + map.html from the bundled real-data sample")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sample:
        return run_sample(args)
    if args.lat is None or args.lon is None:
        print("ERROR: --lat and --lon are required (or use --sample).", file=sys.stderr)
        return 2
    return run_live(args)


if __name__ == "__main__":
    sys.exit(main())
