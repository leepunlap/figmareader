#!/usr/bin/env python3
"""
Build a side-by-side comparison of a rendered screen and its Figma source.

Both images are normalised to the same size first (the source is 4x, the
render 2x), so the comparison is 1:1.

  python3 scripts/compare.py lion-08
  python3 scripts/compare.py lion-08 --y0 140 --y1 400 --scale 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--y0", type=float, default=0)
    ap.add_argument("--y1", type=float, default=None)
    ap.add_argument("--x0", type=float, default=0)
    ap.add_argument("--x1", type=float, default=None)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    spec = SCREENS[args.screen]
    render = Image.open(Path("/tmp/figma-render") / (Path(spec["page"]).stem + ".png")).convert("RGB")
    source = Image.open(ROOT / spec["source"]).convert("RGB")
    if source.size != render.size:
        source = source.resize(render.size, Image.LANCZOS)

    w, h = render.size
    y1 = args.y1 if args.y1 is not None else h / 2
    x1 = args.x1 if args.x1 is not None else w / 2
    box = (int(args.x0 * 2), int(args.y0 * 2), int(x1 * 2), int(y1 * 2))
    rc = render.crop(box)
    sc = source.crop(box)

    gap = 16
    out = Image.new("RGB", (rc.width * 2 + gap, rc.height), (120, 120, 130))
    out.paste(sc, (0, 0))
    out.paste(rc, (rc.width + gap, 0))
    if args.scale != 1.0:
        out = out.resize((int(out.width * args.scale), int(out.height * args.scale)),
                         Image.LANCZOS)
    path = args.out or f"/tmp/cmp-{args.screen}.png"
    out.save(path)
    print(path, out.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
