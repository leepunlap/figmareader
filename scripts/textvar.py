#!/usr/bin/env python3
"""Measure a page with the text of one element replaced.

The pixel diff can be driven by the *characters* in the HTML, not only by the
CSS.  OCR gives the ground truth for what a line says, but the OCR box does
not always include the spaces the source was drawn with, so a line can be
one character short and drift by a whole glyph.  This tool renders the page
with a candidate string substituted in and reports the page diff and the
hot fraction of one band, so the candidates can be compared directly.

  python3 scripts/textvar.py v73-competition2-02 \
      --band 631-651 --text "拉坯班（1.5小時）：適合9歲或以上兒童，學習" \
      --variant "拉坯班 （1.5小時）：適合 9 歲或以上兒童，學習"
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def render(html_text: str, slug: str, width: int, height: int, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    page = work / f"{slug}.html"
    png = work / f"{slug}.png"
    html_text = html_text.replace("<body>", '<body class="render">').replace(
        "<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    page.write_text(html_text, encoding="utf-8")
    if png.exists():
        png.unlink()
    prof = work / f"tv-{os.getpid()}"
    shutil.rmtree(prof, ignore_errors=True)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           "--allow-file-access-from-files", "--force-device-scale-factor=2",
           "--virtual-time-budget=12000", f"--user-data-dir={prof}",
           f"--window-size={width},{height}", f"--screenshot={png}",
           f"file://{page}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(prof, ignore_errors=True)
    if not png.exists():
        raise SystemExit("[error] chrome produced no screenshot")
    return png


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--band", default="", help="y0-y1 css px to score")
    ap.add_argument("--text", required=True, help="the string currently in the HTML")
    ap.add_argument("--variant", action="append", default=[],
                    help="candidate replacement (repeatable)")
    ap.add_argument("--work", default="/tmp/textvar")
    args = ap.parse_args()

    slug = args.slug
    sys.path.insert(0, str(ROOT / "scripts"))
    from render_check import WIDTHS, HEIGHTS
    w, h = WIDTHS[slug], HEIGHTS[slug]
    page = ROOT / f"{slug}.html"
    original = page.read_text(encoding="utf-8")
    if args.text not in original:
        print("[error] the --text string is not in the page")
        return 1

    src_path = ROOT / ("source/v1raw73/screens/%s.png" % slug if slug.startswith("v73-")
                       else "source/v1raw/screens/%s.png" % slug[3:])
    src_im = Image.open(src_path).convert("RGB")
    work = Path(args.work)

    def score(html_text: str):
        png = render(html_text, slug, w, h, work)
        ren = Image.open(png).convert("RGB")
        s = src_im.resize(ren.size, Image.LANCZOS)
        A = np.asarray(s).astype(int)
        R = np.asarray(ren).astype(int)
        page_pct = float((np.abs(A - R).sum(axis=2) > 24).mean() * 100)
        band_pct = None
        if args.band:
            y0, y1 = (int(v) for v in args.band.split("-"))
            box = (0, y0 * 2, ren.size[0], y1 * 2)
            a = A[box[1]:box[3], box[0]:box[2]]
            r = R[box[1]:box[3], box[0]:box[2]]
            band_pct = float((np.abs(a - r).sum(axis=2) > 24).mean() * 100)
        return page_pct, band_pct

    try:
        base_page, base_band = score(original)
        print("base          page %6.2f%%  band %s" % (
            base_page, "%.2f%%" % base_band if base_band is not None else "-"))
        for v in args.variant:
            p, b = score(original.replace(args.text, v))
            print("%-13s page %6.2f%%  band %s   (page %+.2f)" % (
                v[:13], p, "%.2f%%" % b if b is not None else "-", p - base_page))
    finally:
        page.write_text(original, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
