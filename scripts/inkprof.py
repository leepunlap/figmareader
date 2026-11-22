#!/usr/bin/env python3
"""Compare a horizontal band of the export against the render.

Reports, for each band:
  hot%     fraction of band pixels whose summed |dRGB| exceeds 24
  iou      intersection-over-union of the two ink masks (shape agreement)
  ink      render ink area / source ink area (stroke weight agreement)
  dx, dy   the shift that maximises the match

The export is a 4x PNG, the render a 2x PNG; the export is downscaled with
LANCZOS first so both live in the same pixel grid.

  python3 scripts/inkprof.py v1-competition-detail-closed --bands 540,560 560,580
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")


def load(slug: str):
    p = ROOT / "source" / "v1raw" / "screens" / f"{slug.replace('v1-', '')}.png"
    if not p.exists():
        p = ROOT / "source" / "v1raw73" / "screens" / f"{slug}.png"
    src = Image.open(p).convert("RGB")
    r = Image.open(WORK / f"{slug}.png").convert("RGB")
    if r.size != src.size:
        src = src.resize(r.size, Image.LANCZOS)
    return np.asarray(src).astype(int), np.asarray(r).astype(int)


def band(a, b, y0, y1, x0=0, x1=402, search=6):
    s = a[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    best = None
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            yy0 = y0 * 2 + dy * 2
            xx0 = x0 * 2 + dx * 2
            if yy0 < 0 or xx0 < 0 or yy0 + s.shape[0] > b.shape[0] or xx0 + s.shape[1] > b.shape[1]:
                continue
            r = b[yy0:yy0 + s.shape[0], xx0:xx0 + s.shape[1]]
            hot = (np.abs(s - r).sum(axis=2) > 24)
            ms = s.sum(axis=2) < 700
            mr = r.sum(axis=2) < 700
            inter = (ms & mr).sum()
            union = (ms | mr).sum()
            iou = inter / max(1, union)
            score = iou
            if best is None or score > best[0]:
                best = (score, hot.mean() * 100, iou, ms.sum(), mr.sum(), dx, dy)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--bands", default="")
    ap.add_argument("--x", default="0,402")
    args = ap.parse_args()

    a, b = load(args.slug)
    x0, x1 = (int(v) for v in args.x.split(","))
    if args.bands:
        bands = []
        for part in args.bands.split(","):
            y0, y1 = (int(v) for v in part.split("-"))
            bands.append((y0, y1))
    else:
        rows = (np.abs(a - b).sum(axis=2) > 24).sum(axis=1)
        n = len(rows) // 20 * 20
        rb = rows[:n].reshape(-1, 20).sum(axis=1)
        order = sorted(range(len(rb)), key=lambda i: -rb[i])[:20]
        bands = sorted((i * 20, i * 20 + 20) for i in order)

    for y0, y1 in bands:
        best = band(a, b, y0, y1, x0, x1)
        if not best:
            continue
        _, hot, iou, ms, mr, dx, dy = best
        ratio = mr / max(1, ms)
        print("y %5d-%5d  hot %5.2f%%  iou %.3f  ink %5d/%5d (%.2fx)  best dx %+d dy %+d"
              % (y0, y1, hot, iou, ms, mr, ratio, dx, dy))


if __name__ == "__main__":
    main()
