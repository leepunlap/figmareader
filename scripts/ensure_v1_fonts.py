#!/usr/bin/env python3
"""
Make sure every built v1.0 page ships the font subset it links.

A page that links assets/v1/<slug>-fonts.css but does not ship that file
silently falls back to a system face, whose metrics differ from the design —
so the page renders, but its diff jumps and the fallback is invisible.

This reads the actual <link href> out of each page and generates exactly that
file, so it does not matter whether a page calls its subset "home-fonts.css"
or "v1-home-fonts.css".

  python3 scripts/ensure_v1_fonts.py          # generate the missing ones
  python3 scripts/ensure_v1_fonts.py --check  # only report
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets/v1"
LINK = re.compile(r'<link[^>]+href="(assets/v1/[^"]*-fonts\.css)"')


def linked_fonts(page: Path) -> list[str]:
    raw = page.read_text(encoding="utf-8")
    out: list[str] = []
    for href in LINK.findall(raw):
        if href not in out:
            out.append(href)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    jobs: list[tuple[str, str]] = []      # (page stem, href)
    pages = sorted(list(ROOT.glob("v1-*.html")) + list(ROOT.glob("v73-*.html")))
    for page in pages:
        hrefs = linked_fonts(page)
        if hrefs:
            for href in hrefs:
                if not (ROOT / href).exists():
                    jobs.append((page.stem, href))
        else:
            # the page ships no per-page subset at all: give it one, otherwise
            # its CJK glyphs fall back to a system face with the wrong metrics
            jobs.append((page.stem, f"assets/v1/{page.stem}-fonts.css"))

    if not jobs:
        print("[fonts] every built v1 page ships the subset it links")
        return 0

    print(f"[fonts] {len(jobs)} missing subset(s):")
    for stem, href in jobs:
        print(f"  {stem} -> {href}")
    if args.check:
        return 1

    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for stem, href in jobs:
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts/fetch_v1_fonts.py"), stem, "--out", href],
            cwd=ROOT, capture_output=True, text=True,
        )
        ok = (ROOT / href).exists()
        print(f"  {stem} -> {href}: {'ok' if ok else 'FAILED'}")
        if not ok:
            print("   ", (r.stdout or "") + (r.stderr or "")[-400:])
        elif not linked_fonts(ROOT / f"{stem}.html"):
            # --out does not insert the <link>; do it here
            page = ROOT / f"{stem}.html"
            raw = page.read_text(encoding="utf-8")
            marker = '<link rel="stylesheet" href="assets/fonts/fonts.css">'
            if marker in raw and href not in raw:
                raw = raw.replace(marker, marker + f'\n<link rel="stylesheet" href="{href}">')
                page.write_text(raw, encoding="utf-8")
                print(f"  {stem}: linked {href}")

    still = [h for _s, h in jobs if not (ROOT / h).exists()]
    if still:
        print(f"[fonts] still missing: {', '.join(still)}")
        return 1
    print("[fonts] all subsets present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
