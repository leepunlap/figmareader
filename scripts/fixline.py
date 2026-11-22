#!/usr/bin/env python3
"""
Repair an OCR text line and re-fit its font size.

The Vision OCR sometimes drops a trailing character or reads a similar
looking character wrong.  The fitter then solves for the font size that
makes the *line width* match the export, so a short line ends up with a
font size that is too big and every glyph in it drifts.

This tool rewrites the text of a line, renders the page, measures the new
ink width against the export and rescales the font size so the width
matches again.

  python3 scripts/fixline.py v1-competition-detail-open \
      "手捏創作班（1.5小時）：使用泥版、手揑、黏貼=手捏創作班（1.5小時）：使用泥版、手捏、黏貼的"
  python3 scripts/fixline.py v1-competition-detail-open --drop "！•延1丁子件土咫子白"
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
from render_check import SCREENS, WIDTHS, HEIGHTS  # noqa: E402


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
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=12000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://%s" % (WORK / page),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot: {res.stderr[-1200:]}")
    return out


def ink_box(arr: np.ndarray, scale: int, x0: float, y0: float,
            x1: float, y1: float, th: int = 150):
    ix0, iy0 = int(x0 * scale), int(y0 * scale)
    ix1, iy1 = int(x1 * scale), int(y1 * scale)
    if ix1 <= ix0 or iy1 <= iy0:
        return None
    reg = arr[iy0:iy1, ix0:ix1]
    m = reg.min(axis=2) < th
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return (x0 + xs.min() / scale, y0 + ys.min() / scale,
            x0 + xs.max() / scale, y0 + ys.max() / scale)


def ocr_rows(screen: str):
    tsv = ROOT / "analysis/ocr" / f"{screen}.tsv"
    rows = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) >= 6:
            rows.append((float(p[0]), float(p[1]), float(p[2]), float(p[3]), p[5]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("pairs", nargs="*", help="old=new")
    ap.add_argument("--drop", action="append", default=[],
                    help="remove every <p> whose text contains this")
    ap.add_argument("--no-refit", action="store_true")
    args = ap.parse_args()

    name = args.screen
    spec = SCREENS[name]
    page = ROOT / spec["page"]
    html = page.read_text(encoding="utf-8")
    rows = ocr_rows(name)

    # ---- 1. rewrite the text -----------------------------------------
    changed = []
    for pair in args.pairs:
        old, new = pair.split("=", 1)
        if old not in html:
            print(f"[warn] text not found: {old[:30]}")
            continue
        html = html.replace(f">{old}</p>", f">{new}</p>")
        changed.append((old, new))
    for frag in args.drop:
        html = re.sub(r'\n\s*<p class="[^"]*" style="[^"]*">[^<]*'
                      + re.escape(frag) + r'[^<]*</p>', "", html)
    page.write_text(html, encoding="utf-8")

    if not changed or args.no_refit:
        print("text patched")
        return 0

    # ---- 2. render and measure the changed lines ----------------------
    h, w = HEIGHTS[name], WIDTHS.get(name, 390)
    prepare(spec["page"])
    shot = shoot(spec["page"], h, w)
    src = np.asarray(Image.open(ROOT / spec["source"]).convert("RGB"))
    ren = np.asarray(Image.open(shot).convert("RGB"))

    for old, new in changed:
        row = next((r for r in rows if r[4] == old), None)
        if row is None:
            print(f"[warn] no OCR row for {old[:24]}")
            continue
        x0, y0, x1, y1, _ = row
        s = ink_box(src, 4, x0, y0, x1, y1)
        # the repaired text can be longer than the OCR box, so the render is
        # measured over a wider window; the source keeps its own box
        r = ink_box(ren, 2, x0 - 4, y0, x1 + 60, y1)
        if not s or not r:
            print(f"[warn] no ink for {old[:24]}")
            continue
        sw = s[2] - s[0]
        rw = r[2] - r[0]
        m = re.search(r'([^<>]*' + re.escape(new) + r')</p>', html)
        if not m:
            continue
        # the font-size that belongs to this exact line
        before = html[:m.start()]
        sizes = re.findall(r'font-size:([\d.]+)px', before)
        size = float(sizes[-1]) if sizes else 14.0
        factor = sw / rw if rw else 1.0
        new_size = round(size * factor, 2)
        # rewrite only that line's font-size
        tail = html[m.start():]
        tail2 = re.sub(r'font-size:[\d.]+px', f'font-size:{new_size}px', tail, count=1)
        html = before + tail2
        print(f"{old[:22]:24s} size {size:5.2f} -> {new_size:5.2f}  "
              f"(src {sw:.2f} ren {rw:.2f} ratio {factor:.4f})")

    page.write_text(html, encoding="utf-8")
    print("patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
