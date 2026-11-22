#!/usr/bin/env python3
"""Sweep the font weight of a page's text and report the resulting diff.

The exports are drawn in PingFang SC, whose Regular is noticeably heavier
than Noto Sans TC Regular.  A body line that is 4 % lighter in ink still
produces hot pixels on every stroke, so the weight is worth tuning from
measurements rather than guessed.

    python3 scripts/weightsweep.py v1-competition-detail-closed --sel ".v1--cdc .cdc__t"
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


def prepare(page_html: Path) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / page_html.name
    html = page_html.read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", '<head>\n<base href="file://%s/">' % ROOT, 1)
    out.write_text(html, encoding="utf-8")
    return out


def render(page: Path, width: int, height: int, out: Path) -> None:
    profile = WORK / f"wprofile-{__import__('os').getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           "--allow-file-access-from-files", "--force-device-scale-factor=2",
           "--virtual-time-budget=12000", "--user-data-dir=%s" % profile,
           "--window-size=%d,%d" % (width, height),
           "--screenshot=%s" % out, "file://%s" % page]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    shutil.rmtree(profile, ignore_errors=True)


def diff(render_png: Path, src_png: Path) -> float:
    a = Image.open(render_png).convert("RGB")
    b = Image.open(src_png).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    d = (np.abs(np.asarray(a).astype(int) - np.asarray(b).astype(int)).sum(axis=2) > 24)
    return d.mean() * 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--css", required=True, help="per-screen css file to patch")
    ap.add_argument("--sel", required=True, help="selector whose weight is swept")
    ap.add_argument("--weights", default="400,450,500,600")
    ap.add_argument("--marker", default="__WEIGHT_SWEEP__")
    args = ap.parse_args()

    slug = args.slug
    page = ROOT / f"{slug}.html"
    css = ROOT / args.css
    html = page.read_text(encoding="utf-8")
    css_text = css.read_text(encoding="utf-8")
    src = ROOT / ("source/v1raw73/screens/%s.png" % slug if slug.startswith("v73-")
                  else "source/v1raw/screens/%s.png" % slug[3:])
    im = Image.open(src)
    w, h = im.size[0] // 4, im.size[1] // 4

    css_backup = css.read_text(encoding="utf-8")
    page_backup = page.read_text(encoding="utf-8")
    try:
        for weight in [int(v) for v in args.weights.split(",")]:
            page.write_text(html, encoding="utf-8")
            # inject the override into the rendered copy only, so an
            # interrupted run can never leave the stylesheet modified
            prep = prepare(page)
            extra = "<style>%s { font-weight: %d !important; }</style>\n</head>" % (args.sel, weight)
            prep.write_text(prep.read_text(encoding="utf-8").replace("</head>", extra),
                            encoding="utf-8")
            out = WORK / f"{slug}.png"
            if out.exists():
                out.unlink()
            render(prep, w, h, out)
            if not out.exists():
                print("weight %d  RENDER FAILED" % weight)
                continue
            print("weight %d  diff %6.2f%%" % (weight, diff(out, src)))
    finally:
        page.write_text(page_backup, encoding="utf-8")
        css.write_text(css_backup, encoding="utf-8")


if __name__ == "__main__":
    main()
