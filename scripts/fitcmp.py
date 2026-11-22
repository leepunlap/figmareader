#!/usr/bin/env python3
"""
Compare every fitted text run of a screen against the render and print the
correction that is needed.

For each run of analysis/ocr/<slug>-fit.json it looks for the ink inside the
render (searching a window around the expected position) and reports how far
the ink is off and how much wider or narrower it is than in the export.

    python3 scripts/fitcmp.py v1-competition-detail-open
    python3 scripts/fitcmp.py v1-competition-detail-open --top 30
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


def load(p: Path, size: tuple[int, int]) -> np.ndarray:
    im = Image.open(p).convert("RGB")
    return np.asarray(im.resize(size, Image.LANCZOS)).astype(int)


def ink_box(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, bgcol=None):
    h, w, _ = arr.shape
    x0 = max(0, x0); y0 = max(0, y0); x1 = min(w, x1); y1 = min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    reg = arr[y0:y1, x0:x1]
    flat = reg.reshape(-1, 3)
    if bgcol is None:
        cols, counts = np.unique(flat, axis=0, return_counts=True)
        bg = cols[int(np.argmax(counts))]
    else:
        bg = np.array(bgcol)
    m = np.abs(reg - bg).max(axis=2) > 40
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return (int(xs.min() + x0), int(ys.min() + y0), int(xs.max() + x0), int(ys.max() + y0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--top", type=int, default=0, help="only show the n worst runs")
    ap.add_argument("--y0", type=int, default=-1)
    ap.add_argument("--y1", type=int, default=10 ** 9)
    args = ap.parse_args()

    slug = args.slug
    src_png = (ROOT / "source/v1raw73/screens" / f"{slug}.png" if slug.startswith("v73-")
               else ROOT / "source/v1raw/screens" / f"{slug[3:]}.png")
    ren_png = WORK / f"{slug}.png"
    if not ren_png.exists():
        print(f"[error] no render for {slug}; run scripts/render_check.py {slug}")
        return 1
    si = Image.open(src_png).convert("RGB")
    ri = Image.open(ren_png).convert("RGB")
    W = si.size[0] // 4
    H = si.size[1] // 4
    src = load(src_png, (W, H))
    ren = load(ren_png, (W, H))

    runs = json.loads((ROOT / "analysis/ocr" / f"{slug}-fit.json").read_text(encoding="utf-8"))
    rows = []
    for i, r in enumerate(runs):
        f = r.get("fit")
        if not f:
            continue
        if not (args.y0 <= r["src_y0"] <= args.y1):
            continue
        sw = int(r["src_x1"] - r["src_x0"] + 1)
        sh = int(r["src_y1"] - r["src_y0"] + 1)
        # search window: the expected box, grown generously
        mx = 6
        my = max(3, sh // 3)
        win = ink_box(ren, int(r["src_x0"]) - mx, int(r["src_y0"]) - my,
                      int(r["src_x1"]) + mx, int(r["src_y1"]) + my)
        if win is None:
            rows.append((999, i, r, None, sw, sh))
            continue
        rw = win[2] - win[0] + 1
        rh = win[3] - win[1] + 1
        dx = win[0] - r["src_x0"]
        dy = win[1] - r["src_y0"]
        err = abs(dx) * 2 + abs(dy) * 2 + abs(rw - sw) * 3 + abs(rh - sh) * 2
        rows.append((err, i, r, (win, dx, dy, rw, rh), sw, sh))

    rows.sort(reverse=True, key=lambda t: t[0])
    show = rows[:args.top] if args.top else rows
    print(f"{'#':>3s} {'dx':>4s} {'dy':>4s} {'dW':>5s} {'dH':>4s}  text")
    for err, i, r, info, sw, sh in show:
        if info is None:
            print(f"{i:3d} {'':>4s} {'':>4s} {'':>5s} {'':>4s}  (no ink in render) {r['text'][:40]!r}")
            continue
        win, dx, dy, rw, rh = info
        print(f"{i:3d} {dx:4.1f} {dy:4.1f} {rw - sw:5.1f} {rh - sh:4.1f}  {r['text'][:46]!r}")
    print(f"\n{len(rows)} runs compared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
