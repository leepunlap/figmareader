#!/usr/bin/env python3
"""
Build one subsetted webfont stylesheet per Lion screen.

Why per page:
  assets/fonts/fonts.css only carries the glyphs the home/list (Tasks) screens
  use.  The Lion screens use ~600 further CJK glyphs, and a missing glyph
  silently falls back to a system face whose metrics differ from the design
  (measured: 456 809 px of ink moved when the subset was incomplete).

  A per-page subset keeps every page light (30-90 KB instead of a shared
  500 KB file) while guaranteeing that each page has every glyph it renders.

How it works:
  For each page we collect
    * the text the page renders  -> the glyph set
    * the font-weights it uses   -> which @font-face declarations we need
  then ask Google Fonts for a subset containing exactly those glyphs and
  inline the woff2 as a data URI (browsers refuse cross-origin/ file:// font
  loads otherwise, and inlining keeps the pages double-clickable).

  The generated file is linked *after* assets/fonts/fonts.css, so its
  @font-face rules win for the family+weight they declare (same-family faces
  are resolved last-declaration-wins).

  python3 scripts/fetch_lion_fonts.py            # all lion-*.html
  python3 scripts/fetch_lion_fonts.py lion-08     # just one
"""

from __future__ import annotations

import base64
import html
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "lion"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Latin faces used by the design, in the order we want them to win.
LATIN_FAMILIES = ["Poppins"]
# Weights we always provide for the CJK face.
CJK_WEIGHTS = ["400", "500", "600", "700"]
LATIN_WEIGHTS = ["400", "500", "600", "700"]

# Font stack used by the Lion pages.
FAMILY_STACK = "'Noto Sans TC', 'PingFang TC', sans-serif"


def page_files() -> list[Path]:
    return sorted(ROOT.glob("lion-*.html"))


def strip_markup(raw: str) -> str:
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(raw)


def page_text(page: Path) -> str:
    """Everything the page can possibly render: markup text, css content
    strings, and attribute values (aria-labels, alt, title, data-*)."""
    raw = page.read_text(encoding="utf-8")
    out = [strip_markup(raw)]
    # css / js string literals inside the page
    for m in re.finditer(r"content:\s*\"([^\"]*)\"|\"([^\"]{2,})\"", raw):
        out.append(m.group(1) or m.group(2) or "")
    # stylesheets the page pulls in
    for href in re.findall(r'<link[^>]+href="([^"]+\.css)"', raw):
        css_path = (ROOT / href).resolve()
        if css_path.exists():
            out.append(css_path.read_text(encoding="utf-8"))
    return " ".join(out)


def page_weights(page: Path) -> set[str]:
    """font-weight values the page can actually render with."""
    raw = page.read_text(encoding="utf-8")
    weights: set[str] = set()
    for m in re.finditer(r"font-weight:\s*(\d{3})", raw):
        weights.add(m.group(1))
    for href in re.findall(r'<link[^>]+href="([^"]+\.css)"', raw):
        css_path = (ROOT / href).resolve()
        if css_path.exists():
            for m in re.finditer(r"font-weight:\s*(\d{3})", css_path.read_text(encoding="utf-8")):
                weights.add(m.group(1))
    # always keep the base weights available
    weights |= {"400"}
    return weights


def split_sets(text: str) -> tuple[str, str]:
    cjk = "".join(sorted({c for c in text if ord(c) > 0x2000 and not c.isspace()}))
    latin = "".join(sorted({c for c in text if ord(c) <= 0x2000 and not c.isspace()}))
    return cjk, latin


def fetch_css(family: str, weight: str, text: str) -> str:
    url = (
        "https://fonts.googleapis.com/css2?family="
        + urllib.parse.quote(family)
        + ":wght@"
        + weight
        + "&text="
        + urllib.parse.quote(text)
        + "&display=swap"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def fetch_woff2(family: str, weight: str, text: str) -> bytes | None:
    try:
        css = fetch_css(family, weight, text)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] {family} {weight}: css fetch failed ({exc})")
        return None
    m = re.search(r"src:\s*url\((https://[^)]+)\)\s*format\('woff2'\)", css)
    if not m:
        print(f"  [warn] {family} {weight}: no woff2 in css")
        return None
    req = urllib.request.Request(m.group(1), headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()


def build(page: Path, weights: set[str], dry: bool = False) -> None:
    text = page_text(page)
    cjk, latin = split_sets(text)
    slug = page.stem
    out_path = FONT_DIR / f"{slug}-fonts.css"
    print(f"{slug}: {len(cjk)} CJK glyphs, {len(latin)} latin, weights {sorted(weights)}")

    rules = [
        f"/* Subsetted webfonts for {slug}.",
        " * Generated by scripts/fetch_lion_fonts.py — do not edit by hand.",
        " * Linked after assets/fonts/fonts.css so these faces win for the",
        " * characters they cover. */",
        "",
    ]

    for weight in sorted(weights):
        data = fetch_woff2("Noto Sans TC", weight, cjk)
        if not data:
            continue
        print(f"  [noto] {weight}  {len(data) / 1024:.1f} KB")
        rules.append(
            "@font-face{font-family:'Noto Sans TC';font-style:normal;font-weight:%s;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2')}"
            % (weight, base64.b64encode(data).decode("ascii"))
        )

    for weight in sorted(weights):
        if not latin:
            break
        data = fetch_woff2("Poppins", weight, latin)
        if not data:
            continue
        print(f"  [poppins] {weight}  {len(data) / 1024:.1f} KB")
        rules.append(
            "@font-face{font-family:'Poppins';font-style:normal;font-weight:%s;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2')}"
            % (weight, base64.b64encode(data).decode("ascii"))
        )

    # Arimo = Arial metrics (the Lion design's Latin is a Helvetica-class
    # grotesque, not the geometric Poppins the Tasks page uses).
    for weight in sorted(weights):
        if not latin:
            break
        data = fetch_woff2("Arimo", weight, latin)
        if not data:
            continue
        print(f"  [arimo] {weight}  {len(data) / 1024:.1f} KB")
        rules.append(
            "@font-face{font-family:'Arimo';font-style:normal;font-weight:%s;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2')}"
            % (weight, base64.b64encode(data).decode("ascii"))
        )

    css = "\n".join(rules) + "\n"
    if dry:
        return
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(css, encoding="utf-8")
    print(f"  -> {out_path.relative_to(ROOT)}  ({len(css.encode()) / 1024:.1f} KB)")


def ensure_link(page: Path) -> None:
    """Make sure the page links its own subset right after fonts.css."""
    raw = page.read_text(encoding="utf-8")
    href = f"assets/lion/{page.stem}-fonts.css"
    if href in raw:
        return
    marker = '<link rel="stylesheet" href="assets/fonts/fonts.css">'
    if marker not in raw:
        print(f"  [warn] {page.name}: fonts.css link not found")
        return
    raw = raw.replace(marker, marker + f'\n<link rel="stylesheet" href="{href}">', 1)
    page.write_text(raw, encoding="utf-8")
    print(f"  [link] {page.name} -> {href}")


def main() -> int:
    targets = sys.argv[1:]
    pages = [ROOT / f"{t}.html" for t in targets] if targets else page_files()
    for page in pages:
        if not page.exists():
            print(f"[skip] {page.name} missing")
            continue
        build(page, page_weights(page))
        ensure_link(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
