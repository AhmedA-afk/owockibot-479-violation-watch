"""Violation Watch: upstream permit-violation feed + map.

Queries EPA ECHO Clean Water Act web services for facilities with permit
violations near a point, sorts them upstream-first (elevation proxy), and
renders a valid Atom 1.0 feed plus a self-contained Leaflet map.
"""

__version__ = "1.0.0"

from .echo_client import EchoClient, EchoUnavailableError, Facility  # noqa: F401
from .upstream import sort_upstream_first  # noqa: F401
from .feed import build_feed  # noqa: F401
from .mapview import build_map_html  # noqa: F401
