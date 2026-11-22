#!/usr/bin/env python3
"""
Measure the ink box of a horizontal slice of an export.

Used to compare a 7.3 export with its v1.0 twin and find out whether the
difference is a size, a position or a colour difference.

    python3 scripts/slice.py source/v1raw73/screens/v73-competition-01.png 70,60,150,30
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def ink_box(path: Path, x0: int, y0: int, x1: int, y1: int, scale: int = 4):
    """Ink bbox (in css px) inside a css-space rect, plus ink colour."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    x0d, y0d, x1d, y1d = x0 * scale, y0 * scale, x1 * scale, y1 * scale
    reg = a[y0d:y1d, x0d:x1d]
    if reg.size == 0:
        return None
    # background = the region's own border columns/rows
    bg = np.concatenate([
        reg[:, :2].reshape(-1, 3), reg[:, -2:].reshape(-1, 3),
        reg[:2, :].reshape(-1, 3), reg[-2:, :].reshape(-1, 3),
    ])
    bgc = np.median(bg, axis=0)
    dist = np.abs(reg - bgc).sum(axis=2)
    hot = dist > 60
    if not hot.any():
        return None
    ys, xs = np.nonzero(hot)
    top = y0 + ys.min() / scale
    bot = y0 + ys.max() / scale
    left = x0 + xs.min() / scale
    right = x0 + xs.max() / scale
    ink = reg[hot]
    inkc = np.median(ink, axis=0)
    return dict(top=round(top, 2), bottom=round(bot, 2), left=round(left, 2),
                right=round(right, 2), h=round(bot - top, 2), w=round(right - left, 2),
                ink=[int(v) for v in inkc], bg=[int(v) for v in bgc])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--rect", required=True, help="css x0,y0,x1,y1")
    args = ap.parse_args()
    x0, y0, x1, y1 = (int(v) for v in args.rect.split(","))
    for p in args.paths:
        b = ink_box(Path(p), x0, y0, x1, y1)
        print(f"{Path(p).name:34s} {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
