#!/usr/bin/env python3
"""
Compare a text region between the Figma export and the rendered page and
print the offset you have to apply.

Unlike scripts/align_text.py this does not assume dark ink on a light
background: it looks for pixels that differ from the region's own background
colour, so it works for white text on a gradient header too.

    python3 scripts/txtcmp.py v1-points-mall \
        --rect 40,225,160,25,r1title \
        --rect 55,160,45,24,tab1

`--rect` is x,y,w,h[,label] in css px.  The source is compared at 2x, the
same as the render.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402


def ink_bbox(a: np.ndarray, x0: int, y0: int, x1: int, y1: int, tol: int = 26):
    """bbox of pixels that differ from the region's modal colour (css floats)."""
    reg = a[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    if reg.size == 0:
        return None
    flat = reg.reshape(-1, reg.shape[-1])
    if flat.shape[1] == 1:
        vals, counts = np.unique(flat, axis=0, return_counts=True)
        bg = vals[int(np.argmax(counts))]
        m = np.abs(flat.astype(int) - int(bg)).max(axis=1) > tol
    else:
        cols, counts = np.unique(flat, axis=0, return_counts=True)
        bg = cols[int(np.argmax(counts))]
        m = np.abs(flat.astype(int) - bg.astype(int)).max(axis=1) > tol
    if not m.any():
        return None
    ys, xs = np.nonzero(m.reshape(reg.shape[:2]))
    return (xs.min() / 2 + x0, xs.max() / 2 + x0, ys.min() / 2 + y0, ys.max() / 2 + y0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--rect", action="append", required=True)
    ap.add_argument("--tol", type=int, default=26)
    args = ap.parse_args()

    info = SCREENS[args.screen]
    css_w, css_h = info["w"], info["h"]
    src = np.asarray(Image.open(ROOT / info["source"]).convert("RGB")
                     .resize((css_w * 2, css_h * 2), Image.LANCZOS)).astype(int)
    ren = np.asarray(Image.open(WORK / f"{args.screen}.png").convert("RGB")).astype(int)

    for spec in args.rect:
        parts = spec.split(",")
        x, y, w, h = (int(v) for v in parts[:4])
        label = parts[4] if len(parts) > 4 else ""
        sb = ink_bbox(src, x, y, x + w, y + h, args.tol)
        rb = ink_bbox(ren, x, y, x + w, y + h, args.tol)
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
