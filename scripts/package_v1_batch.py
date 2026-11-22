#!/usr/bin/env python3
"""
Package a completed v1.0 batch.

  python3 scripts/package_v1_batch.py                 # measure + gallery + zip
  python3 scripts/package_v1_batch.py --zip-only      # just rebuild the archive

Steps:
  1. measure every built v1 screen (2x diff) -> analysis/v1-diff.json
  2. regenerate the v1.0 gallery page (v1.html)
  3. rebuild the delivery zip and check every asset reference resolves

The zip is written to aimeee-2026-oct-html.zip; a dated copy is kept next to
it so each completed batch has its own archive.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=ROOT, text=True)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip-only", action="store_true")
    ap.add_argument("--no-copy", action="store_true")
    args = ap.parse_args()

    if not args.zip_only:
        # a page that links a font subset it does not ship falls back to a
        # system face, so generate any that are missing before measuring
        run([sys.executable, str(ROOT / "scripts/ensure_v1_fonts.py")])
        run([sys.executable, str(ROOT / "scripts/measure_v1.py")])
        run([sys.executable, str(ROOT / "scripts/gallery_v1.py")])

    rc = run([sys.executable, str(ROOT / "scripts/package.py")])
    if rc:
        return rc
    rc = run([sys.executable, str(ROOT / "scripts/check_package.py")])
    if rc:
        return rc

    if not args.no_copy:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        copy = ROOT / f"aimeee-2026-oct-html-{stamp}.zip"
        shutil.copy2(ROOT / "aimeee-2026-oct-html.zip", copy)
        print(f"[copy] {copy.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
