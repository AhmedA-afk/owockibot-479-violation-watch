"""Run the whole suite: python tests/run_all.py"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

files = ["test_upstream.py", "test_feed.py", "test_map.py", "test_cli_sample.py"]
failed = []
for f in files:
    print(f"\n=== {f} ===")
    r = subprocess.run([sys.executable, str(ROOT / f)], capture_output=True, text=True)
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    if r.returncode != 0:
        failed.append(f)
print("\n" + ("ALL SUITES PASSED" if not failed else f"FAILED: {failed}"))
sys.exit(1 if failed else 0)
