#!/usr/bin/env python3
"""
Find where an extracted asset sits inside its source screen.

The assets are cut out of the 4x exports at 2x, so the search compares the
asset against the source downscaled to 2x.  The result is the css position the
asset belongs at.

    python3 scripts/place2.py v1-home-1 assets/v1/home-1-vip.png
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
    ap.add_argument("--near", default=None, help="comma list of left,top guesses")
    args = ap.parse_args()

    src = Image.open(source_png(args.slug)).convert("RGB")
    S = np.asarray(src.resize((src.width // 2, src.height // 2), Image.LANCZOS)).astype(np.int16)
    A = np.asarray(Image.open(args.asset).convert("RGB")).astype(np.int16)
    if A.shape[0] > S.shape[0] or A.shape[1] > S.shape[1]:
        print("[error] asset larger than screen")
        return 1

    if args.near:
        l, t = (int(v) for v in args.near.split(","))
        cx, cy = l, t
    else:
        cx = (S.shape[1] - A.shape[1]) // 2
        cy = (S.shape[0] - A.shape[0]) // 2

    best = None
    for dy in range(-24, 25):
        for dx in range(-24, 25):
            y = cy + dy
            x = cx + dx
            if y < 0 or x < 0 or y + A.shape[0] > S.shape[0] or x + A.shape[1] > S.shape[1]:
                continue
            reg = S[y:y + A.shape[0], x:x + A.shape[1]]
            d = np.abs(reg - A)
            # only compare where the asset is not fully transparent
            pct = float((d.sum(axis=2) > 40).mean() * 100)
            if best is None or pct < best[2]:
                best = (x, y, pct)
    x, y, pct = best
    print(f"{Path(args.asset).name:26s} -> css left {x / 2:.2f}px top {y / 2:.2f}px "
          f"(w {A.shape[1] / 2:.2f} h {A.shape[0] / 2:.2f})  mismatch {pct:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
