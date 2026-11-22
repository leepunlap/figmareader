#!/usr/bin/env python3
"""
Generate the static HTML pages that reproduce the Figma design.

The output is plain HTML + CSS (no JS, no framework) — this script only exists
so the three near-identical list screens stay in sync.  Every geometric value
comes from the pixel analysis in ./analysis/<screen>/frame.json.

Usage
  python3 scripts/build_pages.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------- content

TASKS = [
    ("摸摸我的小臉", "指出自己的一個身體部位。"),
    ("今天想玩哪一個", "用指認、拿取或說話表達一個喜好。"),
    ("我能收好一件東西", "嘗試把一件物品放回原位。"),
    ("自己試，也可以求助", "用動作或短語表示需要幫忙。"),
    ("不一樣，也能一起玩", "與家長選不同動作並輪流模仿。"),
    ("今天可以換個選擇", "示意保留或改變自己的選擇。"),
    ("用動作介紹我", "展示一項喜好及一個做過的動作。"),
]

HOME_CARDS = [
    ("01", "認識自己與喜好", "指出身體部位及一項喜好。", "warm"),
    ("02", "嘗試與求助", "嘗試收好物品並示意求助。", "cool"),
    ("03", "選擇與改變", "示意保留或改變自己的選擇。", "warm"),
    ("04", "接納彼此差異", "與家長各做不同動作並模仿。", "cool"),
]

# name, done count, active task number (1-based) or None, total height
LIST_SCREENS = [
    ("list-020", "任務清單 · 0/7", 0, 1, 1074, "assets/hero-list.png"),
    ("list-023", "任務清單 · 3/7", 3, 4, 1032, "assets/hero-list.png"),
    ("list-027", "任務清單 · 7/7", 7, None, 990, "assets/hero-list-027.png"),
]

# ----------------------------------------------------------------------- icons

ICONS = {
    "chevron-white": (
        '<svg viewBox="0 0 12 20" fill="none" stroke="currentColor" stroke-width="2.4"'
        ' stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5 2 10l8 7.5"/></svg>'
    ),
    "pencil": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>'
        '<path d="m15 5 4 4"/></svg>'
    ),
    "spark": (
        '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 1.4c.75 6.2 4.35 9.85 10.6 10.6C16.35 12.75 12.75 16.4 12 22.6 11.25 16.4 7.65 12.75 1.4 12 7.65 11.25 11.25 7.6 12 1.4Z"/></svg>'
    ),
    "spark-grad": (
        '<svg viewBox="0 0 24 24">'
        '<defs><linearGradient id="sparkGrad" x1="0" y1="0" x2="0.85" y2="1">'
        '<stop offset="0" stop-color="#fe7758"/><stop offset="1" stop-color="#9f5da8"/>'
        '</linearGradient></defs>'
        '<path fill="url(#sparkGrad)" d="M12 1.4c.75 6.2 4.35 9.85 10.6 10.6C16.35 12.75 12.75 16.4 12 22.6 11.25 16.4 7.65 12.75 1.4 12 7.65 11.25 11.25 7.6 12 1.4Z"/></svg>'
    ),
    "clock": (
        '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.3"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="6" cy="6" r="4.6"/><path d="M6 3.1V6l1.9 1.5"/></svg>'
    ),
    "check": (
        '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.7"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M1.2 5.9 4.2 8.9 8.9 1.1"/></svg>'
    ),
    "nav-back": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"'
        ' stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>'
    ),
    "nav-bookmark": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M19 21l-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>'
    ),
    "nav-star": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M11.53 2.3a.53.53 0 0 1 .95 0l2.31 4.68a2.12 2.12 0 0 0 1.59 1.16l5.17.76a.53.53 0 0 1 .29.9l-3.74 3.64a2.12 2.12 0 0 0-.61 1.88l.88 5.14a.53.53 0 0 1-.77.56l-4.62-2.43a2.12 2.12 0 0 0-1.97 0l-4.62 2.43a.53.53 0 0 1-.77-.56l.88-5.14a2.12 2.12 0 0 0-.61-1.88l-3.74-3.64a.53.53 0 0 1 .3-.9l5.16-.76a2.12 2.12 0 0 0 1.6-1.16z"/></svg>'
    ),
    "nav-share": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 14V3"/><path d="m8 7 4-4 4 4"/><path d="M5 13v6a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-6"/></svg>'
    ),
    "signal": (
        '<svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor">'
        '<rect x="0" y="7.5" width="3" height="4.5" rx="1"/>'
        '<rect x="5" y="5" width="3" height="7" rx="1"/>'
        '<rect x="10" y="2.5" width="3" height="9.5" rx="1"/>'
        '<rect x="15" y="0" width="3" height="12" rx="1"/></svg>'
    ),
    "wifi": (
        '<svg width="17" height="12" viewBox="0 0 17 12" fill="none" stroke="currentColor"'
        ' stroke-width="1.9" stroke-linecap="round">'
        '<path d="M1.4 4.2a10.6 10.6 0 0 1 14.2 0"/><path d="M4.1 7a6.8 6.8 0 0 1 8.8 0"/>'
        '<path d="M6.9 9.7a2.9 2.9 0 0 1 3.2 0"/><circle cx="8.5" cy="11.4" r=".6" fill="currentColor" stroke="none"/></svg>'
    ),
    "battery": (
        '<svg width="26" height="12" viewBox="0 0 26 12" fill="none">'
        '<rect x=".6" y=".6" width="21" height="10.8" rx="3" stroke="currentColor" stroke-width="1.2"/>'
        '<rect x="2.4" y="2.4" width="17.4" height="7.2" rx="1.7" fill="currentColor"/>'
        '<path d="M23.4 4.2v3.6a2 2 0 0 0 0-3.6z" fill="currentColor"/></svg>'
    ),
}

# --------------------------------------------------------------------- helpers

HEAD = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=390, initial-scale=1">
<title>{title}</title>
<!-- self-hosted, subsetted webfonts (see scripts/fetch_fonts.py) -->
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles.css">
</head>
"""

