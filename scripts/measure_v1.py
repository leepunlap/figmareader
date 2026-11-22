#!/usr/bin/env python3
"""
Measure the built v1.0 screens and record the result.

  python3 scripts/measure_v1.py                 # every built v1 screen
  python3 scripts/measure_v1.py v1-home v1-play # only some

Runs the shared render/diff pipeline (scripts/render_check.py, 2x) and writes
analysis/v1-diff.json, which the gallery and the README read.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis/v1-diff.json"

ROW = re.compile(r"^(\S+)\s+\(\d+,\s*\d+\)\s+\(\d+,\s*\d+\)\s+([\d.]+)%")


def built_names() -> list[str]:
    """Screen names of every built page: v1-<slug> for the big page and
    v73-<slug> for the 7.3 page.  The name is also the page stem."""
    return sorted([p.stem for p in ROOT.glob("v1-*.html")] +
                  [p.stem for p in ROOT.glob("v73-*.html")])


def main() -> int:
    targets = sys.argv[1:]
    names = list(targets) if targets else built_names()
    if not names:
        print("no built v1 screens")
        return 0

    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_check.py"), *names],
        cwd=ROOT, capture_output=True, text=True,
    )
    print(res.stdout[-4000:])
    if res.returncode != 0:
        print(res.stderr[-2000:])

    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for line in res.stdout.splitlines():
        m = ROW.match(line.strip())
        if m:
            data[m.group(1)] = float(m.group(2))
    # drop entries whose screen no longer exists (e.g. the pre-rename keys)
    known = set(built_names())
    stale = [k for k in data if k not in known]
    for k in stale:
        del data[k]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    if stale:
        print(f"[clean] dropped {len(stale)} stale entry/entries")

    vals = [v for k, v in data.items() if k in names]
    if vals:
        print(f"\n{len(vals)} measured  min {min(vals):.2f} %  max {max(vals):.2f} %  "
              f"mean {sum(vals)/len(vals):.2f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
