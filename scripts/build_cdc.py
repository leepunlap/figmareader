#!/usr/bin/env python3
"""Assemble v1-competition-detail-closed.html from the fitted OCR runs."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIT = os.path.join(ROOT, "analysis/ocr/v1-competition-detail-closed-fit.json")

runs = json.load(open(FIT))

# runs that are baked into a cropped image and must NOT be rendered as text
BAKED = set(range(0, 3)) | set(range(30, 46)) | {78} | set(range(91, 96))


texts = []

# The auto-fitter estimates the size from the OCR box width, which is skewed
# whenever the source sets fullwidth punctuation with extra advance.  Measuring
# the CJK advance (exactly 1 em in every weight) gives the real size, and the
# whole screen turns out to use only 12 / 14 / 16 / 18 / 22 px.
FS = {
    3: 22.0,    # 中國語文菁英計劃
    4: 14.0,    # 報名：4月18日…
    6: 14.0,    # 比賽：4月25日…
    8: 14.0,    # 香港薄扶林道102號
    9: 14.0,    # North Point，步行約8分鐘
    10: 16.0, 11: 16.0, 12: 16.0, 13: 16.0, 14: 16.0,      # tab strip
    15: 18.0,                                        # 比賽介紹
    16: 14.0,                                        # 活動內容
    26: 14.0, 27: 14.0, 28: 14.0,                    # chips
    46: 18.0, 47: 14.0,                              # 收費
    56: 18.0, 57: 14.0,                              # 日程表
    67: 18.0, 68: 14.0,                              # 參加須知
    75: 18.0, 76: 14.0, 77: 14.0,                    # 主辦方
    79: 18.0, 80: 16.0,                              # 嘉賓 / 睇更多
    85: 12.0, 86: 12.0, 87: 12.0, 88: 12.0,          # 校長
    89: 18.0, 90: 12.0,                              # 活動相冊
    96: 14.0, 97: 12.0,                              # 共6張 / 查看全部
}
for i in range(17, 26):
    FS[i] = 14.0      # card 1 body copy
for i in range(48, 56):
    FS[i] = 14.0      # 收費 body copy
for i in range(58, 67):
    FS[i] = 14.0      # 日程表 body copy
for i in range(69, 75):
    FS[i] = 14.0      # 參加須知 body copy
for i in range(81, 85):
    FS[i] = 14.0      # 王仁曼


def p(idx, extra_class="", extra_style=""):
    r = runs[idx]
    f = r["fit"]
    fs = FS.get(idx, f["fs"])
    # keep the source's ink box in place when the size changes
    left = f["left"]
    top = f["top"]
    if fs != f["fs"]:
        ratio = fs / f["fs"]
        left = r["src_x0"] - (r["src_x0"] - f["left"]) * ratio
        top = r["src_y0"] - (r["src_y0"] - f["top"]) * ratio
    style = (f"left:{round(left, 2)}px;top:{round(top, 2)}px;"
             f"font-size:{fs}px;color:{f['color']}")
    if f.get("weight", 400) != 400:
        style += f";font-weight:{f['weight']}"
    if extra_style:
        style += ";" + extra_style
    cls = "cdc__t" + (" " + extra_class if extra_class else "")
    return f'  <p class="{cls}" style="{style}">{r["text"]}</p>'


texts = []
# header
texts.append(p(3))
texts.append(p(4))
texts.append(p(5))
texts.append(p(6))
texts.append(p(7))
texts.append(p(8))
texts.append(p(9))
# tab strip
texts.append(p(10))
texts.append(p(11))
texts.append(p(12))
texts.append(p(13))
texts.append(p(14))
# card 1
for i in range(15, 29):
    texts.append(p(i))
# 油畫 / 書法 are one OCR run but two separate pills
texts.append('  <p class="cdc__t" style="left:228.08px;top:710.52px;'
              'font-size:14px;color:#ff884a;font-weight:600">油畫</p>')
texts.append('  <p class="cdc__t" style="left:276.08px;top:710.52px;'
              'font-size:14px;color:#ff884a;font-weight:600">書法</p>')
# cards 2..5
for i in range(46, 78):
    texts.append(p(i))
# card 6 (嘉賓)
for i in range(79, 89):
    texts.append(p(i))
# card 7 (活動相冊)
texts.append(p(89))
texts.append(p(90))
texts.append(p(96))
texts.append(p(97).replace(">查看全部，</p>", ">查看全部</p>"))

SOCI = ('<svg width="19.75" height="19.75" viewBox="0 0 20 20">'
        '<circle cx="10" cy="10" r="10" fill="#1877f2"/>'
        '<path d="M11.6 19v-7.2h2.5l.4-2.9h-2.9V7.1c0-.85.24-1.42 1.46-1.42h1.56V3.1A21 21 0 0 0 12.4 3C10.2 3 8.7 4.3 8.7 6.7v2.2H6.2v2.9h2.5v7.2z" fill="#fff"/></svg>')
IG = ('<svg width="19.75" height="19.75" viewBox="0 0 20 20">'
      '<defs><linearGradient id="cdig%s" x1="0" y1="1" x2="1" y2="0">'
      '<stop offset="0" stop-color="#ffdc7c"/><stop offset=".35" stop-color="#ff5f6d"/>'
      '<stop offset=".7" stop-color="#c531a5"/><stop offset="1" stop-color="#7b3ff2"/>'
      '</linearGradient></defs>'
      '<rect x="0" y="0" width="20" height="20" rx="5.5" fill="url(#cdig%s)"/>'
      '<rect x="4.2" y="4.2" width="11.6" height="11.6" rx="3.6" fill="none" stroke="#fff" stroke-width="1.5"/>'
      '<circle cx="10" cy="10" r="2.9" fill="none" stroke="#fff" stroke-width="1.5"/>'
      '<circle cx="14.2" cy="5.9" r="1.1" fill="#fff"/></svg>')
GL = ('<svg width="18.25" height="18.25" viewBox="0 0 18.25 18.25" fill="none" '
      'stroke="#8a94a6" stroke-width="1.1"><circle cx="9.125" cy="9.125" r="8.4"/>'
      '<ellipse cx="9.125" cy="9.125" rx="3.9" ry="8.4"/>'
      '<path d="M.9 6.3h16.45M.9 11.95h16.45"/></svg>')

CHEVRON = ('<svg class="cdc__chev cdc__chev--%s" viewBox="0 0 12 12" fill="none" '
           'stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M4.5 2.5 8 6l-3.5 3.5"></path></svg>')

html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=402, initial-scale=1">
<title>活動 · 比賽詳情 · 已結束</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/noto-latin.css">
<link rel="stylesheet" href="assets/v1/competition-detail-closed.css">
<link rel="stylesheet" href="assets/v1/competition-detail-closed-fonts.css">
</head>
<body>
<div class="v1 v1--cdc" style="width:402px;height:2714px">

  <!-- hero photo, status bar and the three round buttons are one bitmap ---- -->
  <div class="cdc__hero"><img src="assets/v1/competition-detail-closed-hero.png" alt="比賽場地"></div>

  <!-- gradient header ------------------------------------------------------ -->
  <div class="cdc__grad"></div>
  <svg class="cdc__clock cdc__clock--1" viewBox="0 0 20 20"><circle cx="10" cy="10" r="8.4" stroke-width="2"/><path d="M10 4.6V10l3.5 3.3" stroke-width="2" stroke-linecap="round"/></svg>
  <svg class="cdc__clock cdc__clock--2" viewBox="0 0 20 20"><circle cx="10" cy="10" r="8.4" stroke-width="2"/><path d="M10 4.6V10l3.5 3.3" stroke-width="2" stroke-linecap="round"/></svg>
  <svg class="cdc__pin" viewBox="0 0 18 21"><path d="M9 20.2s7-6.3 7-11.6A7 7 0 1 0 2 8.6c0 5.3 7 11.6 7 11.6Z" stroke-width="1.9" stroke-linejoin="round"/><circle cx="9" cy="8.5" r="2.5" stroke-width="1.7"/></svg>
  <div class="cdc__map"><img src="assets/v1/competition-detail-closed-map.png" alt=""></div>
  <div class="cdc__tabunderline"></div>

  <!-- card 1 : 比賽介紹 ---------------------------------------------------- -->
  <article class="cdc__card cdc__card--1">
    <div class="cdc__pill cdc__pill--1"></div>
    <div class="cdc__pill cdc__pill--2"></div>
    <div class="cdc__pill cdc__pill--3"></div>
    <div class="cdc__pill cdc__pill--4"></div>
    <div class="cdc__pill cdc__pill--5"></div>
    <div class="cdc__poster"><img src="assets/v1/competition-detail-closed-poster.png" alt="宣傳海報"></div>
  </article>

  <!-- cards 2..4 : 收費 / 日程表 / 參加須知 ---------------------------------- -->
  <article class="cdc__card cdc__card--2"></article>
  <article class="cdc__card cdc__card--3"></article>
  <article class="cdc__card cdc__card--4"></article>

  <!-- card 5 : 主辦方 ------------------------------------------------------- -->
  <article class="cdc__card cdc__card--5">
    <div class="cdc__org cdc__org--1"><img src="assets/v1/competition-detail-closed-org1.png" alt="主辦方"></div>
    <div class="cdc__org cdc__org--2"><img src="assets/v1/competition-detail-closed-org2.png" alt="主辦方"></div>
    <span class="cdc__soc cdc__soc--fb1">{SOCI}</span>
    <span class="cdc__soc cdc__soc--ig1">{IG % (1, 1)}</span>
    <span class="cdc__soc cdc__soc--gl1">{GL}</span>
    <span class="cdc__soc cdc__soc--fb2">{SOCI}</span>
    <span class="cdc__soc cdc__soc--ig2">{IG % (2, 2)}</span>
    <span class="cdc__soc cdc__soc--gl2">{GL}</span>
  </article>

  <!-- card 6 : 嘉賓 --------------------------------------------------------- -->
  <article class="cdc__card cdc__card--6">
    <div class="cdc__guest cdc__guest--1"><img src="assets/v1/competition-detail-closed-guest1.png" alt=""></div>
    <div class="cdc__guest cdc__guest--2"><img src="assets/v1/competition-detail-closed-guest2.png" alt=""></div>
    <div class="cdc__guest cdc__guest--3"><img src="assets/v1/competition-detail-closed-guest3.png" alt=""></div>
    <div class="cdc__guest cdc__guest--4"><img src="assets/v1/competition-detail-closed-guest4.png" alt=""></div>
    {CHEVRON % ("guest", "#6f87a4")}
  </article>

  <!-- card 7 : 活動相冊 ----------------------------------------------------- -->
  <article class="cdc__card cdc__card--7">
    <div class="cdc__album"><img src="assets/v1/competition-detail-closed-album.png" alt=""></div>
    <div class="cdc__countpill"></div>
    {CHEVRON % ("album", "#6f8198")}
  </article>

  <div class="cdc__homebar"></div>

{chr(10).join(texts)}
</div>
</body>
</html>
"""

out = os.path.join(ROOT, "v1-competition-detail-closed.html")
open(out, "w").write(html)
print(out, len(texts), "text runs")
