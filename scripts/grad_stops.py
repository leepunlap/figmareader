#!/usr/bin/env python3
"""
Turn the vertical page gradient of a screen into CSS gradient stops.

The 7.3 / v1 home screens run a single vertical gradient down the page.  The
gradient is sampled straight out of the 4x export (clean columns only, so no
card or illustration contaminates the samples) and written as a
`linear-gradient(180deg, ...)` with one stop per sample row.

    python3 scripts/grad_stops.py v1-home-1 371 559 --out /tmp/stops.css
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent


def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("top", type=int, help="band top in css px")
    ap.add_argument("height", type=int, help="band height in css px")
    ap.add_argument("--cols", default="385,195",
                    help="css x columns to sample, most reliable first")
    ap.add_argument("--step", type=int, default=3, help="rows per stop")
    ap.add_argument("--from-row", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    img = np.asarray(Image.open(source_png(args.slug)).convert("RGB")).astype(int)
    cols = [int(c) for c in args.cols.split(",")]

    rows = []
    start = args.from_row if args.from_row is not None else args.top
    for y in range(start, args.top + args.height, args.step):
        best = None
        for c in cols:
            px = img[y * 4, c * 4]
            # reject cream / white / very light pixels (those are panels)
            if px.sum() > 700 or px.min() > 235:
                continue
            if best is None:
                best = px
        if best is None:
            continue
        rows.append((y, tuple(int(v) for v in best)))

    stops = []
    for y, c in rows:
        pct = (y - args.top) / args.height * 100
        stops.append(f"#{c[0]:02x}{c[1]:02x}{c[2]:02x} {pct:.2f}%")
    css = "background: linear-gradient(180deg,\n    " + ",\n    ".join(stops) + ");"
    if args.out:
        Path(args.out).write_text(css, encoding="utf-8")
    print(css)
    return 0


if __name__ == "__main__":
    sys.exit(main())
