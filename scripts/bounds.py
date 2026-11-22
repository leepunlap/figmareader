#!/usr/bin/env python3
"""
Compare the bounding box of individual home-screen elements between the Figma
export and the rendered page.

  python3 scripts/bounds.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RENDER = Path("/tmp/figma-render")

src = np.asarray(Image.open(ROOT / "source" / "home.png").convert("RGB")).astype(int)
ren = np.asarray(Image.open(RENDER / "home.png").convert("RGB")).astype(int)
S = 4  # source scale


def box(arr: np.ndarray, scale: int, pred, region):
    x0, y0, x1, y1 = region
    patch = arr[y0 * scale : y1 * scale, x0 * scale : x1 * scale]
    m = pred(patch)
    if not m.any():
        return None
    ys, xs = np.where(m)
    return (
        round(x0 + xs.min() / scale, 2),
        round(y0 + ys.min() / scale, 2),
        round(x0 + xs.max() / scale, 2),
        round(y0 + ys.max() / scale, 2),
    )


def near(px, c, tol=14):
    return np.abs(px - np.array(c)).sum(axis=2) <= tol


CHECKS = [
    ("hero bottom",  (0, 380, 390, 440), lambda p: near(p, (255, 249, 244), 6)),
    ("photo",        (0, 100, 390, 320), lambda p: near(p, (255, 255, 255), 8)),
    ("instructor",   (140, 300, 390, 400), lambda p: near(p, (255, 255, 255), 6)),
    ("section icon", (0, 410, 90, 500), lambda p: near(p, (254, 184, 146), 10)),
    ("outcome pill", (0, 520, 390, 600), lambda p: near(p, (255, 255, 255), 6)),
    ("card1",        (0, 610, 200, 740), lambda p: near(p, (255, 255, 255), 6)),
    ("card2",        (195, 610, 390, 740), lambda p: near(p, (255, 255, 255), 6)),
    ("card3",        (0, 725, 200, 855), lambda p: near(p, (255, 255, 255), 6)),
    ("cta",          (0, 850, 390, 940), lambda p: near(p, (254, 136, 74), 14)),
    ("indicator",    (100, 930, 290, 975), lambda p: near(p, (41, 38, 45), 40)),
]

print(f"{'element':14s} {'source bbox (x0,y0,x1,y1)':>40s}   {'render bbox':>40s}")
for name, region, pred in CHECKS:
    s = box(src, S, pred, region)
    r = box(ren, 2, pred, region)
    flag = "" if s and r and all(abs(a - b) < 1.2 for a, b in zip(s, r)) else "   <-- differs"
    print(f"{name:14s} {str(s):>40s}   {str(r):>40s}{flag}")
