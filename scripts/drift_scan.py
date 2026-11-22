#!/usr/bin/env python3
"""
Scan a rendered screen for horizontal text drift.

Splits the page into text rows (runs of rows that contain dark pixels inside
the artboard), then compares the source and the render column by column inside
each row.  If every row drifts by the same amount the page needs one global
nudge; otherwise the per-row deltas point at the individual elements.

  python3 scripts/drift_scan.py lion-09
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import HEIGHTS, SCREENS, WIDTHS  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--thr", type=int, default=150)
    args = ap.parse_args()

    spec = SCREENS[args.screen]
    src = np.asarray(Image.open(ROOT / spec["source"]).convert("L")
                     .resize((780, 1856), Image.LANCZOS)).astype(int)
    ren = np.asarray(Image.open(WORK / f"{args.screen}.png").convert("L")).astype(int)
    w = min(src.shape[1], ren.shape[1])
    h = min(src.shape[0], ren.shape[0])
    src, ren = src[:h, :w], ren[:h, :w]

    dark_s = (src < args.thr)
    dark_r = (ren < args.thr)
    rows_s = dark_s.sum(axis=1)
    rows_r = dark_r.sum(axis=1)

    print(f"{args.screen}: scanning {h//2} css rows")
    print(" css y    src_ink ren_ink  dx(px)  drift")
    i = 0
    deltas = {}
    while i < h:
        if rows_s[i] > 4 and rows_r[i] > 4:
            j = i
            while j < h and (rows_s[j] > 4 or rows_r[j] > 4):
                j += 1
            band_s = dark_s[i:j]
            band_r = dark_r[i:j]
            xs_s = np.nonzero(band_s.any(axis=0))[0]
            xs_r = np.nonzero(band_r.any(axis=0))[0]
            if len(xs_s) and len(xs_r):
                d = (xs_s.min() - xs_r.min()) / 2
                deltas[round(d * 2) / 2] = deltas.get(round(d * 2) / 2, 0) + 1
                if len(xs_s) > 8:
                    print(f" {i//2:5d} {band_s.sum():8d} {band_r.sum():8d}"
                          f"  {d:+6.2f}")
            i = j
        else:
            i += 1
    print("\ndrift histogram (css px -> #rows):")
    for k in sorted(deltas):
        print(f"  {k:+.2f} : {deltas[k]}")


if __name__ == "__main__":
    main()
