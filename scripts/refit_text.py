#!/usr/bin/env python3
"""
Re-place the text of an existing page with freshly fitted geometry.

A page that was cloned from a sibling (or hand-built earlier) carries the
positions of that sibling.  When the export of the target screen sits a
pixel or two lower, or uses a slightly different size, every text run has to
move.  This tool reads the fitted geometry of the target screen and writes it
back into the page's own stylesheet, matching the page's text elements to the
OCR runs by position and by how similar the two strings are.

    python3 scripts/refit_text.py v73-competition-01
    python3 scripts/refit_text.py v73-competition-01 --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def page_files(slug: str) -> tuple[Path, Path]:
    name = slug[3:] if slug.startswith("v1-") else slug
    html = ROOT / f"{slug}.html"
    css = ROOT / "assets/v1" / f"{name}.css"
    if not html.exists() or not css.exists():
        raise SystemExit(f"[error] {html} or {css} missing")
    return html, css


def element_texts(html: str) -> dict[str, str]:
    """class -> the text of the first element that uses it."""
    out: dict[str, str] = {}
    for m in re.finditer(r'<(?:p|span|h[1-6]|div)\b[^>]*class="([^"]+)"[^>]*>([^<]*)</', html):
        classes = m.group(1).split()
        text = m.group(2).strip()
        if not text:
            continue
        for c in classes:
            out.setdefault(c, text)
    return out


def rules(css: str) -> list[tuple[str, str, int, int]]:
    """(selector, body, start, end) for every rule in the sheet."""
    out = []
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
        out.append((m.group(1).strip(), m.group(2), m.start(2), m.end(2)))
    return out


def decl(body: str, prop: str) -> str | None:
    m = re.search(r'(?:^|;)\s*%s\s*:\s*([^;]+)' % prop, body)
    return m.group(1).strip() if m else None


def num(v: str | None) -> float | None:
    if not v:
        return None
    m = re.match(r'-?[\d.]+', v)
    return float(m.group(0)) if m else None


def norm(s: str) -> str:
    return re.sub(r'\s+', '', s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tol", type=float, default=26.0,
                    help="max distance between the element and the OCR run")
    args = ap.parse_args()

    slug = args.slug
    html_path, css_path = page_files(slug)
    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")

    fit_path = ROOT / "analysis/ocr" / f"{slug}-fit.json"
    if not fit_path.exists():
        raise SystemExit(f"[error] {fit_path} missing - run scripts/ocrfit.py {slug}")
    runs = [r for r in json.loads(fit_path.read_text(encoding="utf-8")) if r.get("fit")]

    texts = element_texts(html)
    edits: list[tuple[int, int, str]] = []
    used: set[int] = set()
    changed = 0

    for selector, body, s, e in rules(css):
        left = num(decl(body, "left"))
        top = num(decl(body, "top"))
        if left is None or top is None:
            continue
        # the class this rule positions
        classes = re.findall(r'\.([\w-]+)', selector)
        cls = None
        for c in classes:
            if c in texts:
                cls = c
                break
        if cls is None:
            continue
        want = norm(texts[cls])
        best = None
        for i, r in enumerate(runs):
            if i in used:
                continue
            dist = ((r["src_x0"] - left) ** 2 + (r["src_y0"] - top) ** 2) ** 0.5
            if dist > args.tol:
                continue
            sim = SequenceMatcher(None, want, norm(r["text"])).ratio()
            score = dist - sim * 12.0
            if best is None or score < best[0]:
                best = (score, i, dist, sim)
        if best is None:
            continue
        _, i, dist, sim = best
        used.add(i)
        f = runs[i]["fit"]
        new_left = f"{f['left']:.2f}px"
        new_top = f"{f['top']:.2f}px"
        new_fs = f"{f['fs']:.2f}px"
        if decl(body, "left") == new_left and decl(body, "top") == new_top \
                and decl(body, "font-size") == new_fs:
            continue
        nb = re.sub(r'left\s*:\s*[^;]+', "left: " + new_left, body)
        nb = re.sub(r'top\s*:\s*[^;]+', "top: " + new_top, nb)
        if decl(nb, "font-size"):
            nb = re.sub(r'font-size\s*:\s*[^;]+', "font-size: " + new_fs, nb)
        else:
            nb = nb.rstrip() + f"\n  font-size: {new_fs};"
        w = f.get("weight", 400)
        if w != 400:
            if decl(nb, "font-weight"):
                nb = re.sub(r'font-weight\s*:\s*[^;]+', f"font-weight: {w}", nb)
            else:
                nb = nb.rstrip() + f"\n  font-weight: {w};"
        edits.append((s, e, nb))
        changed += 1
        print(f"  {cls:22} {left:7.2f},{top:7.2f} -> {f['left']:7.2f},{f['top']:7.2f} "
              f"fs {f['fs']:5.2f} w{w}  sim{sim:.2f} d{dist:.1f}  {texts[cls][:18]!r}")

    if not args.dry_run and edits:
        for s, e, nb in sorted(edits, reverse=True):
            css = css[:s] + nb + css[e:]
        css_path.write_text(css, encoding="utf-8")
    print(f"{slug}: {changed} rules updated" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
