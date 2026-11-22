#!/usr/bin/env python3
"""
Measure the ink bounding box of a text/graphic region in the Figma source and
in the current render, side by side.

For every region (a CSS-pixel rect) it reports
    src  : ink bbox inside the source (2x raster), in CSS px
    ren  : ink bbox inside the render (2x raster), in CSS px
    dx/dy: where the render's ink sits relative to the source
    dw   : how much wider/narrower the render's ink is
    ink  : how much darker/denser the render's ink is (mean darkness)

That is everything needed to correct a heading: position, size, weight.

  python3 scripts/inkbox.py lion-03 --rect 101,64,260,20
  python3 scripts/inkbox.py lion-03 --rects regions.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RENDER = Path("/tmp/figma-render")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402


def load2x(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    if im.width // 4 in (390, 402) and im.width % 4 == 0:
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    return np.asarray(im).astype(np.int32)


def ink_bbox(a: np.ndarray, rect: tuple[int, int, int, int], bg: tuple[int, int, int],
             tol: int = 26):
    """bbox of pixels that differ from the background colour, in CSS px."""
    x, y, w, h = rect
    sub = a[y * 2:(y + h) * 2, x * 2:(x + w) * 2]
    if sub.size == 0:
        return None
    d = np.abs(sub - np.array(bg, dtype=np.int32)).sum(axis=2)
    mask = d > tol
    ys, xs = mask.nonzero()
    if len(xs) == 0:
        return None
    bx0, bx1 = xs.min() / 2 + x, (xs.max() + 1) / 2 + x
    by0, by1 = ys.min() / 2 + y, (ys.max() + 1) / 2 + y
    darkness = float((255 * 3 - sub[mask].sum(axis=1)).mean()) if mask.any() else 0.0
    return {
        "bbox": (round(float(bx0), 2), round(float(by0), 2),
                 round(float(bx1), 2), round(float(by1), 2)),
        "w": round(float(bx1 - bx0), 2),
        "h": round(float(by1 - by0), 2),
        "ink": round(darkness, 1),
        "px": int(mask.sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--rect", action="append", default=[],
                    help="x,y,w,h in CSS px (repeatable)")
    ap.add_argument("--regions", help="json file: {name: [x,y,w,h]}")
    ap.add_argument("--bg", default="#ffffff", help="background colour of the region")
    ap.add_argument("--tol", type=int, default=26)
    args = ap.parse_args()

    hexs = args.bg.lstrip("#")
    bg = tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4))

    regions: dict[str, tuple[int, int, int, int]] = {}
    for r in args.rect:
        parts = tuple(int(v) for v in r.split(","))
        regions[r] = parts
    if args.regions:
        data = json.loads(Path(args.regions).read_text())
        for k, v in data.items():
            regions[k] = tuple(v)

    src = load2x(ROOT / SCREENS[args.screen]["source"])
    ren_path = RENDER / f"{args.screen}.png"
    if not ren_path.exists():
        print(f"no render for {args.screen}; run scripts/render_check.py {args.screen}")
        return 1
    ren = np.asarray(Image.open(ren_path).convert("RGB")).astype(np.int32)

    print(f"{'region':22s} {'src x0,y0 x1,y1':>26s} {'w':>6s} {'ren x0,y0 x1,y1':>26s} "
          f"{'w':>6s} {'dx':>6s} {'dy':>6s} {'dw':>6s} {'ink s/r':>14s}")
    for name, rect in regions.items():
        s = ink_bbox(src, rect, bg, args.tol)
        r = ink_bbox(ren, rect, bg, args.tol)
        if not s or not r:
            print(f"{name:22s} {'(no ink)' if not s else '':>26s}")
            continue
        sb, rb = s["bbox"], r["bbox"]
        print(f"{name:22s} {str(sb):>26s} {s['w']:6.1f} {str(rb):>26s} {r['w']:6.1f} "
              f"{rb[0]-sb[0]:6.1f} {rb[1]-sb[1]:6.1f} {r['w']-s['w']:6.1f} "
              f"{s['ink']:6.1f}/{r['ink']:<7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
