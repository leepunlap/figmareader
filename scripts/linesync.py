#!/usr/bin/env python3
"""
Compare every OCR text line of a screen against the rendered page.

For each row of analysis/ocr/<screen>.tsv it measures the ink bounding box
in the Figma export and in the Chrome render inside the *same* css rect and
prints them side by side:

    text                          src_w  ren_w   ratio   html size   drift

`ratio` is the source width over the render width for the same text:

  * ratio  1.00  the line is right
  * ratio < 1.00  the render is too wide  -> font size too big, or the
    source used a narrower advance for one of the glyphs
  * ratio > 1.00  the render is too narrow -> text is missing characters
    (the OCR dropped them) or the font size is too small

`drift` is where the last glyph of the line ends, source versus render.  It
shows how far the line has slid sideways by the time it reaches its end.

  python3 scripts/linesync.py v1-competition-detail-open
  python3 scripts/linesync.py v1-competition-detail-open --min 1200 --max 1700
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
WORK = Path("/tmp/parent-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import SCREENS, WIDTHS, HEIGHTS  # noqa: E402

import re  # noqa: E402

FONT_RE = re.compile(r'font-size:([\d.]+)px')


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
    """Ink bounding box inside a css rect, in css px."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--min", type=float, default=0)
    ap.add_argument("--max", type=float, default=1e9)
    ap.add_argument("--pad", type=float, default=3.0)
    args = ap.parse_args()

    name = args.screen
    if name not in SCREENS:
        raise SystemExit(f"unknown screen {name}")
    spec = SCREENS[name]
    h, w = HEIGHTS[name], WIDTHS.get(name, 390)

    tsv = ROOT / "analysis/ocr" / f"{name}.tsv"
    if not tsv.exists():
        raise SystemExit(f"no OCR file {tsv}")
    rows = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 6:
            continue
        rows.append((float(p[0]), float(p[1]), float(p[2]), float(p[3]),
                     float(p[4]), p[5]))

    prepare(spec["page"])
    shot = shoot(spec["page"], h, w)
    src = np.asarray(Image.open(ROOT / spec["source"]).convert("RGB"))
    ren = np.asarray(Image.open(shot).convert("RGB"))

    # the html font sizes, keyed by the text they carry
    sizes: dict[str, list[float]] = {}
    for m in re.finditer(r'<p class="[^"]*" style="[^"]*font-size:([\d.]+)px[^"]*">(.*?)</p>',
                         (ROOT / spec["page"]).read_text(encoding="utf-8")):
        sizes.setdefault(m.group(2), []).append(float(m.group(1)))

    print(f"[{name}] {w}x{h} css")
    print(f"{'text':46s} {'src_w':>7s} {'ren_w':>7s} {'ratio':>6s} {'size':>6s} {'drift':>7s}")
    for x0, y0, x1, y1, conf, text in rows:
        if y0 < args.min or y0 > args.max:
            continue
        s = ink_box(src, 4, x0, y0, x1, y1)
        r = ink_box(ren, 2, x0, y0, x1, y1)
        if not s or not r:
            continue
        sw, rw = s[2] - s[0], r[2] - r[0]
        ratio = sw / rw if rw else 0
        drift = r[2] - s[2]
        size = sizes.get(text, [0])
        sz = size[0] if size else 0
        flag = "  <<<" if abs(ratio - 1) > 0.02 else ""
        print(f"{text[:44]:46s} {sw:7.2f} {rw:7.2f} {ratio:6.3f} {sz:6.2f} {drift:7.2f}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
