#!/usr/bin/env python3
"""Sweep a uniform vertical (and optional horizontal) shift of every text run.

Text runs are placed from the OCR ink box, but the subset font does not put
its ink at the same offset inside the line box as the export's typeface did,
so the whole page can end up a pixel or two high.  This nudges every text
element by the same amount and reports the resulting page diff, so the best
constant can be picked from evidence instead of guessed.

    python3 scripts/shiftsweep.py v1-competition-detail-closed
    python3 scripts/shiftsweep.py v1-competition-detail-closed --class cdc__t
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

P_RE = re.compile(r'<p\b[^>]*style="([^"]*)"[^>]*>')
TOP_RE = re.compile(r"(top:\s*)(-?[\d.]+)px")
LEFT_RE = re.compile(r"(left:\s*)(-?[\d.]+)px")


def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def prepare(page_html: str) -> Path:
    """Mirror scripts/render_check.py: copy into the work dir with a base href."""
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / page_html
    html = Path(page_html).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", '<head>\n<base href="file://%s/">' % ROOT, 1)
    out.write_text(html, encoding="utf-8")
    return out


def render(page: Path, width: int, height: int, out: Path) -> None:
    profile = WORK / f"shift-profile-{__import__('os').getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files", "--force-device-scale-factor=2",
        "--virtual-time-budget=10000", "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out, "file://%s" % page,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    shutil.rmtree(profile, ignore_errors=True)


def diff(render_png: Path, src_png: Path) -> float:
    a = Image.open(render_png).convert("RGB")
    b = Image.open(src_png).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    d = (np.abs(np.asarray(a).astype(int) - np.asarray(b).astype(int)).sum(axis=2) > 24)
    return d.mean() * 100


def shift_html(html: str, cls: str | None, dy: float, dx: float) -> str:
    """Shift every <p> that carries an inline left/top, keeping the tag intact."""
    tag_re = re.compile(r'<p\b[^>]*>')

    def repl(m: re.Match) -> str:
        tag = m.group(0)
        if cls and ('class="%s' % cls) not in tag:
            return tag
        sm = re.search(r'style="([^"]*)"', tag)
        if not sm:
            return tag
        style = sm.group(1)
        style = TOP_RE.sub(lambda t: "%s%.2fpx" % (t.group(1), float(t.group(2)) + dy), style)
        style = LEFT_RE.sub(lambda t: "%s%.2fpx" % (t.group(1), float(t.group(2)) + dx), style)
        return tag[:sm.start()] + 'style="%s"' % style + tag[sm.end():]

    return tag_re.sub(repl, html)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--class", dest="cls", default=None)
    ap.add_argument("--dx", type=float, default=0.0)
    ap.add_argument("--dys", default="-2,-1,0,1,2,3,4")
    args = ap.parse_args()

    slug = args.slug
    page = ROOT / f"{slug}.html"
    html = page.read_text(encoding="utf-8")
    src = source_png(slug)
    src_img = Image.open(src)
    w = src_img.size[0] // 4
    h = src_img.size[1] // 4

    backup = WORK / f"{slug}.shiftbackup.html"
    backup.write_text(html, encoding="utf-8")
    try:
        for dy in [float(v) for v in args.dys.split(",")]:
            page.write_text(shift_html(html, args.cls, dy, args.dx), encoding="utf-8")
            out = WORK / f"{slug}.png"
            if out.exists():
                out.unlink()
            render(prepare(str(page)), w, h, out)
            if not out.exists():
                print("dy %+5.1f  RENDER FAILED" % dy)
                continue
            print("dy %+5.1f  diff %6.2f%%" % (dy, diff(out, src)))
    finally:
        page.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
