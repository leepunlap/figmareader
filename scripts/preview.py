#!/usr/bin/env python3
"""
Build contact sheets from the headless-Chrome renders.

  python3 scripts/preview.py

Writes:
  preview.png   4-up sheet of the RENDERED pages (the reproduction)
  compare.png   source (Figma export) vs render, per screen, with diff %
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCREENS = [
    ("home", "home.html", 1196),
    ("list-020", "list-020.html", 1074),
    ("list-023", "list-023.html", 1032),
    ("list-027", "list-027.html", 990),
]

BG = (16, 16, 20)
FG = (235, 235, 240)
DIM = (130, 130, 140)


def render_all() -> None:
    """Re-render every screen into WORK (renders/ are kept)."""
    WORK.mkdir(parents=True, exist_ok=True)
    for name, page, height in SCREENS:
        html = (ROOT / page).read_text(encoding="utf-8")
        html = html.replace("<body>", '<body class="render">')
        html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
        out = WORK / page
        out.write_text(html, encoding="utf-8")
        shot = WORK / f"{name}.png"
        cmd = [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-first-run", "--no-default-browser-check", "--disable-extensions",
            "--allow-file-access-from-files",
            "--force-device-scale-factor=2",
            "--virtual-time-budget=12000",
            f"--user-data-dir={WORK}/profile",
            f"--window-size=390,{height}",
            f"--screenshot={shot}",
            f"file://{out}",
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(f"[render] {name}")


def diff_pct(render: Image.Image, source: Image.Image) -> float:
    a = np.asarray(render).astype(np.int16)
    b = np.asarray(source).astype(np.int16)
    if a.shape != b.shape:
        b = np.asarray(source.resize(render.size, Image.LANCZOS)).astype(np.int16)
    d = np.abs(a - b).sum(axis=2)
    return float((d > 24).mean()) * 100


def label(draw: ImageDraw.ImageDraw, xy, text, fill, size=15):
    draw.text(xy, text, fill=fill, font=None)


def sheet(items, title, out_path, cell_w, pad=18, top=58, left=18):
    """items: list of (label, PIL.Image)"""
    imgs = [im for _, im in items]
    cols = len(items)
    scaled = [int(im.height * cell_w / im.width) for im in imgs]
    cell_h = max(scaled)
    W = left * 2 + cols * cell_w + (cols - 1) * pad
    H = top + cell_h + 46
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.text((left, 12), title, fill=FG)
    for i, ((lab, im), x) in enumerate(zip(items, range(cols))):
        px = left + i * (cell_w + pad)
        d.text((px, top - 22), lab, fill=DIM)
        canvas.paste(im.convert("RGB").resize((cell_w, scaled[i]), Image.LANCZOS), (px, top))
    canvas.save(out_path)
    print(f"[write] {out_path}  {canvas.size}")


def main() -> int:
    render_all()

    rendered = []
    compare_rows = []
    for name, _page, _h in SCREENS:
        r = Image.open(WORK / f"{name}.png").convert("RGB")
        s = Image.open(ROOT / f"source/{name}.png").convert("RGB")
        rendered.append((name.upper(), r))
        pct = diff_pct(r, s)
        compare_rows.append((f"{name}  source", s))
        compare_rows.append((f"{name}  render  ({pct:.2f}% diff)", r))

    sheet(rendered, "Aimeee 2026 OCT — HTML/CSS reproduction (rendered)", ROOT / "preview.png", cell_w=330)
    sheet(compare_rows, "Figma export vs. HTML/CSS render", ROOT / "compare.png", cell_w=210)
    shutil.rmtree(WORK / "profile", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
