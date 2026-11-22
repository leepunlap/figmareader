#!/usr/bin/env python3
"""
Inventory of the exported v1.0 / v1.0-7.3 screens.

  python3 scripts/v1_inventory.py              # both pages
  python3 scripts/v1_inventory.py v1raw        # only the v1.0 page

The v1.0 page was exported as 188 top-level layers, 96 of which are real
phone screens (390 or 402 css px wide). The 7.3 page was exported as four big
sections; those are segmented into screens by scripts/v1_segment.py.

Prints a table plus the totals, and writes source/v1raw/manifest.json.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
Image.MAX_IMAGE_PIXELS = None

V1 = ROOT / "source/v1raw"
V73 = ROOT / "source/v1raw73"

SCREEN_WIDTHS = {1560: 390, 1608: 402}


def slugify(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z._-]+", "-", name).strip("-.")
    return re.sub(r"-{2,}", "-", s) or "screen"


def scan(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.png")):
        try:
            with Image.open(p) as im:
                w, h = im.size
        except Exception as exc:  # pragma: no cover - diagnostic only
            print(f"  !! {p.name}: {exc}")
            continue
        if w in SCREEN_WIDTHS:
            out.append({
                "file": p.name,
                "slug": slugify(p.stem),
                "px": [w, h],
                "css": [SCREEN_WIDTHS[w], h // 4],
            })
    return out


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"

    if which in ("all", "v1raw"):
        rows = scan(V1)
        print(f"== v1.0 page: {len(rows)} screens ==")
        for r in rows:
            print(f"  {r['slug'][:44]:46s} {r['css'][0]}x{r['css'][1]}")
        (V1 / "manifest.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    if which in ("all", "v1raw73"):
        rows = scan(V73)
        print(f"== v1.0 7.3 page: {len(rows)} screens ==")
        for r in rows:
            print(f"  {r['slug'][:44]:46s} {r['css'][0]}x{r['css'][1]}")
        (V73 / "manifest.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
