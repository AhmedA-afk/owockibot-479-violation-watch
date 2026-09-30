"""Self-contained Leaflet map page generator.

The page embeds the facility list as JSON, pulls Leaflet from a CDN, and
renders one marker per facility with a popup (name, NPDES id, violation
status, distance, upstream rank). A location hash like #LA0042081 opens that
facility's popup, so Atom feed entries can deep-link into the map.
"""

from __future__ import annotations

import json

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


def _esc(s: object) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_map_html(
    facilities: list,
    lat: float,
    lon: float,
    radius_miles: float,
    source_note: str = "EPA ECHO CWA web services",
) -> str:
    data = []
    for fac in facilities:
        if fac.lat is None or fac.lon is None:
            continue
        data.append(
            {
                "npdes_id": fac.npdes_id,
                "name": fac.name,
                "address": fac.address,
                "city": fac.city,
                "state": fac.state,
                "zip": fac.zip_code,
                "lat": fac.lat,
                "lon": fac.lon,
                "dist_mi": fac.dist_mi,
                "elevation_m": round(fac.elevation_m, 1)
                if fac.elevation_m is not None
                else None,
                "upstream_rank": fac.upstream_rank,
                "snc": fac.snc,
                "status": fac.status_label,
                "summary": fac.violation_summary,
                "detail_url": fac.detail_url,
            }
        )
    payload = json.dumps(data).replace("</", "<\\/")
    anchors = "\n".join(
        f'<div class="anchor" id="{_esc(f["npdes_id"])}"></div>' for f in data if f["npdes_id"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Upstream permit violations near {lat:.4f}, {lon:.4f}</title>
<link rel="stylesheet" href="{LEAFLET_CSS}">
<style>
  html, body {{ margin: 0; height: 100%; font-family: system-ui, sans-serif; }}
  #map {{ height: 100%; }}
  .banner {{
    position: absolute; top: 10px; left: 50px; z-index: 1000;
    background: rgba(255,255,255,.94); padding: 10px 14px; border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,.25); max-width: 430px; font-size: 13px;
  }}
  .banner h1 {{ font-size: 15px; margin: 0 0 4px; }}
  .banner p {{ margin: 2px 0; color: #444; }}
  .legend {{ line-height: 1.7; }}
  .dot {{ display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; }}
  .popup b {{ font-size: 14px; }}
  .popup table {{ border-collapse: collapse; margin-top: 6px; font-size: 12px; }}
  .popup td {{ padding: 2px 6px 2px 0; vertical-align: top; }}
  .popup td:first-child {{ color: #555; white-space: nowrap; }}
  .anchor {{ display: none; }}
</style>
</head>
<body>
{anchors}
<div id="map"></div>
<div class="banner">
  <h1>Upstream permit violations</h1>
  <p><b>{len(data)} facilities</b> with CWA violations within {radius_miles:g} mi of
     {lat:.4f}, {lon:.4f} &mdash; sorted most-upstream first.</p>
  <p class="legend"><span class="dot" style="background:#d62728"></span>SNC (significant non-compliance)
     <span class="dot" style="background:#ff7f0e; margin-left:10px"></span>Violation reported</p>
  <p>Source: {_esc(source_note)}. Upstream order is an elevation proxy
     (USGS EPQS), not NHDPlus flowline tracing. Markers are numbered by upstream rank;
     append <code>#NPDES_ID</code> to the URL to open a facility.</p>
</div>
<script src="{LEAFLET_JS}"></script>
<script>
var FACILITIES = {payload};
var map = L.map('map').setView([{lat}, {lon}], 11);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}}).addTo(map);
// query point
L.circleMarker([{lat}, {lon}], {{radius: 8, color: '#1f77b4', fillColor: '#1f77b4', fillOpacity: 0.9}})
  .addTo(map).bindPopup('<b>Query point</b><br>{lat:.4f}, {lon:.4f}');
var markersById = {{}};
var bounds = [[{lat}, {lon}]];
FACILITIES.forEach(function (f) {{
  var color = f.snc ? '#d62728' : '#ff7f0e';
  var num = f.upstream_rank ? String(f.upstream_rank) : '?';
  var icon = L.divIcon({{
    className: 'rank-marker',
    html: '<div style="background:' + color + ';color:#fff;border-radius:50%;'
        + 'width:24px;height:24px;line-height:24px;text-align:center;'
        + 'font-size:11px;font-weight:bold;border:2px solid #fff;'
        + 'box-shadow:0 1px 4px rgba(0,0,0,.4)">' + num + '</div>',
    iconSize: [24, 24], iconAnchor: [12, 12]
  }});
  var rows = [
    ['Permit (NPDES)', f.npdes_id || 'unknown'],
    ['Status', f.status],
    ['Distance', (f.dist_mi == null ? 'unknown' : f.dist_mi + ' mi')],
    ['Upstream rank', f.upstream_rank == null ? 'n/a' : '#' + f.upstream_rank + ' of ' + FACILITIES.length],
    ['Elevation', f.elevation_m == null ? 'unavailable' : f.elevation_m + ' m'],
    ['Address', [f.address, f.city, f.state, f.zip].filter(Boolean).join(', ') || 'n/a'],
  ];
  var htmlRows = rows.map(function (r) {{
    return '<tr><td>' + r[0] + '</td><td><b>' + r[1] + '</b></td></tr>';
  }}).join('');
  var detail = f.detail_url ? '<br><a href="' + f.detail_url + '" target="_blank" rel="noopener">EPA detailed facility report</a>' : '';
  var popup = '<div class="popup"><b>' + f.name + '</b><table>' + htmlRows + '</table>'
    + '<div style="margin-top:6px;font-size:12px;color:#333">' + f.summary + '</div>' + detail + '</div>';
  var m = L.marker([f.lat, f.lon], {{icon: icon}}).addTo(map).bindPopup(popup);
  if (f.npdes_id) markersById[f.npdes_id] = m;
  bounds.push([f.lat, f.lon]);
}});
map.fitBounds(bounds, {{padding: [40, 40]}});
// deep-link: #NPDES_ID opens that facility's popup
(function () {{
  var id = decodeURIComponent((location.hash || '').slice(1));
  if (id && markersById[id]) {{
    var m = markersById[id];
    map.setView(m.getLatLng(), 13);
    m.openPopup();
  }}
}})();
</script>
</body>
</html>
"""
