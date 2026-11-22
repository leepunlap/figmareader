#!/usr/bin/env python3
"""
Measure the CJK character advance of every text run in the Figma exports.

The design's type is not plain Noto Sans TC: several strings are set with
negative letter-spacing (e.g. the "7 天學習成果" pill advances 16px at an 18px
font size).  This script finds the ink column runs inside a region and reports
the median advance, so the CSS letter-spacing can be derived rather than
guessed.

  python3 scripts/advances.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# label, screen, css rect, font-size, weight, mode
RUNS = [
    ("hero age",      "home", (18, 46, 120, 22), 13, 400, "light"),
    ("hero title",    "home", (18, 76, 260, 30), 25, 700, "light"),
    ("hero lede L1",  "home", (18, 320, 150, 18), 13, 400, "light"),
    ("hero lede L2",  "home", (18, 336, 150, 18), 13, 400, "light"),
    ("hero name",     "home", (225, 325, 140, 22), 15, 700, "dark"),
    ("hero role",     "home", (225, 343, 140, 20), 13, 400, "dark"),
    ("section title", "home", (80, 426, 280, 28), 21, 700, "dark"),
    ("section lede1", "home", (80, 462, 290, 20), 14, 400, "dark"),
    ("outcome pill",  "home", (120, 548, 200, 22), 18, 700, "light"),
    ("caption",       "home", (90, 592, 220, 20), 13, 400, "dark"),
    ("card1 title",   "home", (66, 638, 140, 18), 13, 700, "dark"),
    ("card1 text1",   "home", (66, 656, 130, 18), 13, 400, "dark"),
    ("banner title",  "list-020", (18, 252, 250, 30), 22, 700, "light"),
    ("banner dur",    "list-020", (32, 292, 130, 18), 13, 400, "light"),
    ("progress",      "list-020", (18, 360, 120, 20), 13, 400, "dark"),
    ("section title", "list-020", (47, 408, 200, 26), 18, 700, "dark"),
    ("task1 title",   "list-020", (91, 458, 200, 20), 15, 700, "dark"),
    ("task1 desc",    "list-020", (91, 479, 260, 20), 12, 400, "dark"),
    ("task2 title",   "list-020", (91, 528, 220, 20), 15, 700, "dark"),
]


def runs_for(arr: np.ndarray, scale: int, region, mode: str):
    x0, y0, w, h = region
    patch = arr[y0 * scale:(y0 + h) * scale, x0 * scale:(x0 + w) * scale]
    if mode == "light":
        m = np.all(patch >= 250, axis=2)
    else:
        flat = patch.reshape(-1, 3)
        keys = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2].astype(np.int32)
        vals, counts = np.unique(keys, return_counts=True)
        k = int(vals[np.argmax(counts)])
        bg = np.array([(k >> 16) & 0xFF, (k >> 8) & 0xFF, k & 0xFF])
        m = np.abs(patch - bg).sum(axis=2) > 40
    cols = m.any(axis=0)
    out = []
    start = None
    for i, v in enumerate(cols):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start / scale, (i - 1) / scale))
            start = None
    if start is not None:
        out.append((start / scale, (len(cols) - 1) / scale))
    return [r for r in out if r[1] - r[0] > 0.4]


def main() -> int:
    imgs = {
        s: np.asarray(Image.open(ROOT / "source" / f"{s}.png").convert("RGB")).astype(int)
        for s in ("home", "list-020")
    }
    print(f"{'element':16s} {'size':>5s} {'runs':>5s}  advances (start-to-start)        implied ls")
    for label, screen, region, size, weight, mode in RUNS:
        r = runs_for(imgs[screen], 4, region, mode)
        if len(r) < 2:
            print(f"{label:16s} {size:5d} {len(r):5d}  {r}")
            continue
        starts = [a for a, _ in r]
        adv = [round(starts[i + 1] - starts[i], 2) for i in range(len(starts) - 1)]
        # keep only advances close to the font size (CJK advances)
        cjk = [a for a in adv if a > size * 0.75]
        med = float(np.median(cjk)) if cjk else float(np.median(adv))
        print(
            f"{label:16s} {size:5d} {len(r):5d}  {str(adv):36s} {med - size:+.2f}px"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
