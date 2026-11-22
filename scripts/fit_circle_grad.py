#!/usr/bin/env python3
"""
Emit an exact vertical colour-profile PNG for a circular gradient button.

The chat screens' send button is a circle filled with a non-linear vertical
gradient (Figma interpolates it with an eased curve, so a CSS linear-gradient
does not reproduce it).  Because the fill is purely vertical — every column
inside the circle carries the same colour at a given row — one column of the
source export is enough to describe the whole fill.

So: take the median colour of the saturated pixels in each row of the button,
and write it into a narrow PNG that is stretched with `background-size: 100% 100%`
behind the button's `border-radius: 50%`.  The white arrow stays an SVG on top.

  python3 scripts/fit_circle_grad.py source/lion/lion-08-chat-1.png \
      --region 320,837,52,52 --out assets/lion/chat-send-grad.png --scale 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--region", required=True, help="css x,y,w,h of the circle")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=4, help="device px per css px")
    ap.add_argument("--min-sat", type=int, default=30,
                    help="min(max-min) for a pixel to count as the gradient")
    args = ap.parse_args()

    im = Image.open(args.png).convert("RGB")
    A = np.asarray(im).astype(int)
    s = args.scale
    x, y, w, h = (int(v) for v in args.region.split(","))

    rows: list[tuple[int, int, int]] = []
    for dy in range(h):
        yy = (y + dy) * s
        row = A[yy, x * s:(x + w) * s]
        mx = row.max(axis=1)
        mn = row.min(axis=1)
        sat = (mx - mn) > args.min_sat
        if sat.sum() < 2:
            continue
        med = np.median(row[sat], axis=0)
        rows.append((dy, int(round(med[0])), int(round(med[1])), int(round(med[2]))))

    if not rows:
        raise SystemExit("[error] no gradient pixels found")

    # fill any row that the circle's anti-aliased cap left empty by
    # interpolating between the rows we did measure
    by_dy = {r[0]: r[1:] for r in rows}
    strip = []
    for dy in range(h):
        if dy in by_dy:
            strip.append(by_dy[dy])
        else:
            lo = max((d for d in by_dy if d < dy), default=None)
            hi = min((d for d in by_dy if d > dy), default=None)
            if lo is None:
                strip.append(by_dy[hi])
            elif hi is None:
                strip.append(by_dy[lo])
            else:
                t = (dy - lo) / (hi - lo)
                strip.append(tuple(
                    int(round(by_dy[lo][c] + (by_dy[hi][c] - by_dy[lo][c]) * t))
                    for c in range(3)
                ))

    out = Image.new("RGB", (4, h))
    px = out.load()
    for dy, rgb in enumerate(strip):
        for dx in range(4):
            px[dx, dy] = rgb
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out)

    print(f"{args.out}: {out.size[0]}x{out.size[1]} profile")
    print(f"  top    {strip[0]}")
    print(f"  middle {strip[h // 2]}")
    print(f"  bottom {strip[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
