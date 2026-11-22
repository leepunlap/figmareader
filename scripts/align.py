#!/usr/bin/env python3
"""
Find the translation that best aligns two exports.

The 7.3 Figma page was exported per *section*, so every phone inside a section
was rasterised at its fractional position inside the section canvas.  The
resulting screen PNG is the artboard shifted by a sub-pixel amount, which is
enough to wreck a pixel comparison even though the design is identical.

This tool searches integer device-pixel offsets and prints the best one for
the whole screen and for the top / bottom half separately, so a pure
translation can be told apart from a scale.

    python3 scripts/align.py source/v1raw73/screens/v73-competition-01.png \
        source/v1raw/screens/my-competition-all.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def best_shift(a: np.ndarray, b: np.ndarray, rng: int = 4):
    """Return (dy, dx, pct) minimising the differing-pixel share."""
    h, w = a.shape[:2]
    best = None
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            # slide a over b
            ys0, ys1 = max(0, -dy), min(h, h - dy)
            xs0, xs1 = max(0, -dx), min(w, w - dx)
            if ys1 - ys0 < 40 or xs1 - xs0 < 40:
                continue
            pa = a[ys0:ys1, xs0:xs1]
            pb = b[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            pct = float((np.abs(pa - pb).sum(axis=2) > 24).mean() * 100)
            if best is None or pct < best[2]:
                best = (dy, dx, pct)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--rng", type=int, default=4)
    args = ap.parse_args()

    A = np.asarray(Image.open(args.a).convert("RGB")).astype(np.int16)
    B = np.asarray(Image.open(args.b).convert("RGB")).astype(np.int16)
    h = min(A.shape[0], B.shape[0])
    w = min(A.shape[1], B.shape[1])
    A, B = A[:h, :w], B[:h, :w]
    print(f"images {w}x{h}")
    print(f"  full   dy={best_shift(A, B, args.rng)[0]:+d} dx={best_shift(A, B, args.rng)[1]:+d}"
          f"  {best_shift(A, B, args.rng)[2]:.2f}%")
    for name, sl in (("top", slice(0, h // 2)), ("bot", slice(h // 2, h))):
        dy, dx, pct = best_shift(A[sl], B[sl], args.rng)
        print(f"  {name:4s}  dy={dy:+d} dx={dx:+d}  {pct:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
