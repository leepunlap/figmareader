#!/usr/bin/env python3
"""
Compare the rendered screen with the Figma source, band by band.

For every horizontal band of content found in the SOURCE, this reports the
ink bounding box in the source and the best-matching ink bounding box in the
RENDER (searching a small window for the best alignment).  The deltas are
exactly the CSS nudges the page needs.

  python3 scripts/ink_compare.py lion-08
  python3 scripts/ink_compare.py lion-08 --rows 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402


def load2x(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    if im.width // 4 in (390, 402) and im.width % 4 == 0:
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    return np.asarray(im).astype(np.int32)


def ink_mask(a: np.ndarray, ref=None) -> np.ndarray:
    """Pixels that differ from the image's modal colour (or an explicit ref)."""
    if ref is None:
        flat = a.reshape(-1, 3)
        keys = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
        uv, cnt = np.unique(keys, return_counts=True)
        v = int(uv[np.argmax(cnt)])
        ref = np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255])
    return np.abs(a - ref).sum(axis=2) > 30


def bands(mask: np.ndarray, merge: int = 3):
    rows = mask.sum(axis=1)
    on = rows > 0
    out = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j + 1 < len(on) and (on[j + 1] or (j + 2 < len(on) and on[j + 1:j + 3].any())):
                j += 1
            out.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return out


def bbox(mask: np.ndarray, x0: int, x1: int):
    sub = mask[:, x0:x1]
    ys, xs = np.nonzero(sub)
    if not len(ys):
        return None
    return x0 + int(xs.min()), x0 + int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--rows", type=int, default=12, help="band height in css px")
    ap.add_argument("--win", type=int, default=14, help="alignment search radius")
    ap.add_argument("--y0", type=float, default=0, help="ignore content above this css y")
    ap.add_argument("--ref", help="hex reference colour for the ink test")
    args = ap.parse_args()
    ref = None
    if args.ref:
        h = args.ref.lstrip("#")
        ref = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.int32)

    spec = SCREENS[args.screen]
    render = load2x(Path("/tmp/figma-render") / (Path(spec["page"]).stem + ".png"))
    source = load2x(ROOT / spec["source"])
    if render.shape != source.shape:
        print("[error] size mismatch", render.shape, source.shape)
        return 1

    rm = ink_mask(render, ref)
    sm = ink_mask(source, ref)
    if ref is None:
        # use the modal colour of the sheet area so the header gradient
        # does not turn every row into "ink"
        sheet = source[int(150 * 2):]
        flat = sheet.reshape(-1, 3)
        keys = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
        uv, cnt = np.unique(keys, return_counts=True)
        v = int(uv[np.argmax(cnt)])
        bg = np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255])
        rm = ink_mask(render, bg)
        sm = ink_mask(source, bg)
    top = int(args.y0 * 2)
    rm[:top] = False
    sm[:top] = False

    print(f"{args.screen}: render {render.shape[1]}x{render.shape[0]} (2x)")
    print(f"{'source band':>16s}  {'source ink x':>18s}   {'render ink x':>18s}   "
          f"{'dx':>5s} {'dy':>5s}  score")
    for y0, y1 in bands(sm):
        sb = bbox(sm[y0:y1], 0, sm.shape[1])
        if sb is None:
            continue
        sx0, sx1, sy0, sy1 = sb
        sy0 += y0
        sy1 += y0
        if sy1 - sy0 < 3:
            continue
        # search the render for the best matching vertical band
        best = None
        for dy in range(-args.win, args.win + 1):
            ry0, ry1 = sy0 + dy, sy1 + dy
            if ry0 < 0 or ry1 > rm.shape[0]:
                continue
            rb = bbox(rm[:, sx0:sx1], 0, rm.shape[1])
            if rb is None:
                continue
            # score = overlap of the render's ink with the source's ink rows
            inter = int((rm[ry0:ry1, sx0:sx1] & sm[sy0:sy1, sx0:sx1]).sum())
            union = int((rm[ry0:ry1, sx0:sx1] | sm[sy0:sy1, sx0:sx1]).sum())
            score = inter / union if union else 0
            if best is None or score > best[0]:
                best = (score, dy, ry0, ry1)
        if best is None or best[0] < 0.05:
            continue
        score, dy, ry0, ry1 = best
        # horizontal offset of the render's ink in that band
        rx0, rx1, _, _ = bbox(rm[ry0:ry1], 0, rm.shape[1])
        if rx0 is None:
            continue
        print(f"  y {sy0/2:7.2f}..{sy1/2:7.2f}  "
              f"x {sx0/2:6.2f}..{sx1/2:7.2f}   "
              f"x {rx0/2:6.2f}..{rx1/2:7.2f}   "
              f"{(rx0-sx0)/2:+5.1f} {dy/2:+5.1f}  {score:5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
