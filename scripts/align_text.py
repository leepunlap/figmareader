#!/usr/bin/env python3
"""
Measure the sub-pixel offset of a text region between the source export and
the rendered page.

Chrome rasterises text at a fractional origin, so a block that is off by half
a CSS pixel loses almost every stroke overlap - the single biggest source of
diff in these screens.  This tool prints, for each region, the ink bounding
box in the source and in the render and the delta you need to apply.

  python3 scripts/align_text.py lion-11 \
      --rect 54,287,136,15 --label "chip 1" \
      --rect 73,545,250,16 --label "bubble p2 l1"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402


def ink_bbox(a, x0, y0, x1, y1, thr=150):
    """Ink bbox inside a css rect of a 2x image (returns css floats)."""
    reg = a[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    ys, xs = np.nonzero(reg < thr)
    if not len(ys):
        return None
    return (xs.min() / 2 + x0, xs.max() / 2 + x0,
            ys.min() / 2 + y0, ys.max() / 2 + y0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--rect", action="append", required=True,
                    help="x,y,w,h[,label] in css px")
    args = ap.parse_args()

    src_path = ROOT / SCREENS[args.screen]["source"]
    css_w, css_h = SCREENS[args.screen]["w"], SCREENS[args.screen]["h"]
    src = np.asarray(Image.open(src_path).convert("L")
                     .resize((css_w * 2, css_h * 2), Image.LANCZOS)).astype(int)
    ren = np.asarray(Image.open(WORK / f"{args.screen}.png").convert("L")).astype(int)

    for spec in args.rect:
        parts = spec.split(",")
        x, y, w, h = (int(v) for v in parts[:4])
        label = parts[4] if len(parts) > 4 else ""
        sb = ink_bbox(src, x, y, x + w, y + h)
        rb = ink_bbox(ren, x, y, x + w, y + h)
        if not sb or not rb:
            print(f"{label:22s} (no ink: src={bool(sb)} ren={bool(rb)})")
            continue
        dx = sb[0] - rb[0]
        dy = sb[2] - rb[2]
        dw = (sb[1] - sb[0]) - (rb[1] - rb[0])
        dh = (sb[3] - sb[2]) - (rb[3] - rb[2])
        print(f"{label:22s} dx={dx:+6.2f}  dy={dy:+6.2f}   dW={dw:+6.2f} dH={dh:+6.2f}"
              f"   src w={sb[1]-sb[0]:.2f} h={sb[3]-sb[2]:.2f}"
              f" | ren w={rb[1]-rb[0]:.2f} h={rb[3]-rb[2]:.2f}")


if __name__ == "__main__":
    main()
