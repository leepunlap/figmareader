#!/usr/bin/env python3
"""Compare every text line of a screen, export vs render.

For each OCR run it measures the ink box of that line in the export and in the
render and prints the offsets.  Offsets near zero mean the line is placed
correctly; a large offset, or a width that does not match, means the line is
placed wrongly or its text is wrong.

The background colour is taken as the most common colour in the band, so the
tool works on white cards, coloured chips and the gradient header alike.

  python3 scripts/lineaudit.py v1-competition-detail-closed
  python3 scripts/lineaudit.py v1-competition-detail-closed --only 17,24,26
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")


def load(slug: str):
    p = ROOT / "source/v1raw/screens" / f"{slug.replace('v1-', '')}.png"
    if not p.exists():
        p = ROOT / "source/v1raw73/screens" / f"{slug}.png"
    src = Image.open(p).convert("RGB")
    r = Image.open(WORK / f"{slug}.png").convert("RGB")
    if r.size != src.size:
        src = src.resize(r.size, Image.LANCZOS)
    return np.asarray(src).astype(int), np.asarray(r).astype(int)


def inkbox(im, y0, y1, x0, x1, thr=60):
    """Ink box of the band, using the modal colour as the background."""
    reg = im[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    if reg.size == 0:
        return None
    flat = reg.reshape(-1, 3)
    bg = np.array(Counter(map(tuple, flat)).most_common(1)[0][0])
    d = np.abs(reg - bg).sum(axis=2)
    m = d > thr
    if not m.any():
        return None
    ys = np.nonzero(m.any(axis=1))[0]
    xs = np.nonzero(m.any(axis=0))[0]
    return (round(x0 + xs.min() / 2, 1), round(x0 + xs.max() / 2, 1),
            round(y0 + ys.min() / 2, 1), round(y0 + ys.max() / 2, 1),
            int(m.sum()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--only", default="")
    ap.add_argument("--pad", type=int, default=3)
    args = ap.parse_args()

    slug = args.slug
    a, b = load(slug)
    runs = json.load(open(ROOT / "analysis/ocr" / f"{slug}-fit.json"))
    only = set(int(v) for v in args.only.split(",")) if args.only else None

    print("%-3s %-6s %-6s %-6s %-6s %-6s %-6s %-6s  %s"
          % ("#", "dx0", "dx1", "dy0", "dy1", "w_src", "w_ren", "ink", "text"))
    for i, r in enumerate(runs):
        if only is not None and i not in only:
            continue
        y0 = int(r["src_y0"]) - args.pad
        y1 = int(r["src_y1"]) + args.pad
        x0 = max(0, int(r["src_x0"]) - args.pad)
        x1 = min(402, int(r["src_x1"]) + 18)
        s = inkbox(a, y0, y1, x0, x1)
        n = inkbox(b, y0, y1, x0, x1)
        if not s or not n:
            print("%-3d  %s" % (i, "missing ink in " + ("render" if s else "source")))
            continue
        dx0 = n[0] - s[0]
        dx1 = n[1] - s[1]
        dy0 = n[2] - s[2]
        dy1 = n[3] - s[3]
        ws = s[1] - s[0]
        wr = n[1] - n[0]
        ratio = n[4] / max(1, s[4])
        flag = ""
        if abs(dx0) > 2 or abs(dx1) > 2:
            flag += " X"
        if abs(ws - wr) > 4:
            flag += " W"
        if ratio < 0.8 or ratio > 1.25:
            flag += " I"
        print("%-3d %+6.1f %+6.1f %+6.1f %+6.1f %6.1f %6.1f %5.2f  %s%s"
              % (i, dx0, dx1, dy0, dy1, ws, wr, ratio, r["text"][:30], flag))


if __name__ == "__main__":
    main()