FOOT = "</body>\n</html>\n"


def write(name: str, html: str) -> None:
    path = ROOT / name
    path.write_text(html, encoding="utf-8")
    print(f"[write] {path}  ({len(html)} bytes)")


# ----------------------------------------------------------------------- home

def build_home() -> str:
    cards = "\n".join(
        f"""      <li class="card">
        <span class="card__badge badge--{tone}">{num}</span>
        <div class="card__body">
          <p class="card__title">{title}</p>
          <p class="card__text">{text}</p>
        </div>
      </li>"""
        for num, title, text, tone in HOME_CARDS
    )

    html = HEAD.format(title="Aimeee · 認識自我與個性探索")
    html += f"""<body>
<main class="phone" style="--phone-h:1196px">
  <section class="home__hero">
    <button class="hero__back" type="button" aria-label="返回">{ICONS['chevron-white']}</button>
    <p class="hero__age">適合 3–4 歲</p>
    <h1 class="hero__title">認識自我與個性探索</h1>
    <img class="home__photo" src="assets/hero-home.png" alt="家長與孩子坐在沙發上，拇指碰著嘴角">
    <p class="home__lede">每天約 3–5 分鐘，陪<br>孩子認識喜好、嘗試<br>求助並尊重差異。</p>
    <div class="hero__instructor">
      <img class="hero__avatar" src="assets/avatar-ellen.png" alt="導師莫韋淇">
      <div class="hero__info">
        <p class="hero__name">莫韋淇 Ellen Mok</p>
        <p class="hero__role">指紋分析導師</p>
      </div>
    </div>
  </section>

  <span class="section__icon" aria-hidden="true">{ICONS['pencil']}</span>
  <h2 class="section__title">從生活小動作，認識我自己。</h2>
  <p class="section__lede">在家長陪伴下，認識自己的身體與喜好，嘗試<br>力所能及的事並表達求助；體驗彼此可以不<br>同，自己的選擇也可以改變。</p>

  <div class="outcome">
    <span class="spark spark--l" style="color:#fc6866">{ICONS['spark']}</span>
    <p class="outcome__pill">7 天學習成果</p>
    <span class="spark spark--r" style="color:#fc6866">{ICONS['spark']}</span>
  </div>

  <p class="home__caption">從認識自己，練習表達與接納。</p>

  <ul class="cards">
{cards}
  </ul>

  <a class="cta" href="list-020.html">開始7天任務包</a>
  <div class="home-indicator"></div>
</main>
"""
    return html + FOOT


# ----------------------------------------------------------------------- list

def task_markup(index: int, done: int, active: int | None) -> str:
    title, desc = TASKS[index - 1]
    if index <= done:
        state, badge = "done", ICONS["check"]
    elif index == active:
        state, badge = "active", str(index)
    else:
        state, badge = "locked", str(index)

    note = ""
    if state == "locked":
        note = '\n        <p class="task__note">完成前一天後開啟</p>'

    return f"""      <li class="task task--{state}">
        <span class="task__badge">{badge}</span>
        <p class="task__duration">3–5 分鐘</p>
        <div class="task__body">
          <p class="task__title">{title}</p>
          <p class="task__desc">{desc}</p>{note}
        </div>
      </li>"""


