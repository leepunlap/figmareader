#!/usr/bin/env python3
"""
Auto-tune the text of a screen: uniform font size per block, then align.

Two systematic defects come out of the auto-fit pipeline:

1. *Noisy font sizes.*  The fitter solves for the font size that makes each
   line's **ink width** match the export.  When the OCR text of a line is
   short (a dropped character, a missing space) the fitter compensates with
   a larger font size, so the glyphs of that line are the wrong size even
   though the line ends in the right place.  A text block in the design
   uses one size, so every line of a block is snapped to the block's
   median size.

2. *Vertical drift.*  A block can sit one or two pixels below the export.
   The best registration shift of the block is measured and applied.

Both fixes are verified by re-rendering; the tool prints the diff before
and after and only keeps the change when the page improves.

  python3 scripts/autotune.py v1-competition-detail-open
  python3 scripts/autotune.py v73-competition-01 --apply
  python3 scripts/autotune.py v1-home --no-sizes
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

LINE = re.compile(
    r'<(?P<tag>p|span|div)\b[^>]*\bstyle="(?P<style>[^"]*)"[^>]*>'
    r'(?P<text>[^<]*)</(?P=tag)>')


def prepare(page: str, text: str | None = None) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    if text is not None:
        html = text
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


def shift(img: Image.Image, dx: float, dy: float, scale: int = 2) -> Image.Image:
    if dx == 0 and dy == 0:
        return img
    return img.transform(img.size, Image.AFFINE,
                         (1, 0, -dx * scale, 0, 1, -dy * scale),
                         resample=Image.BICUBIC)


def best_band(src_img: Image.Image, ren_img: Image.Image, y0: int, y1: int,
              x0: int, x1: int, step: float = 0.5, reach: int = 3):
    pad = int(reach * 2) + 4
    sy0 = max(0, y0 * 2 - pad)
    sy1 = min(src_img.size[1], y1 * 2 + pad)
    sx0 = max(0, x0 * 2)
    sx1 = min(ren_img.size[0], x1 * 2)
    a = np.asarray(src_img.crop((sx0, sy0, sx1, sy1))).astype(int)
    by0, by1 = y0 * 2 - sy0, y1 * 2 - sy0
    best = (1.0, 0.0, 0.0)
    for dy in np.arange(-reach, reach + 0.001, step):
        for dx in np.arange(-reach, reach + 0.001, step):
            r = np.asarray(shift(ren_img.crop((sx0, sy0, sx1, sy1)), dx, dy)).astype(int)
            d = (np.abs(a[by0:by1] - r[by0:by1]).sum(axis=2) > 24).mean()
            if d < best[0]:
                best = (d, dx, dy)
    return best


def parse_lines(html: str):
    """Every element with an inline top and font-size."""
    out = []
    for m in LINE.finditer(html):
        st = m.group("style")
        t = re.search(r"top:([\d.]+)px", st)
        f = re.search(r"font-size:([\d.]+)px", st)
        if not t or not f:
            continue
        if not m.group("text").strip():
            continue
        out.append({"span": m.span(), "top": float(t.group(1)),
                    "size": float(f.group(1)), "text": m.group("text"),
                    "style": st})
    out.sort(key=lambda d: d["top"])
    return out


def blocks(lines, gap: float = 32.0):
    groups, cur = [], []
    for ln in lines:
        if cur and ln["top"] - cur[-1]["top"] > gap:
            groups.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        groups.append(cur)
    return groups


def rewrite(html: str, lines, size_map, shift_map) -> str:
    """Apply the new sizes / tops to the html, back to front."""
    for i in sorted(range(len(lines)), key=lambda i: lines[i]["span"][0], reverse=True):
        ln = lines[i]
        s, e = ln["span"]
        new_style = ln["style"]
        if i in size_map:
            new_style = re.sub(r"font-size:[\d.]+px",
                               "font-size:%gpx" % size_map[i], new_style)
        if i in shift_map:
            new_style = re.sub(r"top:[\d.]+px",
                               "top:%gpx" % shift_map[i], new_style)
        if new_style != ln["style"]:
            html = html[:s] + html[s:e].replace(ln["style"], new_style, 1) + html[e:]
    return html


def pick_size(sizes: list[float]) -> float:
    """The size the block really uses.

    The most common size in the block wins; when several sizes tie the one
    closest to the median is taken, so a block that is mostly 14 px does not
    get pulled to 13.8 px by two outliers.
    """
    cl: dict[float, int] = {}
    for s in sizes:
        cl[round(s, 1)] = cl.get(round(s, 1), 0) + 1
    med = sorted(sizes)[len(sizes) // 2]
    best = max(cl.items(), key=lambda kv: (kv[1], -abs(kv[0] - med)))
    return best[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-sizes", action="store_true")
    ap.add_argument("--no-shift", action="store_true")
    ap.add_argument("--gap", type=float, default=32.0)
    args = ap.parse_args()

    name = args.screen
    if name not in SCREENS:
        raise SystemExit(f"unknown screen {name}")
    spec = SCREENS[name]
    page = ROOT / spec["page"]
    html = page.read_text(encoding="utf-8")
    h, w = HEIGHTS[name], WIDTHS.get(name, 390)

    def render(text: str) -> tuple[float, Image.Image, Image.Image]:
        prepare(spec["page"], text)
        shot = shoot(spec["page"], h, w)
        ren = Image.open(shot).convert("RGB")
        src = Image.open(ROOT / spec["source"]).convert("RGB")
        if ren.size != src.size:
            src = src.resize(ren.size, Image.LANCZOS)
        d = (np.abs(np.asarray(src).astype(int)
                    - np.asarray(ren).astype(int)).sum(axis=2) > 24).mean() * 100
        return d, src, ren

    base, src, ren = render(html)
    print(f"[{name}] baseline {base:.2f}%")

    lines = parse_lines(html)
    groups = blocks(lines, args.gap)
    size_map: dict = {}
    shift_map: dict = {}

    if not args.no_sizes:
        for g in groups:
            if len(g) < 2:
                continue
            sizes = [d["size"] for d in g]
            if max(sizes) - min(sizes) <= 0.4:
                continue
            med = pick_size(sizes)
            for d in g:
                # leave real headings alone: only sizes close to the block's
                # own size are snapped to it
                if abs(d["size"] - med) > 0.4 and abs(d["size"] - med) < med * 0.2:
                    size_map[lines.index(d)] = round(med, 2)
        if size_map:
            html2 = rewrite(html, lines, size_map, {})
            d2, src, ren = render(html2)
            print(f"  uniform sizes: {base:.2f}% -> {d2:.2f}%  ({len(size_map)} lines)")
            if d2 < base:
                html, base = html2, d2
            else:
                size_map = {}

    if not args.no_shift:
        lines = parse_lines(html)
        groups = blocks(lines, args.gap)
        for g in groups:
            if len(g) < 1:
                continue
            y0 = max(0, int(min(d["top"] for d in g)) - 3)
            y1 = min(h, int(max(d["top"] for d in g) + 26))
            if y1 - y0 < 6:
                continue
            _, dx, dy = best_band(src, ren, y0, y1, 0, w)
            if abs(dy) >= 0.5 and abs(dx) < 0.5:
                for d in g:
                    shift_map[lines.index(d)] = round(d["top"] + dy, 2)
                print(f"  block y{y0}-{y1}: shift {dy:+.1f}")
        if shift_map:
            html2 = rewrite(html, lines, {}, shift_map)
            d2, src, ren = render(html2)
            print(f"  vertical align: {base:.2f}% -> {d2:.2f}%  ({len(shift_map)} lines)")
            if d2 < base:
                html, base = html2, d2
            else:
                shift_map = {}

    print(f"[{name}] result {base:.2f}%")
    if args.apply:
        page.write_text(html, encoding="utf-8")
        print("written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
