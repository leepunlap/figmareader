#!/usr/bin/env python3
"""
Fit a 2-D polynomial to a smooth gradient region and emit a tiny PNG.

A Figma header gradient is not a single plane-linear ramp, so CSS gradients
cannot reproduce it exactly.  Instead this fits each colour channel with a low
order 2-D polynomial (robustly rejecting UI chrome drawn on top of it) and
writes a small PNG that is stretched with `background-size: 100% 100%`.

  python3 scripts/fit_gradient2d.py source/lion/lion-03-org-feed-a.png \
      --region 0,0,390,113 --out assets/lion/header-grad.png --w 96 --h 32
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
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--w", type=int, default=96)
    ap.add_argument("--h", type=int, default=32)
    ap.add_argument("--degree", type=int, default=4)
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--out-region", help="css x,y,w,h the emitted bitmap covers; "
                                        "defaults to --region.  Lets the fitted "
                                        "surface be extrapolated past the fitted "
                                        "band (e.g. down to the sheet's rounded "
                                        "corners).")
    args = ap.parse_args()

    s = args.scale
    x, y, w, h = (float(v) for v in args.region.split(","))
    if args.out_region:
        ox, oy, ow, oh = (float(v) for v in args.out_region.split(","))
    else:
        ox, oy, ow, oh = x, y, w, h
    reg = np.asarray(Image.open(args.png).convert("RGB")).astype(np.float64)
    reg = reg[int(y * s):int((y + h) * s), int(x * s):int((x + w) * s)]
    H, W = reg.shape[:2]

    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx / (W - 1)) * 2 - 1
    v = (yy / (H - 1)) * 2 - 1

    terms = []
    for dv in range(args.degree + 1):
        for du in range(args.degree + 1 - dv):
            terms.append((u ** du) * (v ** dv))
    A = np.stack([t.ravel() for t in terms], axis=1)

    keep = np.ones(H * W, dtype=bool)
    coef = None
    for _ in range(args.iters):
        sol, *_ = np.linalg.lstsq(A[keep], reg.reshape(-1, 3)[keep], rcond=None)
        coef = sol
        pred = A @ sol
        resid = np.abs(reg.reshape(-1, 3) - pred).sum(axis=1)
        sigma = max(1.0, np.median(resid[keep]))
        keep = resid < max(12.0, 3.0 * sigma)
    pred = np.clip(A @ coef, 0, 255)

    err = np.abs(reg.reshape(-1, 3)[keep] - pred[keep]).mean()
    print(f"fit residual on {keep.mean()*100:.1f}% of pixels: {err:.2f}/765")

    # render the fitted surface on the small grid
    gy, gx = np.mgrid[0:args.h, 0:args.w]
    # map the output rectangle back onto the fitted rectangle's u/v space
    gu = ((ox + gx / (args.w - 1) * ow) - x) / w * 2 - 1
    gv = ((oy + gy / (args.h - 1) * oh) - y) / h * 2 - 1
    B = np.stack([((gu ** du) * (gv ** dv)).ravel()
                  for dv in range(args.degree + 1)
                  for du in range(args.degree + 1 - dv)], axis=1)
    small = np.clip(B @ coef, 0, 255).reshape(args.h, args.w, 3).astype(np.uint8)
    Image.fromarray(small).save(args.out)
    print(f"{args.out}  {args.w}x{args.h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
