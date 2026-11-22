#!/usr/bin/env python3
"""
Point at the parts of a screen that still differ from the export.

The screen is compared with its render, split into bands, and the bands with
the most differing pixels are listed together with the OCR runs and the
images that sit in them.  That is where the work is.

    python3 scripts/where.py v73-competition-01
    python3 scripts/where.py v1-competition-detail-closed --top 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")


def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--band", type=int, default=50, help="band height in css px")
    args = ap.parse_args()

    slug = args.slug
    ren = WORK / f"{slug}.png"
    if not ren.exists():
        print(f"[error] no render for {slug}; run scripts/render_check.py {slug}")
        return 1
    src = Image.open(source_png(slug)).convert("RGB")
    r = Image.open(ren).convert("RGB")
    if r.size != src.size:
        src = src.resize(r.size, Image.LANCZOS)
    A = np.asarray(r).astype(np.int16)
    B = np.asarray(src).astype(np.int16)
    hot = np.abs(A - B).sum(axis=2) > 24
    scale = r.size[0] / (src.size[0] / 4)
    print(f"{slug}  {r.size}  total {hot.mean() * 100:.2f}%")

    step = args.band * scale
    bands = []
    for i in range(0, hot.shape[0], int(step)):
        seg = hot[i:i + int(step)]
        if seg.size:
            bands.append((i / scale, float(seg.mean() * 100)))
    bands.sort(key=lambda b: -b[1])

    tsv = ROOT / "analysis/ocr" / f"{slug}.tsv"
    runs = []
    if tsv.exists():
        for line in tsv.read_text(encoding="utf-8").splitlines():
            p = line.split("\t")
            if len(p) >= 6:
                runs.append((int(p[1]), "\t".join(p[5:]).strip()))

    for y, pct in bands[:args.top]:
        lo, hi = y - 4, y + args.band + 4
        hits = [t for (ry, t) in runs if lo <= ry <= hi]
        print(f"  y={y:7.0f} {pct:6.2f}%  " + " | ".join(repr(t)[:26] for t in hits[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
