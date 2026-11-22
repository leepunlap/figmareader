#!/usr/bin/env python3
"""
Find text lines where the source and the render drift apart.

The Figma text frames use U+3000 (ideographic space) in places where the
hand-written HTML used an ASCII space or nothing at all.  A missing
ideographic space shifts every following glyph by 14 px, which is why the
affected lines read 5-15 % too narrow in linesync.

This aligns the *ink run* boundaries of the source and the render for every
OCR line and reports the first point where the two drift apart by more
than --tol css px.

  python3 scripts/spacescan.py v1-competition-detail-open
  python3 scripts/spacescan.py v1-competition-detail-open --tol 1.5
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
WORK = Path(os.environ.get("SPACESCAN_WORK", "/tmp/spacescan"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import SCREENS, WIDTHS, HEIGHTS  # noqa: E402


def ocr_rows(slug: str):
    p = ROOT / "analysis/ocr" / f"{slug}.tsv"
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) < 5:
            continue
        try:
            rows.append((float(f[0]), float(f[1]), float(f[2]), float(f[3]), f[5] if len(f) > 5 else ""))
        except ValueError:
            continue
    return rows


def shoot(page: str, width: int, height: int) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    out = WORK / page
    out.write_text(html, encoding="utf-8")
    png = WORK / page.replace(".html", ".png")
    if png.exists():
        png.unlink()
    prof = WORK / f"profile-{os.getpid()}"
    shutil.rmtree(prof, ignore_errors=True)
    prof.mkdir(parents=True, exist_ok=True)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           "--allow-file-access-from-files", "--force-device-scale-factor=2",
           "--virtual-time-budget=12000", f"--user-data-dir={prof}",
           f"--window-size={width},{height}", f"--screenshot={png}",
           f"file://{out}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(prof, ignore_errors=True)
    return png


def runs(arr: np.ndarray, scale: int):
    """Ink column runs as (start, end) in css px, relative to the crop."""
    ink = (arr.sum(axis=2) < 500).sum(axis=0)
    out = []
    st = None
    for i, v in enumerate(ink):
        if v > 0 and st is None:
            st = i
        elif v == 0 and st is not None:
            out.append((st / scale, i / scale))
            st = None
    if st is not None:
        out.append((st / scale, len(ink) / scale))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--tol", type=float, default=1.5,
                    help="run-start drift that counts as a mismatch (css px)")
    args = ap.parse_args()

    slug = args.slug
    page = slug + ".html"
    w = WIDTHS.get(slug, 0)
    h = HEIGHTS.get(slug, 0)
    if not w:
        print("unknown screen", slug)
        return 1
    png = shoot(page, w, h)
    src_path = ROOT / ("source/v1raw73/screens/%s.png" % slug if slug.startswith("v73-")
                       else "source/v1raw/screens/%s.png" % slug[3:])
    src = Image.open(src_path).convert("RGB")
    ren = Image.open(png).convert("RGB")
    # bring the 4x source down to the 2x render scale
    src = src.resize((ren.size[0], ren.size[1]), Image.LANCZOS)

    print(f"[{slug}] {w} css wide, tol {args.tol} px")
    hits = 0
    for x1, y1, x2, y2, text in ocr_rows(slug):
        sy, ey = int(y1 * 2), max(int(y1 * 2) + 2, int(y2 * 2))
        rx = int(x1 * 2)
        rw = max(4, int((x2 - x1) * 2))
        if ey > src.size[1] or rx + rw > src.size[0] or ey > ren.size[1] or rx + rw > ren.size[0]:
            continue
        s = runs(np.asarray(src)[sy:ey, rx:rx + rw], 2)
        r = runs(np.asarray(ren)[sy:ey, rx:rx + rw], 2)
        if len(s) < 2 or len(r) < 2:
            continue
        # the ink box of the whole row is the robust comparison: run
        # boundaries shift with the raster, the first/last ink column do not
        s_start, s_end = s[0][0], s[-1][1]
        r_start, r_end = r[0][0], r[-1][1]
        d_start = s_start - r_start
        d_end = s_end - r_end
        if abs(d_start) <= args.tol and abs(d_end) <= args.tol:
            continue
        # the gap in the source just before the last run that starts the text
        gap = max((s[i][0] - s[i - 1][1] for i in range(1, len(s))
                   if s[i][0] - r_start > 2), default=0.0)
        print("  start %+.2f  end %+.2f px  src gap %.2f | %s"
              % (d_start, d_end, gap, text[:44]))
        hits += 1
    print("%d drifting line(s)" % hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
