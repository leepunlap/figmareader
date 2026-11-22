#!/usr/bin/env python3
"""
Find CSS classes that the page uses but no stylesheet defines.

A page's markup is written by hand, so a class can easily drift away from
the selector the stylesheet expects - the element then falls back to the
default flow position instead of the measured one, which shows up as a
structural difference in the pixel diff.

  python3 scripts/orphan_classes.py
  python3 scripts/orphan_classes.py v1-favourites-expired v1-home
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASS_RE = re.compile(r'class="([^"]+)"')
LINK_RE = re.compile(r'<link[^>]+href="([^"]+\.css)"')
RULE_RE = re.compile(r'\.([A-Za-z0-9_-]+)')


def css_files(page: str) -> list[Path]:
    html = (ROOT / page).read_text(encoding="utf-8")
    out = []
    for href in LINK_RE.findall(html):
        p = ROOT / href
        if p.exists():
            out.append(p)
    return out


def main() -> int:
    pages = sys.argv[1:] or sorted(
        p.name for p in ROOT.glob("v1-*.html")) + sorted(
        p.name for p in ROOT.glob("v73-*.html"))
    bad = 0
    for page in pages:
        html = (ROOT / page).read_text(encoding="utf-8")
        body = html.split("</head>", 1)[-1]
        used = set()
        for group in CLASS_RE.findall(body):
            used.update(group.split())
        defined = set()
        for css in css_files(page):
            defined.update(RULE_RE.findall(css.read_text(encoding="utf-8")))
        missing = sorted(c for c in used if c not in defined)
        if missing:
            bad += 1
            print(f"{page}: {', '.join(missing)}")
    print(f"\n{bad} page(s) with undefined classes out of {len(pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
