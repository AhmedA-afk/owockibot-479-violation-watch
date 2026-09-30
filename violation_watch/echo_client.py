"""Client for the EPA ECHO Clean Water Act REST web services.

Primary source: EPA Enforcement and Compliance History Online (ECHO).
Docs: https://echo.epa.gov/tools/web-services
CWA facility search service: cwa_rest_services.get_facilities
Column metadata: cwa_rest_services.metadata

No API key is required; all endpoints are public GET services.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

import requests

ECHO_BASE = "https://echodata.epa.gov/echo"
CWA_FACILITIES_SERVICE = "cwa_rest_services.get_facilities"
CWA_QID_SERVICE = "cwa_rest_services.get_qid"
# Detailed Facility Report (per-facility page on echo.epa.gov); fid is the FRS
# Registry ID returned by the facility search as RegistryID.
DFR_URL = "https://echo.epa.gov/detailed-facility-report?fid={registry_id}"

# Column IDs from cwa_rest_services.metadata (verified live 2026-09-30):
# 1=CWPName 2=SourceID(NPDES) 3=CWPStreet 4=CWPCity 5=CWPState 7=CWPZip
# 9=RegistryID 11=Statute 25=FacLat 26=FacLong 52=CWPPermitStatusDesc
# 99=CWPSNCStatus 101=CWPSNCStatusDate 103=CWPViolStatus 104=CWPQtrsWithSNC
# 205=ViolFlag 231=VioLastYear
QCOLUMNS = "1,2,3,4,5,7,9,11,25,26,52,99,101,103,104,205,231"


class EchoUnavailableError(RuntimeError):
    """Raised when the ECHO web services cannot be reached or return an error."""


@dataclass
class Violation:
    date: str = ""
    description: str = ""
    code: str = ""


@dataclass
class Facility:
    npdes_id: str = ""
    registry_id: str = ""
    name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    lat: float | None = None
    lon: float | None = None
    dist_mi: float | None = None
    elevation_m: float | None = None
    upstream_rank: int | None = None
    snc: bool = False
    violation_summary: str = ""
    violations: list[Violation] = field(default_factory=list)
    detail_url: str = ""
    permit_status: str = ""
    snc_detail: str = ""
    snc_date: str = ""
    quarters_snc: str = ""

    @property
    def status_label(self) -> str:
        return "SNC (significant non-compliance)" if self.snc else "Violation reported"


def _facility_from_record(rec: dict[str, Any], origin_lat: float, origin_lon: float) -> Facility | None:
    """Build a Facility from one cwa_rest_services facility record.

    Returns None if the record lacks usable coordinates.
    """
    def g(*names: str) -> str:
        for n in names:
            v = rec.get(n)
            if v not in (None, ""):
                return str(v).strip()
        return ""

    lat_s, lon_s = g("FacLat"), g("FacLong")
    try:
        lat, lon = float(lat_s), float(lon_s)
    except (TypeError, ValueError):
        return None

    snc_status = g("CWPSNCStatus")
    viol_status = g("CWPViolStatus")
    viol_flag = g("ViolFlag")
    snc = bool(snc_status)
    is_violator = (
        snc
        or viol_status.lower() == "yes"
        or viol_flag == "1"
    )

    parts = []
    if snc:
        parts.append(f"SNC: {snc_status}")
        if g("CWPSNCStatusDate"):
            parts.append(f"since {g('CWPSNCStatusDate')}")
        if g("CWPQtrsWithSNC"):
            parts.append(f"{g('CWPQtrsWithSNC')} quarter(s) in SNC")
    elif viol_status.lower() == "yes":
        parts.append("Violation reported in ECHO")
    if viol_flag == "1":
        parts.append("ECHO violation flag set")
    if g("VioLastYear") not in ("", "0"):
        parts.append("violation within the last year")
    if g("CWPPermitStatusDesc"):
        parts.append(f"permit status: {g('CWPPermitStatusDesc')}")
    summary = "; ".join(parts) if parts else "Violation flag present"

    registry_id = g("RegistryID")
    return Facility(
        npdes_id=g("SourceID"),
        registry_id=registry_id,
        name=g("CWPName") or "Unnamed facility",
        address=g("CWPStreet"),
        city=g("CWPCity"),
        state=g("CWPState"),
        zip_code=g("CWPZip"),
        lat=lat,
        lon=lon,
        dist_mi=round(haversine_miles(origin_lat, origin_lon, lat, lon), 2),
        snc=snc,
        violation_summary=summary,
        detail_url=DFR_URL.format(registry_id=registry_id) if registry_id else "",
        permit_status=g("CWPPermitStatusDesc"),
        snc_detail=snc_status,
        snc_date=g("CWPSNCStatusDate"),
        quarters_snc=g("CWPQtrsWithSNC"),
    )


def is_violator_record(rec: dict[str, Any]) -> bool:
    """True if the raw record carries any violation/SNC flag."""
    snc = str(rec.get("CWPSNCStatus") or "").strip()
    return bool(
        snc
        or str(rec.get("CWPViolStatus") or "").strip().lower() == "yes"
        or str(rec.get("ViolFlag") or "").strip() == "1"
    )


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class EchoClient:
    """Thin wrapper around the ECHO CWA REST facility search."""

    def __init__(self, timeout: int = 60, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "violation-watch/1.0 (owockibot #479)"})

    def _get(self, service: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{ECHO_BASE}/{service}"
        try:
            resp = self.session.get(url, params={"output": "JSON", **params}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EchoUnavailableError(
                f"ECHO web service unreachable ({service}): {exc}. "
                "The EPA ECHO services may be down; try --sample to use bundled data."
            ) from exc
        if resp.status_code == 503:
            raise EchoUnavailableError(
                f"ECHO web service returned HTTP 503 ({service}): the EPA ECHO "
                "backend is temporarily unavailable. Try --sample to use bundled data."
            )
        if resp.status_code != 200:
            raise EchoUnavailableError(
                f"ECHO web service returned HTTP {resp.status_code} ({service})."
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise EchoUnavailableError(
                f"ECHO web service returned non-JSON for {service}."
            ) from exc

    def search_cwa_facilities(
        self, lat: float, lon: float, radius_miles: float = 10, limit: int = 2000
    ) -> list[Facility]:
        """Return CWA facilities with violation/SNC flags near (lat, lon).

        Uses the two-step get_facilities -> get_qid flow with pinned qcolumns.
        Raises EchoUnavailableError if ECHO cannot be reached.
        """
        payload = self._get(
            CWA_FACILITIES_SERVICE,
            {"p_lat": lat, "p_long": lon, "p_radius": radius_miles, "qcolumns": QCOLUMNS},
        )
        results = payload.get("Results", {})
        qid = results.get("QueryID") or results.get("QID")
        if not qid:
            # No QID: fall back to any inline facility rows.
            rows = results.get("Facilities") or []
            return [
                f for f in
                (_facility_from_record(r, lat, lon) for r in rows if isinstance(r, dict))
                if f is not None and _is_violator_facility(f)
            ][:limit]

        collected: list[dict[str, Any]] = []
        page = 1
        while len(collected) < limit:
            if page > 1:
                time.sleep(0.5)  # be polite to the public service
            nxt = self._get(
                CWA_QID_SERVICE,
                {"qid": qid, "qcolumns": QCOLUMNS, "responseset": page},
            )
            nres = nxt.get("Results", {})
            nrows = nres.get("Facilities") or []
            if not nrows:
                break
            collected.extend(nrows)
            # responseset=1 typically returns the full set; stop when a page
            # repeats or adds nothing new.
            if len(collected) >= limit or page >= 20:
                break
            # Heuristic: if this page returned fewer than a full page, we're done.
            # ECHO doesn't publish the page size, so also break when the total
            # reported rows are already collected.
            try:
                total = int(nres.get("QueryRows") or 0)
            except (TypeError, ValueError):
                total = 0
            if total and len(collected) >= total:
                break
            page += 1
            if page > 1 and len(nrows) < 1000:
                break

        facilities = []
        for rec in collected[:limit]:
            if not isinstance(rec, dict) or not is_violator_record(rec):
                continue
            fac = _facility_from_record(rec, lat, lon)
            if fac is not None:
                facilities.append(fac)
        return facilities


def _is_violator_facility(fac: Facility) -> bool:
    return fac.snc or "violation" in fac.violation_summary.lower() or "SNC" in fac.violation_summary
