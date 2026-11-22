#!/usr/bin/env python3
"""Audit every built screen for text whose declared font-size disagrees with
the size the Figma export actually used.

A CJK ideograph advances exactly 1 em in PingFang SC and in Noto Sans TC, in
every weight.  The start-to-start distance of two adjacent CJK glyphs is
therefore the font size, read straight off the export - no rendering needed
and no font assumption.  Latin-only runs cannot be measured this way, so they
are reported separately.

For every screen this script
  * measures the implied font size of every OCR run that contains >= 2 CJK
    characters,
  * finds the CSS rule of the page that renders that text,
  * and prints the two sizes side by side.

Usage:
    python3 scripts/sizeaudit.py                # every screen
    python3 scripts/sizeaudit.py v1-vip-membership-yearly
    python3 scripts/sizeaudit.py --worst 30
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3005\u3007]")

# OCR run boxes are 1x css px; the exports are 4x
EXPORT_SCALE = 4.0


# --------------------------------------------------------------------------
# source + OCR


def manifest_rows() -> list[tuple[str, Path, int, int]]:
    """(page name, source png, css width, css height) for every screen."""
    rows = []
    for folder, pref in (("v1raw", "v1"), ("v1raw73", "v73")):
        m = ROOT / "source" / folder / "screens" / "manifest.json"
        if not m.exists():
            continue
        for r in json.loads(m.read_text(encoding="utf-8")):
            slug = r["slug"]
            page = r.get("page") or f"v1-{slug}.html"
            src = ROOT / "source" / folder / "screens" / r["file"]
            rows.append((page, src, r["css"][0], r["css"][1]))
    return rows


def load_runs(page: str) -> list[dict]:
    stem = page[:-5] if page.endswith(".html") else page
    p = ROOT / "analysis" / "ocr" / f"{stem}.tsv"
    if not p.exists():
        return []
    runs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            x0, y0, x1, y1 = (float(parts[i]) for i in range(4))
        except ValueError:
            continue
        runs.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": parts[5]})
    return runs


# --------------------------------------------------------------------------
# measurement


def ink_columns(reg: np.ndarray, thr: int = 90) -> list[tuple[int, int]]:
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    mask = np.abs(reg - bg).sum(axis=2) > thr
    cols = mask.any(axis=0)
    runs, start = [], None
    for i, v in enumerate(cols):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(cols)))
    return runs


def ink_box(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int,
            thr: int = 90) -> tuple[int, int, int, int] | None:
    """Tight ink box of a region, background taken from the edges."""
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    reg = arr[y0:y1, x0:x1]
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    mask = np.abs(reg - bg).sum(axis=2) > thr
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)


# A full-width CJK ideograph is 0.93 em tall in Noto Sans TC (measured: a
# 15 px run has a 14.0 px ink height), and a Latin capital is 0.765 em.
CJK_INK_RATIO = 0.93
CAP_INK_RATIO = 0.765


def implied_fs_by_height(arr: np.ndarray, run: dict, scale: float) -> float | None:
    """Font size implied by the ink height of a run.

    CJK ideographs are taller than Latin capitals, so a line that contains
    any ideograph is sized by the ideograph; a pure-Latin line is sized by
    its capitals.
    """
    x0 = max(0, int(run["x0"] * scale) - 2)
    y0 = max(0, int(run["y0"] * scale) - 2)
    x1 = min(arr.shape[1], int(run["x1"] * scale) + 2)
    y1 = min(arr.shape[0], int(run["y1"] * scale) + 2)
    box = ink_box(arr, x0, y0, x1, y1)
    if box is None:
        return None
    h = box[3] - box[1]
    if h < 6:
        return None
    text = run["text"]
    ratio = CJK_INK_RATIO if CJK.search(text) else CAP_INK_RATIO
    return h / scale / ratio


def implied_fs(arr: np.ndarray, run: dict, scale: float) -> float | None:
    """Font size implied by the CJK advance of a run, or None.

    A full-width ideograph advances exactly 1 em, but the *ink* of a glyph
    starts at its own left side bearing, so the gap between two glyph starts
    is 1 em only on average.  Measuring a span of several glyphs and dividing
    by the number of gaps averages the side bearings out.

    CJK glyphs are much wider than Latin letters, so the column groups are
    classified by width and only the longest contiguous run of wide groups is
    used.
    """
    if len(CJK.findall(run["text"])) < 2:
        return None
    x0 = max(0, int(run["x0"] * scale) - 2)
    y0 = max(0, int(run["y0"] * scale) - 2)
    x1 = min(arr.shape[1], int(run["x1"] * scale) + 2)
    y1 = min(arr.shape[0], int(run["y1"] * scale) + 2)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    cols = ink_columns(arr[y0:y1, x0:x1])
    if len(cols) < 2:
        return None
    widths = [b - a for a, b in cols]
    wmax = max(widths)
    if wmax < 4:
        return None
    # a CJK glyph is roughly 0.9 em wide while a Latin letter is about 0.55 em;
    # the threshold has to sit between the two so that only ideographs qualify
    wide = [w >= 0.72 * wmax for w in widths]
    # longest contiguous run of wide groups
    best_len, best_start, cur_len, cur_start = 0, 0, 0, 0
    for i, is_wide in enumerate(wide):
        if is_wide:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0
    if best_len < 2:
        return None
    span = cols[best_start + best_len - 1][0] - cols[best_start][0]
    return span / (best_len - 1) / scale


# --------------------------------------------------------------------------
# page structure


def css_rules(css: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]


def decl(body: str, prop: str) -> str | None:
    m = re.search(r"(?:^|;)\s*%s\s*:\s*([^;]+)" % prop, body)
    return m.group(1).strip() if m else None


def num(v: str | None) -> float | None:
    if not v:
        return None
    m = re.match(r"-?[\d.]+", v)
    return float(m.group(0)) if m else None


def element_texts(html: str) -> dict[str, str]:
    """class -> text of the first element that uses the class."""
    out: dict[str, str] = {}
    for m in re.finditer(
        r'<(?:p|span|h[1-6]|div|li|td|th)\b[^>]*class="([^"]+)"[^>]*>([^<]*)</',
        html,
    ):
        text = m.group(2).strip()
        if not text:
            continue
        for c in m.group(1).split():
            out.setdefault(c, text)
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


# --------------------------------------------------------------------------


def audit(page: str, src: Path) -> list[dict]:
    """Rows of {text, implied, declared, class, delta}."""
    html_p = ROOT / page
    name = page[3:-5] if page.startswith("v1-") else page[4:-5]
    css_p = ROOT / "assets" / "v1" / f"{name}.css"
    if not html_p.exists() or not css_p.exists():
        return []
    html = html_p.read_text(encoding="utf-8")
    css = css_p.read_text(encoding="utf-8")
    runs = load_runs(page)
    if not runs:
        return []
    arr = np.array(Image.open(src).convert("RGB")).astype(int)

    texts = element_texts(html)
    # class -> declared font-size, and class -> (left, top)
    fs_of: dict[str, float] = {}
    pos_of: dict[str, tuple[float, float]] = {}
    for sel, body in css_rules(css):
        fs = num(decl(body, "font-size"))
        left = num(decl(body, "left"))
        top = num(decl(body, "top"))
        for c in re.findall(r"\.([\w-]+)", sel):
            if fs is not None and c not in fs_of:
                fs_of[c] = fs
            if left is not None and top is not None and c not in pos_of:
                pos_of[c] = (left, top)

    out = []
    for r in runs:
        imp = implied_fs(arr, r, EXPORT_SCALE)
        if imp is None:
            continue
        # find the CSS class whose text matches this run best
        best = None
        for cls, txt in texts.items():
            if cls not in fs_of:
                continue
            sim = len(set(norm(txt)) & set(norm(r["text"]))) / max(
                1, len(set(norm(txt)) | set(norm(r["text"])))
            )
            if best is None or sim > best[0]:
                best = (sim, cls)
        if best is None or best[0] < 0.55:
            continue
        cls = best[1]
        declared = fs_of[cls]
        out.append({
            "text": r["text"], "implied": round(imp, 1),
            "declared": declared, "class": cls,
            "delta": round(imp - declared, 1),
            "y": r["y0"],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=[])
    ap.add_argument("--worst", type=int, default=30)
    ap.add_argument("--tolerance", type=float, default=1.2,
                    help="max accepted |implied - declared| in css px")
    args = ap.parse_args()

    rows_all = []
    wanted = set()
    for p in args.pages:
        wanted.add(p if p.endswith(".html") else p + ".html")
    for page, src, _w, _h in manifest_rows():
        if wanted and page not in wanted:
            continue
        if not (ROOT / page).exists():
            continue
        try:
            rows = audit(page, src)
        except Exception as exc:  # noqa: BLE001 - keep going on a bad screen
            print(f"[warn] {page}: {exc}", file=sys.stderr)
            continue
        bad = [r for r in rows if abs(r["delta"]) > args.tolerance]
        if bad:
            rows_all.append((page, bad, rows))

    if args.pages and len(args.pages) == 1:
        page, bad, rows = rows_all[0]
        print(f"{page}: {len(rows)} CJK runs, {len(bad)} size mismatches")
        print(f"{'implied':>8} {'declared':>9} {'delta':>7}  {'y':>6}  class / text")
        for r in sorted(bad, key=lambda r: -abs(r["delta"])):
            print(f"{r['implied']:8.1f} {r['declared']:9.1f} {r['delta']:7.1f}  "
                  f"{r['y']:6.0f}  {r['class']:20s} {r['text'][:26]}")
        return 0

    total_bad = sum(len(b) for _p, b, _r in rows_all)
    print(f"{total_bad} size mismatches across {len(rows_all)} screens")
    rows_all.sort(key=lambda t: -len(t[1]))
    for page, bad, _rows in rows_all[: args.worst]:
        worst = max(bad, key=lambda r: abs(r["delta"]))
        print(f"  {page:34s} {len(bad):3d} bad   worst {worst['delta']:+6.1f} "
              f"({worst['implied']} vs {worst['declared']})  {worst['text'][:20]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
