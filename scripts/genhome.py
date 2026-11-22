#!/usr/bin/env python3
"""
Generate the home screens from their fit file.

The home screens share one layout; only the images and the page height
change.  The text geometry comes from scripts/ocrfit.py, so the markup lives
here once.

    python3 scripts/genhome.py v1-home-1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width={width}, initial-scale=1">
<title>{slug3}</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/noto-latin.css">
<link rel="stylesheet" href="assets/v1/{slug3}.css">
<link rel="stylesheet" href="assets/v1/{slug3}-fonts.css">
</head>
<body>
<div class="v1 v1-{slug3}" style="width:{width}px;height:{height}px">

  <div class="{cls}__band"></div>
  <div class="{cls}__cream"></div>

  {time}
  <img class="{cls}__status-icons" src="assets/v1/{slug3}-status.png" alt="">

  <img class="{cls}__av1" src="assets/v1/{slug3}-av1.png" alt="">
  <img class="{cls}__av2" src="assets/v1/{slug3}-av2.png" alt="">

  <div class="{cls}__search"></div>
  <svg class="{cls}__search-icon" viewBox="0 0 17 17" fill="none" stroke="#6c85a2" stroke-width="1.6" stroke-linecap="round">
    <circle cx="7.2" cy="7.2" r="4.6"></circle>
    <path d="M10.9 10.9 15.4 15.4"></path>
  </svg>
  {search}

  {hello}
  <svg class="{cls}__hello-arrow" viewBox="0 0 8 14" fill="none" stroke="#7089a8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M1.6 1.6 6.4 7 1.6 12.4"></path>
  </svg>
  {sub}
  <svg class="{cls}__sub-arrow" viewBox="0 0 14 12" fill="none" stroke="#7089a8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M1 6h11M8.4 2.2 12.4 6l-4 3.8"></path>
  </svg>

  <img class="{cls}__icons1" src="assets/v1/{slug3}-icons1.png" alt="">
  <img class="{cls}__icons2" src="assets/v1/{slug3}-icons2.png" alt="">

  <img class="{cls}__vip" src="assets/v1/{slug3}-vip.png" alt="">
  <svg class="{cls}__vip-prev" viewBox="0 0 22 22">
    <circle cx="11" cy="11" r="11" fill="#ffffff"></circle>
    <circle cx="11" cy="11" r="9.6" fill="#e4eef0"></circle>
    <path d="M13 5.5 7.5 11 13 16.5" fill="none" stroke="#fe8a4d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></path>
  </svg>
  <svg class="{cls}__vip-next" viewBox="0 0 22 22">
    <circle cx="11" cy="11" r="11" fill="#ffffff"></circle>
    <circle cx="11" cy="11" r="9.6" fill="#e4eef0"></circle>
    <path d="M8.5 5.5 14 11 8.5 16.5" fill="none" stroke="#fe8a4d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></path>
  </svg>
{vip}

  <div class="{cls}__tabbar"></div>
  <img class="{cls}__mascot" src="assets/v1/{slug3}-mascot.png" alt="">
  <img class="{cls}__bubble" src="assets/v1/{slug3}-bubble.png" alt="">
{bottom}
</div>
</body>
</html>
"""

ICONS = ["機構", "課程", "活動", "比賽", "資源",
         "玩樂", "醫療", "學校", "測試", "工具"]
TABS = ["首頁", "發現", "任務", "我嘅"]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def main() -> int:
    slug = sys.argv[1]
    slug3 = slug[3:] if slug.startswith("v1-") else slug
    cls = "home1" if slug3 == "home-1" else "home2"
    width, height = 390, (930 if cls == "home1" else 1659)
    fit = json.loads((ROOT / "analysis/ocr" / f"{slug}-fit.json").read_text(encoding="utf-8"))
    by_text = {r["text"]: r for r in fit}

    def el(text, extra=""):
        r = by_text.get(text)
        if not r or not r.get("fit"):
            return ""
        f = r["fit"]
        w = f.get("weight", 400)
        wt = f"font-weight:{w};" if w != 400 else ""
        fam = "font-family:'Poppins',sans-serif;" if r.get("stack") == "poppins" else ""
        name = f"{cls}__t {extra}".strip()
        return (f'  <p class="{name}" style="left:{f["left"]}px;top:{f["top"]}px;'
                f'font-size:{f["fs"]}px;{wt}{fam}color:{f["color"]}">{esc(text)}</p>')

    def group(texts, extra=""):
        return "\n".join(t for t in (el(x, extra) for x in texts) if t)

    vip = group(["立即開通VIP，", "盡享24項教養法寶",
                 "更多專家資源，多孩家庭必備", "了解詳情"])
    bottom = "\n".join(filter(None, [
        el("AI 教練建議"),
        *group(ICONS).splitlines(),
        *group(TABS).splitlines(),
    ]))

    html = TEMPLATE.format(
        width=width, height=height, slug3=slug3, cls=cls,
        time=el("9:41", f"{cls}__time"),
        search=el("家庭狀態與行動導向", f"{cls}__search-text"),
        hello=el("Hello, Agnes", f"{cls}__hello"),
        sub=el("探索型×試錯型學習者", f"{cls}__sub"),
        vip=vip, bottom=bottom,
    )
    (ROOT / f"{slug}.html").write_text(html, encoding="utf-8")
    print(f"{slug}.html written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
