#!/usr/bin/env python3
"""Show which font actually supplies a given character.

The per-page font subsets are embedded without a unicode-range, so the first
family in the stack that happens to carry a glyph wins it -- including the
fullwidth punctuation, where the "Latin" subset draws the narrow forms.

This renders one character in one family at a time and reports the ink box
it produced, so the caller can see the difference.

  python3 scripts/font_of.py "（" --families "Noto Sans TC Latin" "Noto Sans TC"
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/noto-latin.css">
<link rel="stylesheet" href="assets/v1/{fonts}">
<style>
 html,body {{ margin:0; padding:0; background:#fff; }}
 .row {{ position:absolute; left:10px; white-space:pre; margin:0;
        font-size:40px; line-height:1.4; color:#000; }}
</style></head>
<body>
{rows}
</body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--families", nargs="+", required=True)
    ap.add_argument("--fonts", default="competition-detail-closed-fonts.css")
    ap.add_argument("--weight", type=int, default=400)
    args = ap.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, fam in enumerate(args.families):
        rows.append('<p class="row" style="top:%dpx;font-family:\'%s\';font-weight:%d">%s</p>'
                    % (i * 60, fam, args.weight, args.text))
    page = WORK / "_fontof.html"
    page.write_text(PAGE.format(fonts=args.fonts, rows="\n".join(rows)), encoding="utf-8")
    out = WORK / "_fontof.png"
    if out.exists():
        out.unlink()
    profile = WORK / f"fontof-{__import__('os').getpid()}"
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check",
           "--allow-file-access-from-files", "--force-device-scale-factor=4",
           "--virtual-time-budget=10000", "--user-data-dir=%s" % profile,
           "--window-size=600,%d" % (60 * len(args.families) + 20),
           "--screenshot=%s" % out, "file://%s" % page]
    subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    shutil.rmtree(profile, ignore_errors=True)
    im = Image.open(out).convert("L")
    a = np.asarray(im)
    print("text %r  (render %s)" % (args.text, im.size))
    for i, fam in enumerate(args.families):
        y0 = i * 60 * 4
        y1 = y0 + 60 * 4
        band = a[y0:y1]
        cols = (band < 200).any(axis=0)
        xs = np.nonzero(cols)[0]
        if len(xs) == 0:
            print("  %-24s (no ink)" % fam)
            continue
        print("  %-24s ink x %.1f..%.1f  width %.1f css px"
              % (fam, xs.min() / 4, xs.max() / 4, (xs.max() - xs.min()) / 4))


if __name__ == "__main__":
    main()
