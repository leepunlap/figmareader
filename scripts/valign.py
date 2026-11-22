#!/usr/bin/env python3
"""
Compare the vertical ink placement of every OCR line, export vs render.

linesync.py reports the horizontal drift of a line.  This tool reports the
vertical one: for every OCR row it measures the ink bounding box inside the
same css rect in the export and in the render, and prints the difference of
the top and the bottom edge.

  * dy_top == dy_bottom  the line sits at the right height
  * dy_top != dy_bottom  the line has a different size, not a different place

  python3 scripts/valign.py v1-competition-detail-open
  python3 scripts/valign.py v1-competition-detail-open --min 1200 --max 1700
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
WORK = Path("/tmp/parent-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import WIDTHS, HEIGHTS  # noqa: E402


def prepare(page: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    out = WORK / page
    out.write_text(html, encoding="utf-8")
    return out


def shoot(page: str, height: int, width: int, scale: int = 2) -> Path:
    out = WORK / page.replace(".html", ".png")
    profile = WORK / f"profile-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           "--allow-file-access-from-files",
           "--force-device-scale-factor=%d" % scale,
           "--virtual-time-budget=12000",
           "--user-data-dir=%s" % profile,
           "--window-size=%d,%d" % (width, height),
           "--screenshot=%s" % out,
           "file://%s" % (WORK / page)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot: {res.stderr[-1200:]}")
    return out


def ink_box(arr: np.ndarray, scale: float, x0: float, y0: float,
            x1: float, y1: float, th: int = 150):
    ix0, iy0 = int(x0 * scale), int(y0 * scale)
    ix1, iy1 = int(x1 * scale), int(y1 * scale)
    reg = arr[iy0:iy1, ix0:ix1]
    if reg.size == 0:
        return None
    m = reg.min(axis=2) < th
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return (xs.min() / scale + x0, ys.min() / scale + y0,
            xs.max() / scale + x0, ys.max() / scale + y0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--min", type=float, default=0)
    ap.add_argument("--max", type=float, default=1e9)
    args = ap.parse_args()
    slug = args.slug

    if slug.startswith("v73-"):
        src_p = ROOT / "source/v1raw73/screens" / f"{slug}.png"
    else:
        src_p = ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"
    src_im = Image.open(src_p).convert("RGB")
    width = WIDTHS.get(slug, src_im.size[0] // 4)
    height = HEIGHTS.get(slug, src_im.size[1] // 4)

    prepare(f"{slug}.html")
    ren_p = shoot(f"{slug}.html", height, width)
    ren_im = Image.open(ren_p).convert("RGB")

    S = np.asarray(src_im).astype(int)
    R = np.asarray(ren_im).astype(int)
    ss = S.shape[1] / width
    rs = R.shape[1] / width

    tsv = ROOT / "analysis/ocr" / f"{slug}.tsv"
    print(f"[{slug}]  {width}x{height} css")
    print("   css y      srcTop  srcBot | renTop  renBot |  dTop  dBot   h(src) h(ren)")
    rows = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) < 6:
            continue
        x0, y0, x1, y1 = (float(v) for v in f[:4])
        text = f[5].strip()
        if y1 < args.min or y0 > args.max:
            continue
        a = ink_box(S, ss, x0, y0, x1, y1)
        b = ink_box(R, rs, x0, y0, x1, y1)
        if not a or not b:
            continue
        dt = b[1] - a[1]
        db = b[3] - a[3]
        rows.append((y0, dt, db, a[3] - a[1], b[3] - b[1], text))
        flag = "  <<<" if abs(dt) > 1.0 or abs(db) > 1.0 else ""
        print("  %8.1f  %7.2f %7.2f | %6.2f %6.2f | %5.2f %5.2f  %5.2f %5.2f  %s%s"
              % (y0, a[1], a[3], b[1], b[3], dt, db, a[3] - a[1], b[3] - b[1], text[:26], flag))
    if rows:
        dts = np.array([r[1] for r in rows])
        dbs = np.array([r[2] for r in rows])
        print("\n  dTop  mean %+.2f  median %+.2f  |  dBot mean %+.2f  median %+.2f"
              % (dts.mean(), np.median(dts), dbs.mean(), np.median(dbs)))


if __name__ == "__main__":
    main()
