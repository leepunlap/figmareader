#!/usr/bin/env python3
"""
Find flat-colour regions in a 4x export and print their bounding boxes.

  python3 scripts/flat_regions.py source/lion/lion-08-chat-1.png
  python3 scripts/flat_regions.py source/lion/lion-08-chat-1.png --colour '#cfc5ff'
  python3 scripts/flat_regions.py source/lion/lion-08-chat-1.png --tol 6 --min-area 200
"""

from __future__ import annotations

import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def hexs(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_hex(s: str):
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.int32)


def components(mask: np.ndarray):
    """4-connected components; returns list of (x0,y0,x1,y1,area)."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y0 in range(h):
        row = mask[y0]
        for x0 in range(w):
            if not row[x0] or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            minx = maxx = x0
            miny = maxy = y0
            area = 0
            while stack:
                y, x = stack.pop()
                area += 1
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            out.append((minx, miny, maxx + 1, maxy + 1, area))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--colour", help="target hex colour")
    ap.add_argument("--tol", type=int, default=4, help="per-channel tolerance")
    ap.add_argument("--min-area", type=int, default=120, help="min area in 4x pixels")
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    a = np.asarray(Image.open(args.png).convert("RGB")).astype(np.int32)
    s = args.scale

    if args.colour:
        targets = [parse_hex(args.colour)]
    else:
        flat = a.reshape(-1, 3)
        keys = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
        uv, cnt = np.unique(keys, return_counts=True)
        order = np.argsort(cnt)[::-1]
        targets = []
        for i in order[: args.top]:
            v = int(uv[i])
            targets.append(np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255], dtype=np.int32))
            print(f"colour {hexs(targets[-1])}  {cnt[i]*100.0/len(keys):6.2f}%")

    for t in targets:
        mask = (np.abs(a - t).max(axis=2) <= args.tol)
        comps = components(mask)
        comps = [c for c in comps if c[4] >= args.min_area]
        comps.sort(key=lambda c: -c[4])
        print(f"\n== {hexs(t)} : {len(comps)} region(s) >= {args.min_area}px")
        for x0, y0, x1, y1, area in comps[: 25]:
            print(f"   x {x0/s:8.2f} .. {x1/s:8.2f} (w {(x1-x0)/s:7.2f})   "
                  f"y {y0/s:8.2f} .. {y1/s:8.2f} (h {(y1-y0)/s:7.2f})   area {area}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
