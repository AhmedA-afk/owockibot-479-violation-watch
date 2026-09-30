# Violation Watch: Upstream Permit Feed + Map

Surfaces Clean Water Act permit violations upstream of a point as an
Atom 1.0 feed + live Leaflet map. Built for
[owockibot.xyz bounty #479](https://owockibot.xyz) ($10 USDC).

## What it does

Given `--lat --lon`, the tool:

1. Queries the **live EPA ECHO CWA web services** for facilities near the point.
2. Filters to facilities with violation / SNC (significant non-compliance) flags.
3. Sorts them **upstream-first** using a documented elevation proxy.
4. Writes `feed.xml` (valid Atom 1.0, RFC 4287, one entry per facility with
   GeoRSS point) and `map.html` (self-contained Leaflet map, one numbered
   marker per facility, popups with name / NPDES id / status / distance).
5. Prints a human-readable summary table.

## Data sources (exact endpoints)

All public, no API keys.

| Source | Endpoint | Used for |
|---|---|---|
| EPA ECHO CWA facility search | `https://echodata.epa.gov/echo/cwa_rest_services.get_facilities?output=JSON&p_lat=&p_long=&p_radius=` then `cwa_rest_services.get_qid?output=JSON&qid=&qcolumns=&responseset=` | Facility list + violation/SNC flags. Pinned `qcolumns=1,2,3,4,5,7,9,11,25,26,52,99,101,103,104,205,231` (verified against `cwa_rest_services.metadata`, 2026-09-30): CWPName, SourceID (NPDES id), address, RegistryID, Statute, FacLat/FacLong, CWPPermitStatusDesc, CWPSNCStatus, CWPSNCStatusDate, CWPViolStatus, CWPQtrsWithSNC, ViolFlag, VioLastYear |
| EPA ECHO detailed facility report | `https://echo.epa.gov/detailed-facility-report?fid={RegistryID}` | Per-entry link target |
| USGS Elevation Point Query Service | `https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Meters` | Elevation for the upstream proxy |
| OpenStreetMap tiles + Leaflet 1.9.4 (CDN) | `https://unpkg.com/leaflet@1.9.4/...` | Map rendering |

Docs: https://echo.epa.gov/tools/web-services

A facility counts as a violator when any of these hold: non-empty
`CWPSNCStatus` (SNC), `CWPViolStatus = Yes`, or `ViolFlag = 1`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # requests only
```

## Usage

Live query (New Orleans industrial corridor example — 233 violating
facilities, 68 in SNC, as of 2026-09-30):

```bash
python -m violation_watch.cli --lat 29.95 --lon -90.07 --radius 20 --out output
```

Output:

```
Upstream permit violations within 20 mi of 29.9500, -90.0700
  #  NPDES       Name                       Status   Dist     Elev
  1  LAG530752   1112 ENGINEERS ROAD, LLC    SNC      6.9 mi    ...
...
Wrote output/feed.xml (Atom 1.0, validated) and output/map.html (Leaflet map).
```

Open `output/map.html` in a browser for the live map; subscribe to
`output/feed.xml` with any feed reader. Appending `#NPDES_ID` to the map URL
opens that facility's popup (feed entries link this way when no ECHO detail
URL is available).

### Sample / offline mode

```bash
python -m violation_watch.cli --sample --out output
```

Regenerates `feed.xml` + `map.html` from the committed real-data sample
(`examples/sample_facilities.json`, 20 most-upstream violators near
29.95, -90.07 from a live ECHO run). The map UI is fully demonstrable
offline from the embedded data (only the Leaflet CDN + map tiles need
network).

If ECHO is unreachable, the tool exits with code 2 and a clear error
pointing at `--sample` — never silent empty output.

## The upstream heuristic — read this

Facilities are ordered by ground elevation from USGS EPQS, highest first.
**This is a proxy, not hydrologic tracing.** Real upstream/downstream
relationships need NHDPlus flowline tracing (flow direction, stream network
topology, pour points). In flat terrain (e.g. the Louisiana delta, where
most sample elevations sit within a few meters) the ranking is weak; in
hilly terrain it is a better approximation. The README, feed subtitle, and
map banner all state this. Do not use the ranking for regulatory or legal
decisions.

## Regenerating the committed samples

```bash
python -m violation_watch.cli --sample --out /tmp/regen
cp /tmp/regen/feed.xml examples/feed-sample.xml
cp /tmp/regen/map.html examples/map-sample.html
```

To rebuild the underlying sample from a fresh live ECHO run, re-run the
query above and keep the 20 most-upstream violators in
`examples/sample_facilities.json` (see `meta.provenance` in that file).

## Tests

```bash
python tests/run_all.py
```

- `test_feed.py` — parses `examples/feed-sample.xml`: valid Atom 1.0, all
  required feed/entry elements, GeoRSS points, upstream ordering.
- `test_map.py` — `examples/map-sample.html` embeds Leaflet, one marker per
  sample facility, popup fields, `#NPDES_ID` deep links.
- `test_upstream.py` — elevation-proxy sort unit tests (no network).
- `test_cli_sample.py` — end-to-end `--sample` run, outputs validate.

## Submission / deploy notes (for the claimer)

1. Create a public GitHub repo (e.g. `violation-watch`), push this directory.
2. Claim bounty #479 on [owockibot.xyz](https://owockibot.xyz) with the GitHub
   repo URL and a link to the working feed + map. Note the proposer-priority
   window: only wallet `0xbc97e8588c29d2f3495a8f1384e6aa9de61becc4` may claim
   until 2026-09-30T13:30:00Z; claims open to everyone after that.
3. Nothing here publishes, claims, or creates wallets — the human claimer
   does that.

## License

MIT
