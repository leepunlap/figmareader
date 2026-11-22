#!/usr/bin/env python3
"""
Report ink geometry inside one CSS-space region of a Figma PNG export.

frame_analyze.py segments a whole screen; this drills into a single component
(a task card, the hero block, a progress row) and prints the boxes it finds,
in absolute CSS pixels, with the local background colour of that region.

Usage
  python3 scripts/region_report.py source/list-020.png --scale 4 --region 20,448,350,62
  python3 scripts/region_report.py source/home.png --scale 4 --region 0,0,390,412 --min-frac 0.004
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_analyze import dominant_colors, hex_of, runs_from_profile  # noqa: E402


def modal(arr: np.ndarray) -> np.ndarray:
    flat = arr.reshape(-1, 3)
    keys = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2].astype(np.int32)
    vals, counts = np.unique(keys, return_counts=True)
    k = int(vals[np.argmax(counts)])
    return np.array([(k >> 16) & 0xFF, (k >> 8) & 0xFF, k & 0xFF], dtype=np.int16)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--region", required=True, help="x,y,w,h in CSS px")
    ap.add_argument("--min-frac", type=float, default=0.006, help="row/col ink fraction to count a line")
    ap.add_argument("--gap", type=int, default=3, help="px gap tolerated inside one line")
    ap.add_argument("--thresh", type=int, default=26)
    ap.add_argument("--inset", type=int, default=0, help="px trimmed from each edge of the region")
    ap.add_argument(
        "--mode",
        default="bg",
        choices=["bg", "white", "dark"],
        help="bg = differs from local modal colour; white/dark = luminance band (for gradient backgrounds)",
    )
    args = ap.parse_args()

    img = Image.open(args.png).convert("RGB")
    arr_full = np.asarray(img)
    x, y, w, h = (int(v) for v in args.region.split(","))
    px = (x * args.scale, y * args.scale, (x + w) * args.scale, (y + h) * args.scale)
    patch = arr_full[px[1] : px[3], px[0] : px[2]]
    if patch.size == 0:
        print("[error] empty region", file=sys.stderr)
        return 1

    bg = modal(patch)
    if args.mode == "white":
        lum = patch.astype(np.float32).mean(axis=2)
        mx = patch.max(axis=2).astype(np.float32)
        mn = patch.min(axis=2).astype(np.float32)
        sat = (mx - mn) / np.maximum(mx, 1)
        mask = (lum > 235) & (sat < 0.10)
    elif args.mode == "dark":
        lum = patch.astype(np.float32).mean(axis=2)
        mask = lum < 120
    else:
        d = np.abs(patch.astype(np.int16) - bg).sum(axis=2)
        mask = d > args.thresh

    if args.inset:
        i = args.inset * args.scale
        mask[:i, :] = False
        mask[-i:, :] = False
        mask[:, :i] = False
        mask[:, -i:] = False

    H, W = mask.shape

    print(f"[region] css {x},{y} {w}x{h}   src px {px}   local bg {hex_of(bg)}")

    rows = mask.mean(axis=1)
    bands = runs_from_profile(rows, args.min_frac, args.gap)
    print(f"[lines] {len(bands)}")
    for y0, y1 in bands:
        cy0, cy1 = y + y0 / args.scale, y + y1 / args.scale
        sub = mask[y0:y1]
        cols = sub.mean(axis=0)
        runs = runs_from_profile(cols, 0.004, args.gap)
        print(f"  y {cy0:8.2f} .. {cy1:8.2f}  (h {(cy1-cy0):6.2f})   runs={len(runs)}")
        for x0, x1 in runs:
            cx0, cx1 = x + x0 / args.scale, x + x1 / args.scale
            sub_patch = patch[y0:y1, x0:x1]
            dom = dominant_colors(sub_patch, n=2)
            share = dom[0]["share"] if dom else 0
            print(
                f"      x {cx0:8.2f} .. {cx1:8.2f}  (w {cx1-cx0:7.2f})  "
                f"fill {dom[0]['hex'] if dom else '-':9s} {share*100:5.1f}%  "
                f"next {(dom[1]['hex'] if len(dom)>1 else '-'):9s}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
