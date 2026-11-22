#!/usr/bin/env python3
"""
Find CSS classes that no markup uses ("phantom" classes).

orphan_classes.py goes the other way: it finds markup classes that no
stylesheet defines, so the element silently loses its measured position.

This tool finds the opposite case: the stylesheet positions an element
(absolute left/top/width/height, or a background) that the page never
renders.  The visible effect is a whole card, badge or picture missing
from the page while the CSS looks correct.

  python3 scripts/phantom_classes.py            # every page
  python3 scripts/phantom_classes.py v1-home    # one page
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLASS_RE = re.compile(r'class="([^"]+)"')
LINK_RE = re.compile(r'<link[^>]+href="([^"]+\.css)"')
RULE_RE = re.compile(r'([^{}]*)\{([^{}]*)\}')
SELECTOR_RE = re.compile(r'\.([A-Za-z0-9_-]+)')
# a rule that actually paints something
PAINTS = ("left:", "top:", "width:", "height:", "background", "border",
          "box-shadow", "font-size", "color:", "position:")


def page_css(page: Path) -> list[Path]:
    html = page.read_text(encoding="utf-8")
    out = []
    for href in LINK_RE.findall(html):
        p = ROOT / href
        if p.exists():
            out.append(p)
    return out


def defined_classes(sheets: list[Path]) -> dict[str, list[str]]:
    """class name -> list of declarations, for rules that paint something."""
    out: dict[str, list[str]] = {}
    for sheet in sheets:
        text = sheet.read_text(encoding="utf-8")
        # strip comments
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        for m in RULE_RE.finditer(text):
            sel, body = m.group(1), m.group(2)
            if "@" in sel or not body.strip():
                continue
            if not any(p in body for p in PAINTS):
                continue
            for cls in SELECTOR_RE.findall(sel):
                out.setdefault(cls, []).append(body.strip())
    return out


def used_classes(page: Path) -> set[str]:
    html = page.read_text(encoding="utf-8")
    body = html.split("</head>", 1)[-1]
    used: set[str] = set()
    for g in CLASS_RE.findall(body):
        used.update(g.split())
    return used


def main(argv: list[str]) -> int:
    pages = sorted(list(ROOT.glob("v1-*.html")) + list(ROOT.glob("v73-*.html")))
    if argv:
        pages = [p for p in pages if p.stem in argv]
    bad = 0
    for page in pages:
        sheets = page_css(page)
        if not sheets:
            continue
        defined = defined_classes(sheets)
        used = used_classes(page)
        # a class is shared with the global stylesheet only if it is used
        missing = []
        for cls, bodies in defined.items():
            if cls in used:
                continue
            # skip shared/global hook classes that the page does not need
            if cls.startswith(("v1", "v73", "is-", "has-", "js-")):
                continue
            missing.append(cls)
        if missing:
            bad += 1
            print(f"{page.name}: {', '.join(sorted(missing))}")
    print(f"\n{bad} page(s) with phantom classes out of {len(pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
