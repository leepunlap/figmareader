#!/usr/bin/env python3
"""
Fix the characters the OCR got wrong on a screen.

The macOS Vision OCR reads 資源 as 资源 and 學校 as 学校 (simplified forms),
and it swallows the little chevron arrows of the design into the text run.
Correcting the text and narrowing the box keeps the fitter from solving for a
font size that has to cover artwork that is not text.

    python3 scripts/ocr_fix.py v1-home-1 资源=資源 学校=學校
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    slug = sys.argv[1]
    pairs = []
    for a in sys.argv[2:]:
        old, new = a.split("=", 1)
        pairs.append((old, new))

    tsv = ROOT / "analysis/ocr" / f"{slug}.tsv"
    md = ROOT / "analysis/ocr" / f"{slug}.md"
    rows = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 6:
            continue
        text = "\t".join(p[5:]).strip()
        for old, new in pairs:
            if text == old:
                text = new
                p[5] = text
        rows.append(p)

    out = "\n".join("\t".join(p) for p in rows) + "\n"
    tsv.write_text(out, encoding="utf-8")

    lines = [f"# OCR — {slug}", "", "source: v1 export, boxes in 1x css pixels", "",
             "| x0 | y0 | x1 | y1 | conf | text |", "|---|---|---|---|---|---|"]
    for p in rows:
        lines.append(f"| {p[0]} | {p[1]} | {p[2]} | {p[3]} | {p[4]} | {p[5]} |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{slug}: {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
