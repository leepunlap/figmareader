#!/usr/bin/env python3
"""
Find photographic / illustrative blocks inside a Figma export.

Smooth UI (flat colour, gradients) has near-zero local high-frequency variance;
photos, logos and artwork have a lot.  Scoring windows by the mean absolute
difference between horizontally adjacent pixels isolates real image assets.

  python3 scripts/find_images.py source/lion/lion-03-org-feed-a.png
"""

from __future__ import annotations

import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--win", type=int, default=16, help="window size in css px")
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--thresh", type=float, default=6.0)
    ap.add_argument("--min-size", type=int, default=30)
    ap.add_argument("--max-size", type=int, default=100000)
    args = ap.parse_args()

    s = args.scale
    a = np.asarray(Image.open(args.png).convert("RGB")).astype(np.float64)
    H, W = a.shape[:2]

    # high-frequency energy map
    hf = np.abs(np.diff(a, axis=1)).sum(axis=2)
    hf = np.pad(hf, ((0, 0), (1, 0)))
    hf2 = np.abs(np.diff(a, axis=0)).sum(axis=2)
    hf2 = np.pad(hf2, ((1, 0), (0, 0)))
    energy = (hf + hf2) / 2.0

    win = args.win * s
    step = args.stride * s

    hits = np.zeros((H, W), dtype=bool)
    for y in range(0, max(1, H - win), step):
        for x in range(0, max(1, W - win), step):
            blk = energy[y:y + win, x:x + win]
            if blk.mean() > args.thresh:
                hits[y:y + win, x:x + win] = True

    rows = hits.any(axis=1)
    bands = []
    y = 0
    while y < H:
        if rows[y]:
            y2 = y
            while y2 + 1 < H and rows[y2 + 1]:
                y2 += 1
            bands.append((y, y2 + 1))
            y = y2 + 1
        else:
            y += 1

    out = []
    for (y0, y1) in bands:
        band = hits[y0:y1]
        cols = band.any(axis=0)
        x = 0
        while x < W:
            if cols[x]:
                x2 = x
                while x2 + 1 < W and cols[x2 + 1]:
                    x2 += 1
                w = (x2 - x) / s
                h = (y1 - y0) / s
                if args.min_size <= w <= args.max_size and args.min_size <= h <= args.max_size:
                    out.append((x / s, y0 / s, x2 / s, y1 / s))
                x = x2 + 1
            else:
                x += 1

    for (x0, y0, x1, y1) in out:
        print(f"  x {x0:7.2f}..{x1:7.2f}  y {y0:7.2f}..{y1:7.2f}   "
              f"({x1-x0:7.1f} x {y1-y0:7.1f} css)")
    print(f"\n{len(out)} image blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
