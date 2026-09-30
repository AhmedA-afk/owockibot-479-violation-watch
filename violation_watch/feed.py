"""Atom 1.0 (RFC 4287) feed generator for upstream permit violations."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

ATOM_NS = "http://www.w3.org/2005/Atom"
GEORSS_NS = "http://www.georss.org/georss"

# Register prefixes so serialized XML uses xmlns:georss (not ns0).
register_namespace("georss", GEORSS_NS)
register_namespace("", ATOM_NS)


def _rfc3339_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tag_uri(authority: str, date: str, specific: str) -> str:
    return f"tag:{authority},{date}:{specific}"


def build_feed(
    facilities: list,
    lat: float,
    lon: float,
    radius_miles: float,
    source_note: str = "EPA ECHO CWA web services",
    feed_url: str = "",
) -> str:
    """Build a valid Atom 1.0 feed XML string, one entry per facility.

    Facilities are expected upstream-sorted already; entries carry their
    upstream rank in the title and summary.
    """
    now = _rfc3339_now()
    feed = Element("feed", {"xmlns": ATOM_NS})

    title = SubElement(feed, "title")
    title.text = (
        f"Upstream permit violations near {lat:.4f}, {lon:.4f} "
        f"({radius_miles:g} mi radius)"
    )
    SubElement(feed, "id").text = _tag_uri(
        "owockibot-violation-watch", now[:10], f"upstream/{lat:.4f}/{lon:.4f}"
    )
    SubElement(feed, "updated").text = now
    if feed_url:
        SubElement(feed, "link", {"rel": "self", "href": feed_url})
    SubElement(feed, "link", {"rel": "alternate", "href": "map.html"})
    author = SubElement(feed, "author")
    SubElement(author, "name").text = "Violation Watch (owockibot #479)"
    subtitle = SubElement(feed, "subtitle")
    subtitle.text = (
        f"Clean Water Act facilities with permit violations upstream of "
        f"{lat:.4f}, {lon:.4f}. Source: {source_note}. Upstream order is an "
        "elevation proxy (USGS EPQS), not NHDPlus flowline tracing."
    )

    for fac in facilities:
        entry = SubElement(feed, "entry")
        rank = f"#{fac.upstream_rank} upstream" if fac.upstream_rank else "unranked"
        SubElement(entry, "title").text = (
            f"[{rank}] {fac.name} ({fac.npdes_id or 'no NPDES id'})"
        )
        SubElement(entry, "id").text = _tag_uri(
            "owockibot-violation-watch", now[:10], f"facility/{fac.npdes_id or fac.name}"
        )
        SubElement(entry, "updated").text = now
        link_href = fac.detail_url or f"map.html#{fac.npdes_id}"
        SubElement(entry, "link", {"rel": "alternate", "href": link_href})

        lines = [
            f"Facility: {fac.name}",
            f"NPDES permit: {fac.npdes_id or 'unknown'}",
            f"Status: {fac.status_label}",
            f"Location: {fac.address}, {fac.city}, {fac.state} {fac.zip_code}".strip(" ,"),
            f"Distance from query point: {fac.dist_mi} mi"
            if fac.dist_mi is not None
            else "Distance from query point: unknown",
            f"Elevation: {fac.elevation_m:.1f} m (USGS EPQS)"
            if fac.elevation_m is not None
            else "Elevation: unavailable",
            f"Violation summary: {fac.violation_summary}",
        ]
        for v in fac.violations[:10]:
            bit = f"{v.date} — {v.description}".strip(" —")
            if v.code:
                bit += f" [{v.code}]"
            lines.append(f"  * {bit}")
        summary = SubElement(entry, "summary")
        summary.text = "\n".join(lines)

        if fac.lat is not None and fac.lon is not None:
            point = SubElement(entry, f"{{{GEORSS_NS}}}point")
            point.text = f"{fac.lat} {fac.lon}"

    xml = tostring(feed, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n"


def validate_atom(xml_text: str) -> list[str]:
    """Check RFC 4287 required elements. Returns a list of problems (empty = OK)."""
    from xml.etree.ElementTree import fromstring

    problems: list[str] = []
    try:
        root = fromstring(xml_text)
    except Exception as exc:  # noqa: BLE001
        return [f"not well-formed XML: {exc}"]
    ns = {"a": ATOM_NS, "g": GEORSS_NS}
    if root.tag != f"{{{ATOM_NS}}}feed":
        problems.append(f"root element is {root.tag}, expected Atom feed")
        return problems
    for tag in ("title", "id", "updated"):
        if root.find(f"a:{tag}", ns) is None:
            problems.append(f"feed missing required <{tag}>")
    entries = root.findall("a:entry", ns)
    if not entries:
        problems.append("feed has no entries")
    for i, e in enumerate(entries):
        for tag in ("title", "id", "updated", "link", "summary"):
            if e.find(f"a:{tag}", ns) is None:
                problems.append(f"entry {i} missing required <{tag}>")
        if e.find("g:point", ns) is None:
            problems.append(f"entry {i} missing georss:point")
    # sanity: html-escape check on a raw title containing markup chars is the
    # generator's job; here we just confirm no raw '<' leaks in text
    if "<script" in xml_text.lower():
        problems.append("suspicious raw markup in feed text")
    _ = html  # keep import used for future escaping audits
    return problems
