#!/usr/bin/env python3
"""
Rank the diff pixels of a rendered screen by region, so effort goes where the
error actually is.

  python3 scripts/diff_regions.py lion-11 --grid 40
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

WORK = Path("/tmp/figma-render")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--grid", type=int, default=40)
    args = ap.parse_args()

    r = np.asarray(Image.open(WORK / f"{args.screen}.png").convert("RGB")).astype(int)
    d = np.asarray(Image.open(WORK / f"{args.screen}-diff.png").convert("RGB")).astype(int)
    h, w, _ = r.shape
    # the diff overlay paints differing pixels magenta; anything else is grey
    magenta = (d[:, :, 0] > 200) & (d[:, :, 1] < 120) & (d[:, :, 2] > 60)
    total = int(magenta.sum())
    print(f"{args.screen}: {total} differing px of {w*h} ({total/(w*h)*100:.2f} %)")

    g = args.grid
    rows = []
    for y0 in range(0, h, g):
        for x0 in range(0, w, g):
            blk = magenta[y0:y0+g, x0:x0+g]
            n = int(blk.sum())
            if n:
                rows.append((n, x0, y0, x0 + g, y0 + g))
    rows.sort(reverse=True)
    print("top regions (css px, 2x image):")
    for n, x0, y0, x1, y1 in rows[:22]:
        print(f"  x {x0//2:6.1f}-{x1//2:6.1f}  y {y0//2:6.1f}-{y1//2:6.1f}   {n:7d} px  "
              f"{n/(w*h)*100:5.2f} % of page")


if __name__ == "__main__":
    main()
