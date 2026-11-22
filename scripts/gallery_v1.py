#!/usr/bin/env python3
"""
Generate the v1.0 gallery page (v1.html) from the screen manifest.

  python3 scripts/gallery_v1.py

Every v1 screen that has a built page (v1-<slug>.html) is listed with its
iframe, its Chinese design title and its measured diff % (read from
analysis/v1-diff.json, which scripts/measure_v1.py writes).

The page is regenerated after each batch, so it always matches what is built.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FAMILY_ORDER = [
    ("home", "首頁 · Home"),
    ("chat", "家教顧問 · Chat"),
    ("competition", "比賽 · Competitions"),
    ("play", "玩樂 · Play"),
    ("school", "學校 · Schools"),
    ("product", "積分商城 · Products"),
    ("order", "訂單 · Orders"),
    ("calendar", "日曆 · Calendar"),
    ("notification", "通知 · Notifications"),
    ("membership", "會員 · Membership"),
    ("search", "搜尋 · Search"),
    ("invite", "邀請 · Invites"),
    ("profile", "檔案 · Profile"),
]


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for folder in ("v1raw", "v1raw73"):
        m = ROOT / "source" / folder / "screens" / "manifest.json"
        if not m.exists():
            continue
        for row in json.loads(m.read_text(encoding="utf-8")):
            page_name = row.get("page") or f"v1-{row['slug']}.html"
            page = ROOT / page_name
            if not page.exists():
                continue
            row = dict(row)
            row["key"] = row.get("key") or f"v1-{row['slug']}"
            row["page"] = page_name
            row["folder"] = folder
            rows.append(row)
    return rows


def load_diffs() -> dict[str, float]:
    p = ROOT / "analysis/v1-diff.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def family_of(row: dict) -> str:
    slug = row["slug"]
    if slug.startswith("v73-"):
        # the 7.3 screens keep the family of the v1.0 screen they match
        fam = row.get("family")
        return fam if fam in dict(FAMILY_ORDER) else "v73"
    for key, _label in FAMILY_ORDER:
        if slug.startswith(key):
            return key
    return "other"


def main() -> int:
    rows = load_rows()
    diffs = load_diffs()
    if not rows:
        print("no built v1 screens yet")
        return 0

    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(family_of(r), []).append(r)

    labels = dict(FAMILY_ORDER)
    labels["other"] = "其他 · Other"
    labels["v73"] = "v1.0 最初版 (7.3)"

    parts = []
    for key, label in FAMILY_ORDER + [("v73", labels["v73"]), ("other", labels["other"])]:
        items = groups.get(key)
        if not items:
            continue
        cards = []
        for r in items:
            w, h = r["css"]
            pct = diffs.get(r["key"])
            meta = f"{w}×{h}"
            if pct is not None:
                meta += f" · {pct:.2f} %"
            cards.append(f"""
      <div class="g__item">
        <p class="g__label">
          <span class="g__name">{r['title']}</span>
          <span class="g__meta"><small>{r['slug']} — {meta}</small><a href="{r['page']}">開啟 ↗</a></span>
        </p>
        <div class="g__frame" style="--w:{w}px;--h:{h}px">
          <iframe src="{r['page']}" title="{r['title']}" loading="lazy"></iframe>
        </div>
      </div>""")
        parts.append(f"""
  <section class="g__section">
    <h2 class="g__title">{label}</h2>
    <p class="g__note">{len(items)} 個畫面</p>
    <div class="g__grid">{''.join(cards)}
    </div>
  </section>""")

    total = len(rows)
    built = sum(1 for r in rows if r["key"] in diffs)
    worst = max((diffs[r["key"]] for r in rows if r["key"] in diffs), default=None)
    best = min((diffs[r["key"]] for r in rows if r["key"] in diffs), default=None)
    stat = f"已量測 {built} / {total} 個畫面"
    if worst is not None:
        stat += f" · 差異 {best:.2f}–{worst:.2f} %"

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aimeee 2026 OCT · v1.0 對照</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles.css">
<style>
  body.gallery {{ padding-top: 24px; }}
  .g__section {{ max-width: 1500px; margin: 0 auto 56px; }}
  .g__title {{ font-size: 19px; margin: 0 0 4px; color: #f0ece9; font-weight: 700; }}
  .g__note {{ margin: 0 0 18px; font-size: 13px; color: #9c9490; }}
  .g__grid {{ display: flex; flex-wrap: wrap; gap: 26px 22px; }}
  .g__item {{ width: 300px; }}
  .g__label {{ display: flex; flex-direction: column; gap: 2px; margin: 0 0 8px; }}
  .g__name {{ font-size: 13px; color: #e6e0dd; font-weight: 600; }}
  .g__meta {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .g__meta small {{ font-size: 11px; color: #9c9490; font-weight: 400; }}
  .g__meta a {{ font-size: 12px; color: #ffb38a; text-decoration: none; }}
  .g__frame {{
    width: 300px; height: 640px; overflow: hidden; border-radius: 10px;
    border: 1px solid #2a2a33; background: #fff;
  }}
  .g__frame iframe {{ width: var(--w); height: var(--h); border: 0; display: block; }}
</style>
</head>
<body class="gallery">
<div class="gallery__head">
  <h1>Aimeee 2026 OCT · v1.0</h1>
  <p>Figma 的 <code>v1.0 最初版 - (7.3)</code> 與 <code>v1.0</code> 兩頁，以純 HTML + CSS 重製。<br>
  {stat}。<br>
  <a href="index.html">← 回到總覽</a> · <a href="compare-lion.html">Lion 對照頁 ↗</a></p>
</div>
{''.join(parts)}
</body>
</html>
"""
    out = ROOT / "v1.html"
    out.write_text(html, encoding="utf-8")
    print(f"[write] {out.name}  {total} screens, {built} measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
