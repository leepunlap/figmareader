#!/usr/bin/env python3
"""
Precise pixel probes against a 4x Figma export.

  # horizontal scan: find ink runs along a row
  python3 scripts/probe.py source/lion/x.png --row 200
  # vertical scan
  python3 scripts/probe.py source/lion/x.png --col 40
  # colour of a point
  python3 scripts/probe.py source/lion/x.png --at 40,200
  # print a colour grid of a small area
  python3 scripts/probe.py source/lion/x.png --grid 20,175,120,60

All coordinates are CSS pixels; the script works on the 4x raster.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def load(path: str, scale: int):
    a = np.asarray(Image.open(path).convert("RGB"))
    return a, scale


def hexs(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def runs(vals: np.ndarray, gap: int = 1):
    """Runs of 'ink' where the value differs from the modal colour."""
    flat = vals.reshape(-1, 3).astype(np.int32)
    keys = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    vals_, counts = np.unique(keys, return_counts=True)
    bg = vals_[counts.argmax()]
    bgv = np.array([(bg >> 16) & 255, (bg >> 8) & 255, bg & 255])
    diff = np.abs(flat - bgv).sum(axis=1)
    ink = diff > 24
    out = []
    i = 0
    n = len(ink)
    while i < n:
        if ink[i]:
            j = i
            while j + 1 < n and (ink[j + 1] or (j + 1 + gap < n and ink[j + 1:j + 1 + gap].any())):
                j += 1
            out.append((i, j + 1, hexs(flat[i])))
            i = j + 1
        else:
            i += 1
    return out, hexs(bgv)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--row", type=float, help="css y of a horizontal scan")
    ap.add_argument("--col", type=float, help="css x of a vertical scan")
    ap.add_argument("--at", help="css x,y of a single point")
    ap.add_argument("--grid", help="css x,y,w,h - print the colour histogram")
    ap.add_argument("--row-band", help="css x0,y0,x1,y1 - ink runs averaged over the band")
    args = ap.parse_args()

    a, s = load(args.png, args.scale)

    if args.at:
        x, y = (float(v) for v in args.at.split(","))
        px = a[int(y * s), int(x * s)]
        print(f"({x},{y}) = {hexs(px)}")
        return 0

    if args.row is not None:
        y = int(args.row * s)
        line = a[y]
        rs, bg = runs(line)
        print(f"row y={args.row}  bg={bg}")
        for x0, x1, c in rs:
            print(f"  x {x0/s:8.2f} .. {x1/s:8.2f}  (w {(x1-x0)/s:7.2f})  {c}")
        return 0

    if args.col is not None:
        x = int(args.col * s)
        col = a[:, x, :]
        rs, bg = runs(col)
        print(f"col x={args.col}  bg={bg}")
        for y0, y1, c in rs:
            print(f"  y {y0/s:8.2f} .. {y1/s:8.2f}  (h {(y1-y0)/s:7.2f})  {c}")
        return 0

    if args.grid:
        x0, y0, w, h = (float(v) for v in args.grid.split(","))
        reg = a[int(y0 * s):int((y0 + h) * s), int(x0 * s):int((x0 + w) * s)]
        flat = reg.reshape(-1, 3)
        keys = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2]
        uv, cnt = np.unique(keys, return_counts=True)
        order = np.argsort(cnt)[::-1][:10]
        for i in order:
            v = int(uv[i])
            print(f"  {hexs([(v>>16)&255,(v>>8)&255,v&255])}  {cnt[i]*100.0/len(keys):6.2f}%")
        return 0

    if args.row_band:
        x0, y0, x1, y1 = (float(v) for v in args.row_band.split(","))
        reg = a[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)]
        # column ink profile
        ink = (np.abs(reg.astype(np.int32) - 255).sum(axis=2) > 24)
        prof = ink.sum(axis=0)
        on = prof > max(1, reg.shape[0] * 0.05)
        out = []
        i = 0
        while i < len(on):
            if on[i]:
                j = i
                while j + 1 < len(on) and on[j + 1]:
                    j += 1
                out.append(((x0 + i / s), (x0 + (j + 1) / s)))
                i = j + 1
            else:
                i += 1
        print(f"col bands in {args.row_band} (ink > 5% of band height):")
        for a0, a1 in out:
            print(f"  x {a0:8.2f} .. {a1:8.2f}  (w {a1-a0:7.2f})")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
