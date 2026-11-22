#!/usr/bin/env python3
"""
Layout measurement for the Lion chat screens (08 / 11).

Prints vertical content bands of a 4x export and, for each band, the x
extents of the ink.  Coordinates are CSS pixels.

  python3 scripts/chat_measure.py source/lion/lion-08-chat-1.png
  python3 scripts/chat_measure.py source/lion/lion-08-chat-1.png --bands
"""

from __future__ import annotations

import argparse

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def hexs(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--bands", action="store_true", help="only list vertical bands")
    ap.add_argument("--y0", type=float, default=0)
    ap.add_argument("--y1", type=float, default=None)
    ap.add_argument("--x0", type=float, default=0)
    ap.add_argument("--x1", type=float, default=None)
    args = ap.parse_args()

    a = np.asarray(Image.open(args.png).convert("RGB"))
    s = args.scale
    y1 = args.y1 if args.y1 is not None else a.shape[0] / s
    x1 = args.x1 if args.x1 is not None else a.shape[1] / s

    reg = a[int(args.y0 * s):int(y1 * s), int(args.x0 * s):int(x1 * s)]
    flat = reg.reshape(-1, 3)
    keys = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2]
    uv, cnt = np.unique(keys, return_counts=True)
    bg = int(uv[np.argmax(cnt)])
    bgv = np.array([(bg >> 16) & 255, (bg >> 8) & 255, bg & 255])
    print(f"background {hexs(bgv)}")

    # ink = pixels that differ noticeably from the local background
    ink = np.abs(reg.astype(np.int32) - bgv).sum(axis=2) > 26

    # vertical bands: rows containing ink
    rowink = ink.sum(axis=1)
    on = rowink > 0
    bands = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j + 1 < len(on) and (on[j + 1] or (j + 2 < len(on) and on[j + 1:j + 3].any())):
                j += 1
            bands.append((args.y0 + i / s, args.y0 + (j + 1) / s))
            i = j + 1
        else:
            i += 1

    for b0, b1 in bands:
        sub = ink[int((b0 - args.y0) * s):int((b1 - args.y0) * s)]
        cols = sub.sum(axis=0)
        # column runs of ink
        runs = []
        i = 0
        on2 = cols > 0
        while i < len(on2):
            if on2[i]:
                j = i
                while j + 1 < len(on2) and on2[j + 1]:
                    j += 1
                runs.append((args.x0 + i / s, args.x0 + (j + 1) / s))
                i = j + 1
            else:
                i += 1
        print(f"\ny {b0:8.2f} .. {b1:8.2f}  (h {b1-b0:6.2f})  {len(runs)} col run(s)")
        if args.bands:
            continue
        for c0, c1 in runs:
            print(f"    x {c0:8.2f} .. {c1:8.2f}  (w {c1-c0:7.2f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
