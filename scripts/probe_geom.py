#!/usr/bin/env python3
"""Measure the layout of a v1 screen straight from its 4x export.

usage: probe_geom.py <slug> [--source source/v1raw/screens/<slug>.png]

Prints, in css pixels:
  * the white card rectangles (background #fff8f4, cards #fff + #ffe6d8 hairline)
  * the hero photo bottom and the gradient header band
  * every non-background image rectangle (photos, avatars, thumbs)
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(slug, source):
    names = [slug]
    for pre in ("v1-", "v73-"):
        if slug.startswith(pre):
            names.append(slug[len(pre):])
    path = source
    if path is None:
        for n in names:
            for d in ("source/v1raw/screens", "source/v1raw73/screens"):
                p = os.path.join(ROOT, d, f"{n}.png")
                if os.path.exists(p):
                    path = p
                    break
            if path:
                break
    if not path or not os.path.exists(path):
        raise SystemExit(f"no source for {slug}")
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    return a, im.size[0] // 4, im.size[1] // 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--source")
    args = ap.parse_args()

    a, W, H = load(args.slug, args.source)
    print(f"# {args.slug}  {W} x {H} css px")

    def row(y):
        return a[int(y * 4 + 2)]

    def col(x):
        return a[:, int(x * 4 + 2)]

    # ---- card rectangles -------------------------------------------------
    # a card row is white (255,255,255) over a wide span and the row above and
    # below it is the page background (255,248,244)
    bg = np.array([255, 248, 244])
    print("\n## white card bands")
    prev_white = None
    for y in range(0, H):
        r = row(y)
        frac = ((r[:, 0] > 250) & (r[:, 1] > 250) & (r[:, 2] > 248)).mean()
        white = frac > 0.6
        if white != prev_white:
            print(f"  y {y:5d}  {'CARD' if white else 'gap '}  white_frac {frac:.2f}")
            prev_white = white

    # ---- card horizontal extent ------------------------------------------
    print("\n## card x extent (one row inside each band)")
    y = 0
    bands = []
    prev_white = None
    for yy in range(0, H):
        r = row(yy)
        frac = ((r[:, 0] > 250) & (r[:, 1] > 250) & (r[:, 2] > 248)).mean()
        white = frac > 0.6
        if white != prev_white:
            bands.append((yy, white))
            prev_white = white
    for y0, white in bands:
        if not white:
            continue
        yy = y0 + 6
        r = row(yy)
        w = ((r[:, 0] > 250) & (r[:, 1] > 250) & (r[:, 2] > 248)).tolist()
        runs = []
        s = None
        for x, v in enumerate(w):
            if v and s is None:
                s = x
            elif not v and s is not None:
                runs.append((s / 4, (x - 1) / 4))
                s = None
        if s is not None:
            runs.append((s / 4, W))
        wide = [t for t in runs if t[1] - t[0] > 40]
        print(f"  band starting y {y0}: x {wide}")

    # ---- image rectangles -------------------------------------------------
    # an image rectangle is a run of rows where the colour at a given x keeps
    # changing -> use the local variance to find non-flat regions
    print("\n## column colour change map (x : rows where the colour changes)")
    for x in range(0, W, 1):
        c = col(x)
        d = np.abs(np.diff(c, axis=0)).sum(axis=1)
        # device rows -> css
        idx = np.nonzero(d > 18)[0]
        if len(idx) == 0:
            continue
        # group into css runs
        groups = []
        s = p = idx[0]
        for i in idx[1:]:
            if i - p > 8:
                groups.append((s, p))
                s = i
            p = i
        groups.append((s, p))
        print(f"  x {x:4d}: " + " ".join(f"{g[0]/4:.0f}-{g[1]/4:.0f}" for g in groups))


if __name__ == "__main__":
    sys.exit(main())
