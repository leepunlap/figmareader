#!/usr/bin/env python3
"""
Give the exported v1.0 screens ASCII filenames.

The Figma export uses the design's own Chinese layer names.  Those names are
the best description of each screen, so they are kept in the manifest and
translated into a readable ASCII slug for the file name.

  python3 scripts/v1_name.py v1raw
  python3 scripts/v1_name.py v1raw73

Writes source/v1raw/manifest.json with
    [{file, slug, title (中文), title_en, css:[w,h], px:[w,h]}]
and renames the PNGs to <slug>.png.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
Image.MAX_IMAGE_PIXELS = None

# longest terms first so a compound wins over its parts
TERMS: list[tuple[str, str]] = [
    ("SSVIP會員年費", "ssvip-membership-yearly"),
    ("SSVIP會員月費", "ssvip-membership-monthly"),
    ("SVIP會員年費", "svip-membership-yearly"),
    ("SVIP會員月費", "svip-membership-monthly"),
    ("VIP會員月費", "vip-membership-monthly"),
    ("VIP会员年費", "vip-membership-yearly"),
    ("次數用盡提醒-SVIP用戶", "quota-exhausted-ssvip"),
    ("次數用盡提醒-VIP用戶", "quota-exhausted-vip"),
    ("次數用盡提醒-免費用戶", "quota-exhausted-free"),
    ("档案数量上限-svip会员", "profile-limit-ssvip"),
    ("档案数量上限-vip会员", "profile-limit-vip"),
    ("档案数量上限-普通会员", "profile-limit-standard"),
    ("我的比賽-比賽證書-已领取", "my-competition-certificate-claimed"),
    ("我的比賽-比賽證書-待领取", "my-competition-certificate-pending"),
    ("我的比賽-比賽證書", "my-competition-certificate"),
    ("商品詳情-異常-商品已下架", "product-error-delisted"),
    ("商品詳情-異常-庫存不足", "product-error-out-of-stock"),
    ("商品詳情-異常-米星不足", "product-error-not-enough-stars"),
    ("商品詳情-異常-達到兌換上限", "product-error-limit-reached"),
    ("訂單詳情-憑證已核銷-1", "order-voucher-verified-1"),
    ("訂單詳情-憑證已核銷", "order-voucher-verified"),
    ("訂單詳情-憑證已過期-1", "order-voucher-expired-1"),
    ("訂單詳情-憑證已過期", "order-voucher-expired"),
    ("訂單詳情-正常", "order-normal"),
    ("商品詳情", "product-detail"),
    ("學校-校網篩選-1", "school-network-filter-1"),
    ("學校-校網篩選", "school-network-filter"),
    ("學校-榜單篩選", "school-ranking-filter"),
    ("學校-階段篩選", "school-stage-filter"),
    ("學校-地區篩選", "school-district-filter"),
    ("學校-自選篩選", "school-custom-filter"),
    ("學校-1", "school-1"),
    ("學校", "school"),
    ("玩樂-年齡篩選-1", "play-age-filter-1"),
    ("玩樂-年齡篩選", "play-age-filter"),
    ("玩樂-分類篩選", "play-category-filter"),
    ("玩樂-地區篩選", "play-district-filter"),
    ("玩樂-自選篩選", "play-custom-filter"),
    ("玩樂-無數據時", "play-empty-state"),
    ("玩樂活動詳情", "play-activity-detail"),
    ("玩樂", "play"),
    ("比賽-分類篩選", "competition-category-filter"),
    ("比賽-自選篩選", "competition-custom-filter"),
    ("比賽-空狀態", "competition-empty-state"),
    ("比賽-節假日", "competition-holiday"),
    ("比賽詳情-已結束", "competition-detail-ended"),
    ("比赛详情-報名中", "competition-detail-open"),
    ("比赛详情-已結束", "competition-detail-closed"),
    ("比賽-1", "competition-1"),
    ("比賽", "competition"),
    ("分享-比賽", "share-competition"),
    ("分享-玩樂", "share-play"),
    ("分享海報", "share-poster"),
    ("ai协议窗口", "ai-agreement-modal"),
    ("Chat-家庭資料完成度不足", "chat-incomplete-profile"),
    ("Chat-推薦任務包", "chat-recommended-task-pack"),
    ("Chat-答案已生成", "chat-answer-ready"),
    ("Chat-點贊反饋", "chat-like-feedback"),
    ("Chat-點踩反饋-1", "chat-dislike-feedback-1"),
    ("Chat-點踩反饋", "chat-dislike-feedback"),
    ("Chat-思考中", "chat-thinking"),
    ("全部日曆", "calendar-all"),
    ("日曆詳情-系統", "calendar-detail-system"),
    ("日曆詳情-自創", "calendar-detail-custom"),
    ("某天日程", "calendar-day-schedule"),
    ("自創日曆", "calendar-custom"),
    ("選擇月份", "calendar-pick-month"),
    ("我的收藏-內容失效狀態", "favourites-expired"),
    ("我的收藏-1", "favourites-1"),
    ("我的收藏", "favourites"),
    ("我的比賽-全部", "my-competition-all"),
    ("我的比賽-售後中", "my-competition-after-sales"),
    ("我的比賽-已失效", "my-competition-expired"),
    ("我的比賽-已完成", "my-competition-completed"),
    ("我的比賽-待使用", "my-competition-unused"),
    ("我的比賽", "my-competition"),
    ("我的米星-1", "my-stars-1"),
    ("我的米星", "my-stars"),
    ("會員紀錄", "membership-records"),
    ("積分商城", "points-mall"),
    ("邀請紀錄", "invite-records"),
    ("邀請-1", "invite-1"),
    ("邀請-2", "invite-2"),
    ("通知页面-1", "notifications-1"),
    ("通知页面-2", "notifications-2"),
    ("通知页面-3", "notifications-3"),
    ("通知页面", "notifications"),
    ("搜索結果展示", "search-results"),
    ("搜索", "search"),
    ("学校详情", "school-detail"),
    ("學校詳情", "school-detail"),
    ("首页-1", "home-1"),
    ("首页-2", "home-2"),
    ("首页", "home"),
    ("20选择ai-妈妈", "pick-ai-mum"),
    ("登录A", "login-a"),
    ("測試", "test"),
    ("测试-1", "test-1"),
]

SCREEN_WIDTHS = {1560: 390, 1608: 402}


def slug_for(name: str) -> str:
    for term, slug in TERMS:
        if name == term:
            return slug
    for term, slug in TERMS:
        if term in name:
            return slug
    ascii_name = re.sub(r"[^0-9A-Za-z]+", "-", name).strip("-").lower()
    return ascii_name or "screen"


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "v1raw"
    folder = ROOT / "source" / which
    out = folder / "screens"
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for p in sorted(folder.glob("*.png")):
        try:
            with Image.open(p) as im:
                w, h = im.size
        except Exception:
            continue
        if w not in SCREEN_WIDTHS:
            continue
        title = p.stem
        slug = slug_for(title)
        # keep the file names unique
        n = 2
        while (out / f"{slug}.png").exists():
            slug = f"{slug}-{n}"
            n += 1
        p.rename(out / f"{slug}.png")
        rows.append({
            "file": f"{slug}.png",
            "slug": slug,
            "title": title,
            "css": [SCREEN_WIDTHS[w], h // 4],
            "px": [w, h],
        })

    (out / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(rows)} screens -> {out}")
    for r in rows:
        print(f"  {r['slug'][:40]:42s} {r['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
