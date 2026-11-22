#!/usr/bin/env python3
"""
Measure the ink box of a text string rendered in candidate fonts / sizes.

  python3 scripts/font_probe.py --text "活動日期係2026年2月28日" \
      --family "Noto Sans TC" --family "PingFang TC" --size 14 --weight 400

Prints, per candidate, the ink width/height in css px plus the ink top offset
from the line box top, so a candidate can be compared with the source.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--family", action="append", default=[])
    ap.add_argument("--size", type=float, default=14)
    ap.add_argument("--weight", type=int, default=400)
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--bg", default="#ffffff")
    ap.add_argument("--link", action="store_true",
                    help="link the project's self-hosted font subsets")
    args = ap.parse_args()

    fams = args.family or ["Noto Sans TC"]
    rows = []
    html = ["<html><head><meta charset='utf-8'><style>",
            "body{margin:0;background:%s}" % args.bg]
    if args.link:
        for sheet in ("assets/fonts/fonts.css", "assets/lion/lion-11-fonts.css"):
            p = ROOT / sheet
            if p.exists():
                html.append("@import url('file://%s');" % p)
    for i, f in enumerate(fams):
        html.append(
            "span.f%d{position:absolute;left:0;top:%dpx;display:inline-block;"
            "white-space:pre;font-family:'%s';font-size:%gpx;font-weight:%d;"
            "line-height:1;color:#000;}" % (i, i * 60, f, args.size, args.weight)
        )
    html.append("</style></head><body>")
    for i, f in enumerate(fams):
        html.append("<span class='f%d'>%s</span>" % (i, args.text))
    html.append("</body></html>")

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "probe.html"
        p.write_text("".join(html), encoding="utf-8")
        prof = Path(td) / "prof"
        out = Path(td) / "probe.png"
        subprocess.run([
            CHROME, "--headless=new", f"--user-data-dir={prof}", "--no-sandbox",
            "--hide-scrollbars", "--force-device-scale-factor=%d" % args.scale,
            "--window-size=1200,400", f"--screenshot={out}", p.as_uri(),
        ], check=False, capture_output=True)
        if not out.exists():
            raise SystemExit("chrome failed to render")
        im = np.asarray(Image.open(out).convert("L")).astype(int)

    # each candidate is on its own row; measure each line box separately
    scale = args.scale
    for i, f in enumerate(fams):
        band = im[i * 60 * scale:(i + 1) * 60 * scale, :]
        dark = band < 128
        ys = np.nonzero(dark.any(axis=1))[0]
        xs = np.nonzero(dark.any(axis=0))[0]
        if not len(ys):
            rows.append((f, None))
            continue
        h = (ys[-1] - ys[0] + 1) / scale
        w = (xs[-1] - xs[0] + 1) / scale
        rows.append((f, (round(float(xs[0]) / scale, 2), round(float(xs[-1]) / scale, 2),
                         round(float(w), 2), round(float(h), 2))))

    for f, m in rows:
        if m is None:
            print(f"{f:34s} (no ink)")
        else:
            print(f"{f:34s} x {m[0]:7.2f} .. {m[1]:7.2f}   w={m[2]:6.2f}  h={m[3]:6.2f}")


if __name__ == "__main__":
    main()