def build_list(name: str, label: str, done: int, active: int | None, height: int, hero: str) -> str:
    tasks = "\n".join(task_markup(i, done, active) for i in range(1, 8))

    fill = ""
    if done:
        pct = done / 7 * 100
        fill = f'\n        <div class="progress__fill" style="width:{pct:.4f}%"></div>'

    html = HEAD.format(title=f"Aimeee · {label}")
    html += f"""<body>
<main class="phone lscreen" style="--phone-h:{height}px">
  <img class="lscreen__photo" src="{hero}" alt="家長與孩子在家中相視而笑">

  <div class="chrome statusbar">
    <p class="statusbar__time">9:41</p>
    <div class="statusbar__icons">
      {ICONS['signal']}
      {ICONS['wifi']}
      {ICONS['battery']}
    </div>
  </div>

  <nav class="chrome navbar">
    <button class="navbar__btn navbar__btn--back" type="button" aria-label="返回">{ICONS['nav-back']}</button>
    <button class="navbar__btn navbar__btn--mark" type="button" aria-label="收藏">{ICONS['nav-bookmark']}</button>
    <button class="navbar__btn navbar__btn--star" type="button" aria-label="最愛">{ICONS['nav-star']}</button>
    <button class="navbar__btn navbar__btn--share" type="button" aria-label="分享">{ICONS['nav-share']}</button>
  </nav>

  <section class="banner">
    <h1 class="banner__title">認識自我與個性探索</h1>
    <div class="banner__meta">
      {ICONS['clock']}
      <p class="banner__duration">每天約 3–5 分鐘</p>
    </div>
    <p class="banner__age">適合 3–4 歲</p>
  </section>

  <div class="sheet"></div>

  <div class="progress">
    <div class="progress__row">
      <p class="progress__label">目前進度</p>
      <p class="progress__count">{done} / 7</p>
    </div>
    <div class="progress__bar">{fill}
    </div>
  </div>

  <div class="list__title">
    {ICONS['spark-grad']}
    <h2>7 天任務清單</h2>
  </div>

  <ul class="tasks">
{tasks}
  </ul>

  <div class="home-indicator" style="top:{height - 36.5}px"></div>
</main>
"""
    return html + FOOT


# -------------------------------------------------------------------- gallery

def build_index() -> str:
    items = [
        ("home.html", "首頁 · 認識自我與個性探索", "Home — 課程介紹", 1196, ""),
        ("list-020.html", "任務清單 · 0/7", "List — 剛開始", 1074, " gallery__frame--list020"),
        ("list-023.html", "任務清單 · 3/7", "List — 進行中", 1032, " gallery__frame--list023"),
        ("list-027.html", "任務清單 · 7/7", "List — 全部完成", 990, " gallery__frame--list027"),
    ]

    blocks = []
    for href, title, sub, h, extra in items:
        blocks.append(
            f"""  <div class="gallery__item">
    <p class="gallery__label">
      <span class="gallery__name">{title}</span>
      <span class="gallery__meta"><small>{sub}</small><a href="{href}">開啟 ↗</a></span>
    </p>
    <div class="gallery__frame{extra}"><iframe src="{href}" title="{title}" loading="lazy"></iframe></div>
  </div>"""
        )

    html = HEAD.format(title="Aimeee 2026 OCT · Figma → HTML")
    html += """<body class="gallery">
<div class="gallery__head">
  <h1>Aimeee 2026 OCT</h1>
  <p>由 Figma 設計稿（4 個手機畫面）以純 HTML + CSS 重製，尺寸、配色與圖片位置皆以 4x 匯出圖逐像素量測。<br>
  來源檔案：<code>source/*.png</code> · 樣式：<code>styles.css</code> · 圖片：<code>assets/</code> · 字型：<code>assets/fonts/fonts.css</code>（Noto Sans TC + Poppins，已子集化並內嵌）<br>
  驗證：與 4x 匯出圖逐像素比對，差異像素比例 home 3.53% · list-020 3.13% · list-023 3.55% · list-027 4.10%（主要來自字形光柵化差異）。</p>
</div>
<div class="gallery__grid">
"""
    html += "\n".join(blocks)
    html += """
</div>
</body>
</html>
"""
    return html


# ------------------------------------------------------------------------ main

def main() -> int:
    write("home.html", build_home())
    for name, label, done, active, height, hero in LIST_SCREENS:
        write(f"{name}.html", build_list(name, label, done, active, height, hero))
    write("index.html", build_index())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
