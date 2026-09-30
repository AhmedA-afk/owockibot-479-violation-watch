"""Bundled sample-data loader.

The committed sample (examples/sample_facilities.json) is real EPA data from
the ECHO ICIS-NPDES warehouse snapshot (see README for provenance), used by
--sample mode so the feed + map are demonstrable while ECHO is unreachable.
"""

from __future__ import annotations

import json
from pathlib import Path

from .echo_client import Facility, Violation

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sample_facilities.json"


def load_sample_facilities(path: Path | str | None = None) -> tuple[list[Facility], dict]:
    """Load bundled sample facilities; returns (facilities, meta)."""
    p = Path(path) if path else SAMPLE_PATH
    if not p.exists():
        raise FileNotFoundError(f"sample data not found: {p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    facilities = []
    for rec in doc.get("facilities", []):
        facilities.append(
            Facility(
                npdes_id=rec.get("npdes_id", ""),
                registry_id=rec.get("registry_id", ""),
                name=rec.get("name", "Unnamed facility"),
                address=rec.get("address", ""),
                city=rec.get("city", ""),
                state=rec.get("state", ""),
                zip_code=rec.get("zip", ""),
                lat=rec.get("lat"),
                lon=rec.get("lon"),
                dist_mi=rec.get("dist_mi"),
                elevation_m=rec.get("elevation_m"),
                upstream_rank=rec.get("upstream_rank"),
                snc=bool(rec.get("snc")),
                violation_summary=rec.get("violation_summary", ""),
                violations=[
                    Violation(
                        date=v.get("date", ""),
                        description=v.get("description", ""),
                        code=v.get("code", ""),
                    )
                    for v in rec.get("violations", [])
                ],
                detail_url=rec.get("detail_url", ""),
            )
        )
    return facilities, doc.get("meta", {})
