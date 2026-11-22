#!/usr/bin/env python3
"""How much of a screen's diff is misalignment rather than the text floor?

For every hot band the render is shifted by integer css pixels (no
resampling, so the comparison stays fair) and the band is re-scored.  A band
whose score drops a lot under some shift is a line that is off by that many
pixels; a band that does not move is already at the floor.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def source_png(slug):
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    if slug.startswith("v1-"):
        return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"
    raise SystemExit(
        f"[error] no 4x export known for {slug!r} (v1-* / v73-* only; the Lion\n"
        "        screens live under source/lion/ with their own names)"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("render_png")
    ap.add_argument("band_h", nargs="?", type=int, default=16)
    args = ap.parse_args()

    slug = args.slug
    render_png = args.render_png
    band_h = args.band_h
    src = source_png(slug)
    if not src.exists():
        raise SystemExit(f"[error] missing 4x export {src}")
    src4 = Image.open(src).convert("RGB")
    r = Image.open(render_png).convert("RGB")
    s = np.asarray(src4.resize((r.width, r.height), Image.LANCZOS)).astype(int)
    R = np.asarray(r).astype(int)
    d = np.abs(s - R).sum(axis=2) > 24
    H = d.shape[0]
    bh = band_h * 2
    print(f"{slug}: total {d.mean() * 100:.2f}%")
    print("band(y css)   hot%   best shift  after%   gain")
    rows = []
    for y in range(0, H - bh, bh):
        band = d[y:y + bh]
        hot = band.mean() * 100
        if hot < 12:
            continue
        best = None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                shifted = np.roll(np.roll(R, 2 * dy, axis=0), 2 * dx, axis=1)
                dd = np.abs(s[y:y + bh] - shifted[y:y + bh]).sum(axis=2) > 24
                v = dd.mean() * 100
                if best is None or v < best[0]:
                    best = (v, dx, dy)
        rows.append((hot, y / 2, best[1], best[2], best[0]))
    rows.sort(reverse=True)
    for hot, y, dx, dy, after in rows[:28]:
        gain = hot - after
        flag = "  <<<" if gain > 6 else ""
        print(f"  y {y:7.1f}  {hot:5.1f}%   dx {dx:+d} dy {dy:+d}   {after:5.1f}%  gain {gain:5.1f}{flag}")


if __name__ == "__main__":
    main()
