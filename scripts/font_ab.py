#!/usr/bin/env python3
"""A/B the typeface and rasterisation strategy of a text band.

Background
----------
The Figma exports were rendered at 4x and the comparison downscales them to the
2x render with LANCZOS.  Chrome rasterises text natively at the device scale
(2x here), so even a perfectly positioned, identically shaped glyph ends up
with different anti-aliasing -- and a different typeface differs in outline
too.

This tool renders one line of real source text in several variants and reports
the band diff against the export, after searching for the best vertical
offset.  That separates "wrong typeface" from "wrong rasterisation" from
"wrong position".

  python3 scripts/font_ab.py --slug v1-competition-detail-closed --lines 17,24
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

VARIANTS = {
    # name              font-family                    extra css
    "noto": ("'Noto Sans TC Latin','Noto Sans TC',sans-serif", ""),
    "noto-tc": ("'Noto Sans TC',sans-serif", ""),
    "pingfang": ("'PingFang SC','PingFang TC',sans-serif", ""),
    "pingfang-sc": ("'PingFang SC',sans-serif", ""),
    "noto-x2": ("'Noto Sans TC Latin','Noto Sans TC',sans-serif",
                "transform:scale(0.5);transform-origin:0 0;"),
    "pingfang-x2": ("'PingFang SC','PingFang TC',sans-serif",
                    "transform:scale(0.5);transform-origin:0 0;"),
}

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/noto-latin.css">
<link rel="stylesheet" href="assets/v1/{fonts}">
<style>
 html,body {{ margin:0; padding:0; background:#fff; }}
 #stage {{ position:relative; width:{w}px; height:{h}px; overflow:hidden; }}
 .ln {{ position:absolute; white-space:pre; margin:0; line-height:1;
        font-size:{fs}px; font-weight:{weight}; color:#000;
        font-family:{font}; {extra} }}
</style></head>
<body>
<div id="stage">
{lines}
</div>
</body></html>
"""


def render(page_html: Path, width: int, height: int, out: Path, scale: int = 2) -> None:
    profile = WORK / f"fab-profile-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=8000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://%s" % page_html,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    shutil.rmtree(profile, ignore_errors=True)


def band_diff(a: np.ndarray, b: np.ndarray, sy0: int, sy1: int,
              ty0: int, x0: int, x1: int) -> float:
    """Best vertically-aligned band diff (percent of pixels differing).

    `a` is the export (source of truth) and holds the line at sy0..sy1;
    `b` holds the candidate render with the line starting at ty0.
    """
    s = a[sy0 * 2:sy1 * 2, x0 * 2:x1 * 2]
    best = 1.0
    for dy in range(-12, 13):
        yy0 = ty0 * 2 + dy * 2
        yy1 = yy0 + s.shape[0]
        if yy0 < 0 or yy1 > b.shape[0]:
            continue
        r = b[yy0:yy1, x0 * 2:x1 * 2]
        d = (np.abs(s - r).sum(axis=2) > 24).mean()
        best = min(best, d)
    return best * 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--lines", required=True, help="comma separated OCR run indices")
    ap.add_argument("--variants", default="noto,noto-tc,pingfang,noto-x2,pingfang-x2")
    ap.add_argument("--fonts", default=None)
    args = ap.parse_args()

    fonts = args.fonts or f"{args.slug}-fonts.css"
    runs = json.load(open(ROOT / "analysis" / "ocr" / f"{args.slug}-fit.json"))
    idxs = [int(i) for i in args.lines.split(",")]

    src_path = ROOT / "source" / "v1raw" / "screens" / f"{args.slug.replace('v1-', '')}.png"
    if not src_path.exists():
        src_path = ROOT / "source" / "v1raw73" / "screens" / f"{args.slug}.png"
    src = Image.open(src_path).convert("RGB")
    sw, sh = src.size
    A = np.asarray(src.resize((sw // 2, sh // 2), Image.LANCZOS)).astype(int)

    css_w = sw // 4
    css_h = sh // 4
    WORK.mkdir(parents=True, exist_ok=True)

    for name in args.variants.split(","):
        font, extra = VARIANTS[name]
        # lay the lines out far apart, then compare each against its own band
        rows = []
        for k, i in enumerate(idxs):
            r = runs[i]
            f = r["fit"]
            rows.append((i, r, f, k))
        height = css_h
        lines_html = []
        for i, r, f, k in rows:
            lines_html.append(
                '  <p class="ln" style="left:0px;top:%dpx;font-size:%spx;'
                'font-weight:%s;%s">%s</p>' % (
                    k * 200, f.get("fs", 14), f.get("weight", 400),
                    ("transform:scale(0.5);transform-origin:0 0;" if name.endswith("-x2") else ""),
                    r["text"].replace("&", "&amp;").replace("<", "&lt;"),
                )
            )
        page = WORK / f"_fab_{name}.html"
        page.write_text(PAGE.format(w=css_w, h=height, fs=14, weight=400,
                                    font=font, extra=extra, fonts=fonts,
                                    lines="\n".join(lines_html)),
                        encoding="utf-8")
        out = WORK / f"_fab_{name}.png"
        render(page, css_w, height, out)
        if not out.exists():
            print("%-14s RENDER FAILED" % name)
            continue
        B = np.asarray(Image.open(out).convert("RGB")).astype(int)
        print("--- %s" % name)
        for i, r, f, k in rows:
            y0 = int(r["src_y0"]) - 3
            y1 = int(r["src_y1"]) + 3
            # the variant renders the line at top=k*200; compare there
            d = band_diff(A, B, y0, y1, k * 200, 0, css_w)
            print("   run %-3d %-30s band %5.2f%%" % (i, r["text"][:30], d))


if __name__ == "__main__":
    main()
