#!/usr/bin/env python3
"""
Build the "Lion" page comparison sheet + compare screen.

  python3 scripts/compare_lion.py

Writes (never touches the Tasks-page artefacts preview.png / compare.png):

  compare-lion.png    source (Figma 4x export) vs. render, one row per screen,
                      with the measured diff % on every row
  compare-lion.html   a static compare screen: for every Lion screen a live
                      HTML render (iframe) next to the Figma source image,
                      with the measured diff %

The renders come from scripts/render_check.py, so the numbers printed here are
exactly the ones the verification pipeline reports.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import HEIGHTS, SCREENS, WIDTHS  # noqa: E402

BG = (16, 16, 20)
FG = (235, 235, 240)
DIM = (130, 130, 140)
HOT = (255, 120, 90)
GAP = (120, 120, 130)

# PIL's built-in font has no CJK glyphs, so labels need a real face.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]


def font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()

# display name, source png, page html, css width, css height
LION = [
    ("lion-01", "活動 · 音樂",            "lion-01-activity-feed.png",           390, 874),
    ("lion-02", "活動 · 分類篩選",         "lion-02-activity-filter.png",         390, 874),
    ("lion-03", "課程 · 機構",            "lion-03-org-feed-a.png",              390, 848),
    ("lion-04", "活動 · 機構",            "lion-04-org-feed-b.png",              390, 848),
    ("lion-05", "機構 · 分類篩選",         "lion-05-org-filter.png",              390, 848),
    ("lion-06", "機構詳情 · 香港樂活獅子會", "lion-06-org-detail-lionsclub.png",    390, 1428),
    ("lion-07", "活動詳情 · Rosewood",    "lion-07-event-detail-rosewood.png",   402, 1918),
    ("lion-08", "家教顧問 · 對話 1",      "lion-08-chat-1.png",                  390, 928),
    ("lion-09", "機構詳情 · 香港新時代獅子會", "lion-09-org-detail-lionshk.png",     390, 1428),
    ("lion-10", "活動詳情 · 香港新時代獅子會", "lion-10-event-detail-lionshk.png",  402, 1918),
    ("lion-11", "家教顧問 · 對話 2",      "lion-11-chat-2.png",                  390, 928),
]


def render_all() -> None:
    """Render every Lion screen with the shared verification pipeline."""
    names = [n for n, _t, _s, _w, _h in LION]
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_check.py"), *names],
        cwd=ROOT, check=True,
    )


def diff_pct(render: Image.Image, source: Image.Image) -> float:
    a = np.asarray(render).astype(np.int16)
    b = np.asarray(source).astype(np.int16)
    if a.shape != b.shape:
        b = np.asarray(source.resize(render.size, Image.LANCZOS)).astype(np.int16)
    d = np.abs(a - b).sum(axis=2)
    return float((d > 24).mean()) * 100


def build_png(rows, out_path: Path) -> None:
    """rows: list of (label, source_img, render_img, pct)."""
    cell_w = 200
    pad = 14
    left = 20
    top = 84
    label_w = 250
    f_title = font(19)
    f_body = font(15)
    f_small = font(12)

    # every row is as tall as its own artboard needs
    row_hs = [
        int(min(s.height, r.height) * cell_w / s.width) + 30 for _l, s, r, _p in rows
    ]
    W = left * 2 + label_w + cell_w * 2 + pad
    H = top + sum(row_hs) + 24
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.text((left, 16), "Lion page — Figma 4x export vs. HTML/CSS render", fill=FG, font=f_title)
    d.text((left, 44), "source (left)  |  render (right)  —  measured diff %",
           fill=DIM, font=f_body)

    y = top
    for (label, src, ren, pct), row_h in zip(rows, row_hs):
        d.text((left, y + 4), label, fill=FG, font=f_body)
        d.text((left, y + 26), f"{pct:.2f} % diff",
               fill=HOT if pct > 6 else DIM, font=f_body)
        h = int(src.height * cell_w / src.width)
        sx = left + label_w
        canvas.paste(src.convert("RGB").resize((cell_w, h), Image.LANCZOS), (sx, y))
        rx = sx + cell_w + pad
        canvas.paste(ren.convert("RGB").resize((cell_w, h), Image.LANCZOS), (rx, y))
        d.text((sx, y + h + 6), "source", fill=DIM, font=f_small)
        d.text((rx, y + h + 6), "render", fill=DIM, font=f_small)
        y += row_h

    canvas.save(out_path)
    print(f"[write] {out_path}  {canvas.size}")


def build_sources() -> None:
    """Copy the 4x Figma exports down to 2x into assets/lion/compare/.

    The compare page must work from the delivered zip, which does not ship
    the 72 MB source/ tree — so the reference images travel with it, scaled
    to the same 2x grid the render is measured on.
    """
    out = ROOT / "assets/lion/compare"
    out.mkdir(parents=True, exist_ok=True)
    for key, _label, srcname, _w, _h in LION:
        src = Image.open(ROOT / "source/lion" / srcname).convert("RGB")
        dst = out / srcname
        if dst.exists() and dst.stat().st_mtime >= (ROOT / "source/lion" / srcname).stat().st_mtime:
            continue
        half = (src.width // 2, src.height // 2)
        src.resize(half, Image.LANCZOS).save(dst, optimize=True)
        print(f"[write] {dst}")


def build_html(rows, out_path: Path) -> None:
    """A static compare screen: live render (iframe) next to the source PNG."""
    parts = []
    for label, src, _ren, pct in rows:
        key = label.split()[0]
        page = f"{key}.html"
        srcname = next(s for k, _l, s, _w, _h in LION if k == key)
        w = next(x for k, _l, _s, x, _h in LION if k == key)
        h = next(x for k, _l, _s, _w, x in LION if k == key)
        cls = "hot" if pct > 6 else "ok"
        box_h = 760
        s = min(1.0, box_h / h)
        parts.append(f"""
    <section class="cmp" style="--w:{w}px;--h:{h}px;--s:{s:.4f}">
      <header class="cmp__head">
        <span class="cmp__name">{label}</span>
        <span class="cmp__pct {cls}">{pct:.2f} % diff</span>
        <a class="cmp__link" href="{page}">開啟 ↗</a>
      </header>
      <div class="cmp__pair">
        <figure class="cmp__cell">
          <div class="cmp__box"><img src="assets/lion/compare/{srcname}" alt="{label} — Figma 匯出圖"></div>
          <figcaption>Figma 匯出圖（4x）</figcaption>
        </figure>
        <figure class="cmp__cell">
          <div class="cmp__box"><iframe src="{page}" title="{label} — HTML render" loading="lazy"></iframe></div>
          <figcaption>HTML / CSS 重製（本頁實際渲染）</figcaption>
        </figure>
      </div>
    </section>""")

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aimeee 2026 OCT · Lion 對照</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 28px 24px 60px;
    background: #0f0f14; color: #ebebf0;
    font-family: "Noto Sans TC", "PingFang TC", system-ui, sans-serif;
  }}
  h1 {{ font-size: 22px; margin: 0 0 8px; font-weight: 700; }}
  .sub {{ margin: 0 0 34px; font-size: 13px; line-height: 1.7; color: #b9b2ae; }}
  .sub code {{ color: #ffb38a; }}
  .cmp {{ max-width: 1180px; margin: 0 auto 46px; }}
  .cmp__head {{ display: flex; align-items: baseline; gap: 14px; margin-bottom: 12px; }}
  .cmp__name {{ font-size: 16px; font-weight: 700; }}
  .cmp__pct {{ font-size: 13px; color: #8d8d98; }}
  .cmp__pct.hot {{ color: #ff8a6a; }}
  .cmp__link {{ margin-left: auto; font-size: 13px; color: #ffb38a; text-decoration: none; }}
  .cmp__pair {{ display: flex; gap: 18px; align-items: flex-start; flex-wrap: wrap; }}
  .cmp__cell {{ margin: 0; flex: 0 0 auto; }}
  /* Both columns show the same region: the artboard is scaled by --s so the
     whole screen fits a fixed box height, source and render alike. */
  .cmp__box {{
    width: calc(var(--w) * var(--s));
    height: calc(var(--h) * var(--s));
    overflow: hidden; border: 1px solid #2a2a33; border-radius: 8px; background: #fff;
  }}
  .cmp__box img, .cmp__box iframe {{
    display: block; width: var(--w); height: var(--h);
    transform: scale(var(--s)); transform-origin: top left;
    border: 0;
  }}
  .cmp__cell figcaption {{ margin-top: 7px; font-size: 11px; color: #8d8d98; }}
</style>
</head>
<body>
  <h1>Lion · 獅子會 — 對照</h1>
  <p class="sub">每個畫面左邊是 Figma 的 4x 匯出圖，右邊是本專案以純 HTML + CSS 重製後的實際渲染（iframe 內即為交付檔案）。差異比例由 <code>scripts/render_check.py</code> 以 2x 渲染逐像素量測，殘差主要來自字形光柵化（設計稿原字型無法由點陣圖還原）。<br>
  <a href="index.html" style="color:#ffb38a">← 回到總覽</a> · <a href="compare.png" style="color:#ffb38a">Tasks 頁對照圖 PNG</a></p>
{"".join(parts)}
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
    print(f"[write] {out_path}")


def main() -> int:
    render_all()
    rows = []
    for key, label, srcname, _w, _h in LION:
        spec = SCREENS[key]
        ren = Image.open(WORK / f"{key}.png").convert("RGB")
        src = Image.open(ROOT / spec["source"]).convert("RGB")
        if src.size != ren.size:
            src = src.resize(ren.size, Image.LANCZOS)
        rows.append((f"{key}  {label}", src, ren, diff_pct(ren, src)))
    build_png(rows, ROOT / "compare-lion.png")
    build_html(rows, ROOT / "compare-lion.html")
    build_sources()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
