#!/usr/bin/env python3
"""Side-by-side source|render comparison.

usage: sbs.py <slug> [--scale 2] [--css-y TOP BOTTOM] [--css-x LEFT RIGHT]
                  [--out FILE] [--width N]

Source  = source/v1raw/screens/<slug>.png (4x)  or source/v1raw73/screens/<slug>.png
Render  = /tmp/figma-render/<slug>.png (render_check --keep output)
A magenta separator is drawn between the halves.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_source(slug):
    names = [slug]
    for pre in ("v1-", "v73-"):
        if slug.startswith(pre):
            names.append(slug[len(pre):])
    for n in names:
        for p in (f"source/v1raw/screens/{n}.png", f"source/v1raw73/screens/{n}.png"):
            if os.path.exists(os.path.join(ROOT, p)):
                return os.path.join(ROOT, p)
    raise SystemExit(f"no source for {slug}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--css-y", type=int, nargs=2)
    ap.add_argument("--css-x", type=int, nargs=2)
    ap.add_argument("--out")
    ap.add_argument("--width", type=int, default=420, help="width of each half")
    ap.add_argument("--zoom", type=int, default=1, help="extra magnification")
    args = ap.parse_args()

    src_path = find_source(args.slug)
    ren_path = f"/tmp/figma-render/{args.slug}.png"
    if not os.path.exists(ren_path):
        raise SystemExit(f"no render at {ren_path}; run render_check.py {args.slug} --keep")

    src = Image.open(src_path).convert("RGB")
    ren = Image.open(ren_path).convert("RGB")

    # normalise both to the render's pixel grid
    src = src.resize(ren.size, Image.LANCZOS)

    y0, y1 = 0, ren.size[1]
    x0, x1 = 0, ren.size[0]
    if args.css_y:
        y0, y1 = args.css_y[0] * args.scale, args.css_y[1] * args.scale
    if args.css_x:
        x0, x1 = args.css_x[0] * args.scale, args.css_x[1] * args.scale
    y0, y1 = max(0, y0), min(ren.size[1], y1)
    x0, x1 = max(0, x0), min(ren.size[0], x1)

    a = src.crop((x0, y0, x1, y1))
    b = ren.crop((x0, y0, x1, y1))
    gap = 8
    out = Image.new("RGB", (a.width + b.width + gap, a.height), (255, 0, 255))
    out.paste(a, (0, 0))
    out.paste(b, (a.width + gap, 0))

    w = args.width * args.zoom
    h = max(1, int(out.height * w / out.width))
    out = out.resize((w, h), Image.LANCZOS)
    dest = args.out or f"/tmp/sbs-{args.slug}.png"
    out.save(dest)
    print(dest, out.size)


if __name__ == "__main__":
    sys.exit(main())
