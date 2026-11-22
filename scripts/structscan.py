#!/usr/bin/env python3
"""
Find regions that differ too much to be text anti-aliasing.

A CJK glyph edge that Chrome rasterises slightly differently from Figma
costs a band about 15-35 % of its area.  A *structural* mistake -- a card
that was never rendered, a panel 3 px off, an image in the wrong place --
shows up as a band that is more than half wrong.  This tool renders every
screen into a private work directory and lists the bands that are far too
hot, so the layout bugs stand out from the text noise.

  python3 scripts/structscan.py                 # every screen
  python3 scripts/structscan.py v1-home v1-play # some screens
  python3 scripts/structscan.py --min 50        # only bands over 50 %
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/structscan")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import SCREENS, WIDTHS, HEIGHTS  # noqa: E402


def shoot(page: str, width: int, height: int, scale: int = 2) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    p2 = WORK / page
    p2.write_text(html, encoding="utf-8")
    out = WORK / page.replace(".html", ".png")
    if out.exists():
        out.unlink()
    profile = WORK / f"profile-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           "--allow-file-access-from-files",
           "--force-device-scale-factor=%d" % scale,
           "--virtual-time-budget=12000",
           "--user-data-dir=%s" % profile,
           "--window-size=%d,%d" % (width, height),
           "--screenshot=%s" % out,
           "file://%s" % p2]
    subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot for {page}")
    return out


def source_for(slug: str) -> Path:
    if slug in SCREENS:
        return ROOT / SCREENS[slug]["source"]
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--min", type=float, default=50.0,
                    help="report bands whose hot fraction is above this %%")
    ap.add_argument("--height", type=int, default=10,
                    help="smallest band height, in css px")
    args = ap.parse_args()

    pages = sorted([p.name for p in ROOT.glob("v1-*.html") if p.stem != "v1"] +
                    [p.name for p in ROOT.glob("v73-*.html")] +
                    [p.name for p in ROOT.glob("lion-*.html")])
    if args.slugs:
        pages = [p for p in pages if Path(p).stem in args.slugs]

    flagged = 0
    for page in pages:
        slug = Path(page).stem
        src_p = source_for(slug)
        if not src_p.exists():
            continue
        width = WIDTHS.get(slug, 390)
        height = HEIGHTS.get(slug, 844)
        try:
            ren_p = shoot(page, width, height)
        except SystemExit as exc:
            print(f"{slug}: {exc}")
            continue
        ren = Image.open(ren_p).convert("RGB")
        src = Image.open(src_p).convert("RGB").resize(ren.size, Image.LANCZOS)
        A = np.asarray(src).astype(int)
        B = np.asarray(ren).astype(int)
        mask = np.abs(A - B).sum(axis=2) > 24
        total = 100 * mask.mean()
        hot = mask.sum(axis=1)
        # a band is a run of rows whose hot fraction is above the threshold
        bands = []
        run_start = None
        for i, v in enumerate(hot):
            frac = 100.0 * v / mask.shape[1]
            if frac > args.min:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None and (i - run_start) // 2 >= args.height:
                    bands.append((run_start / 2, i / 2, 100 * hot[run_start:i].mean() / mask.shape[1]))
                run_start = None
        if run_start is not None and (len(hot) - run_start) // 2 >= args.height:
            bands.append((run_start / 2, len(hot) / 2, 100 * hot[run_start:].mean() / mask.shape[1]))
        if bands:
            flagged += 1
            print(f"{slug:34s} diff {total:5.2f}%  " +
                  "  ".join(f"y {a:.0f}-{b:.0f} ({c:.0f}%)" for a, b, c in bands))
    print(f"\n{flagged} screen(s) with bands above {args.min:.0f} %")


if __name__ == "__main__":
    main()
