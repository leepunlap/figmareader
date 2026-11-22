#!/usr/bin/env python3
"""
Find where an already extracted asset sits inside its export.

The artwork of a screen is often cut out in one piece (a poster, a photo
grid, the mascot at the bottom).  Once the crop exists, the only thing left
is to know where to put it, and the export knows that exactly: slide the
crop over the export and take the position where the two agree.

    python3 scripts/place.py v1-home-1 assets/v1/home-1-vip.png
    python3 scripts/place.py v1-home-1 assets/v1/home-1-vip.png --pad 40
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
    ap.add_argument("asset")
    ap.add_argument("--pad", type=int, default=60, help="search radius in css px")
    ap.add_argument("--step", type=int, default=1, help="search step in css px")
    args = ap.parse_args()

    src = Image.open(source_png(args.slug)).convert("RGB")
    W, H = src.size
    ast = Image.open(args.asset).convert("RGB")
    aw, ah = ast.size

    best = None
    for y in range(0, H - ah + 1, args.step * 4):
        for x in range(0, W - aw + 1, args.step * 4):
            d = np.abs(np.asarray(src.crop((x, y, x + aw, y + ah))).astype(np.int16)
                       - np.asarray(ast).astype(np.int16)).sum(axis=2)
            v = float((d > 24).mean())
            if best is None or v < best[0]:
                best = (v, x, y)
    if best is None:
        print("[error] the asset is larger than the export")
        return 1
    v, x, y = best
    # refine on the 1 css grid
    for yy in range(max(0, y - 4), min(H - ah, y + 4) + 1):
        for xx in range(max(0, x - 4), min(W - aw, x + 4) + 1):
            d = np.abs(np.asarray(src.crop((xx, yy, xx + aw, yy + ah))).astype(np.int16)
                       - np.asarray(ast).astype(np.int16)).sum(axis=2)
            vv = float((d > 24).mean())
            if vv < v:
                v, x, y = vv, xx, yy
    print(f"{args.asset} -> css left {x / 4:.2f}px top {y / 4:.2f}px "
          f"(w {aw / 4:.2f} h {ah / 4:.2f})  mismatch {v * 100:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
