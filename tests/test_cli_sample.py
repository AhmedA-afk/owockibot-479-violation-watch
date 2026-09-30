"""End-to-end test of --sample mode: runs the CLI against the bundled sample,
then validates the generated feed.xml (Atom) and map.html. No network needed.
Runnable directly or under pytest.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from violation_watch.feed import ATOM_NS, GEORSS_NS, validate_atom  # noqa: E402


def run_cli_sample() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="vw-test-"))
    proc = subprocess.run(
        [sys.executable, "-m", "violation_watch.cli", "--sample", "--out", str(tmp)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}\n{proc.stdout}"
    return tmp


def test_sample_mode_generates_valid_outputs():
    tmp = run_cli_sample()
    feed_p, map_p = tmp / "feed.xml", tmp / "map.html"
    assert feed_p.exists(), "feed.xml not written"
    assert map_p.exists(), "map.html not written"

    xml = feed_p.read_text(encoding="utf-8")
    assert not validate_atom(xml), "generated feed.xml invalid"
    root = ET.fromstring(xml)
    ns = {"a": ATOM_NS, "g": GEORSS_NS}
    entries = root.findall("a:entry", ns)
    assert entries, "no entries in generated feed"
    assert all(e.find("g:point", ns) is not None for e in entries)

    html = map_p.read_text(encoding="utf-8")
    assert "L.marker(" in html and "leaflet.js" in html


def test_sample_mode_prints_table():
    proc = subprocess.run(
        [sys.executable, "-m", "violation_watch.cli", "--sample", "--out", "/tmp/vw-table-check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    assert "Upstream permit violations" in proc.stdout
    assert "NPDES" in proc.stdout


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
    print(f"{len(tests) - failed}/{len(tests)} cli-sample tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
