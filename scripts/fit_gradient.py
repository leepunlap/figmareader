#!/usr/bin/env python3
"""
Fit a CSS linear-gradient to a flat gradient region of a Figma export.

Samples the region, then for every candidate angle projects the pixels onto the
gradient axis and measures how well a single colour ramp explains them.  Prints
the best angle and the colour stops along that axis.

  python3 scripts/fit_gradient.py source/lion/lion-03-org-feed-a.png --region 0,0,390,113
"""

from __future__ import annotations

import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--region", required=True, help="css x,y,w,h")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--stops", type=int, default=6)
    args = ap.parse_args()

    s = args.scale
    x, y, w, h = (float(v) for v in args.region.split(","))
    a = np.asarray(Image.open(args.png).convert("RGB")).astype(np.float64)

    reg = a[int(y * s):int((y + h) * s), int(x * s):int((x + w) * s)]
    # sample every 4th pixel
    reg = reg[::4, ::4]
    H, W = reg.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    xs = ((xx * 4 / s) + x).ravel()
    ys = ((yy * 4 / s) + y).ravel()

    best = None
    for deg in range(0, 180):
        t = np.radians(deg)
        u = xs * np.cos(t) + ys * np.sin(t)
        order = np.argsort(u)
        us = u[order]
        cols = reg.reshape(-1, 3)[order]
        # fit each channel as a function of u with a piecewise-linear basis
        resid = 0.0
        for c in range(3):
            v = cols[:, c]
            # bin into 60 buckets, average, then measure deviation from the ramp
            bins = np.clip(((us - us.min()) / (us.max() - us.min() + 1e-9) * 59).astype(int), 0, 59)
            prof = np.array([v[bins == b].mean() if (bins == b).any() else np.nan for b in range(60)])
            good = ~np.isnan(prof)
            prof = np.interp(np.arange(60), np.flatnonzero(good), prof[good])
            pred = prof[bins]
            resid += float(((v - pred) ** 2).mean())
        if best is None or resid < best[1]:
            best = (deg, resid)

    deg, resid = best
    print(f"best angle: {deg}deg   residual {resid:.2f}\n")

    t = np.radians(deg)
    u = xs * np.cos(t) + ys * np.sin(t)
    order = np.argsort(u)
    us, cols = u[order], reg.reshape(-1, 3)[order]
    lo, hi = us.min(), us.max()

    print("stops along the axis:")
    for i in range(args.stops + 1):
        f = i / args.stops
        target = lo + f * (hi - lo)
        idx = int(np.argmin(np.abs(us - target)))
        px = cols[idx]
        print(f"  {f*100:5.1f}%  #{int(px[0]):02x}{int(px[1]):02x}{int(px[2]):02x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
