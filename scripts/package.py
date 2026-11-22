#!/usr/bin/env python3
"""
Package the static reproduction into a zip.

The deliverable is the HTML/CSS itself, so the archive contains:

  * index.html          the gallery
  * the 15 screen pages
  * styles.css / styles-lion.css
  * README.md
  * assets/             every image and stylesheet the pages actually reference

It deliberately does NOT ship source/ (72 MB of 4x Figma exports) or analysis/
(scratch measurements) — those are working files, not part of the reproduction.

Only assets that are referenced from the shipped HTML/CSS are included, so
superseded intermediates do not bloat the archive.

  python3 scripts/package.py                 # -> aimeee-2026-oct-html.zip
  python3 scripts/package.py --out other.zip
"""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "index.html",
    "compare-lion.html",
    "v1.html",
    "home.html",
    "list-020.html",
    "list-023.html",
    "list-027.html",
    *[f"lion-{i:02d}.html" for i in range(1, 12)],
]
STYLESHEETS = ["styles.css", "styles-lion.css", "styles-v1.css"]
DOCS = ["README.md", "WORKER-BRIEF.md"]


def v1_pages() -> list[str]:
    """The v1.0 screens — one HTML file per built screen, for both the big
    `v1.0` page (v1-*) and the `v1.0 最初版 - (7.3)` page (v73-*)."""
    return sorted([p.name for p in ROOT.glob("v1-*.html")] +
                  [p.name for p in ROOT.glob("v73-*.html")])


COPY = PAGES + STYLESHEETS + DOCS

ASSET_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".css")
SKIP_PREFIX = ("http://", "https://", "data:", "#", "mailto:", "//")


def _resolve(base: Path, href: str) -> Path | None:
    """Resolve a reference found in `base`'s own directory."""
    if not href or href.startswith(SKIP_PREFIX):
        return None
    href = href.split("?")[0].split("#")[0]
    if not href:
        return None
    p = (base / href).resolve()
    try:
        p.relative_to(ROOT)
    except ValueError:
        return None
    return p


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def referenced_assets() -> set[str]:
    """Every asset path the shipped pages and stylesheets point at.

    A reference inside a stylesheet is relative to THAT stylesheet's directory
    (assets/lion/lion-07.css -> assets/lion/lion-07-hero.png), while a
    reference inside an HTML page is relative to the page.
    """
    out: set[str] = set()
    seeds = [n for n in COPY if (ROOT / n).exists()] + v1_pages()
    queue: list[Path] = [ROOT / n for n in seeds if (ROOT / n).exists()]
    seen: set[Path] = set()

    while queue:
        src = queue.pop()
        try:
            src = src.resolve()
        except OSError:
            continue
        if src in seen:
            continue
        seen.add(src)

        text = _read(src)
        if not text:
            continue
        base = src.parent

        # href="..." / src="..."  (HTML)
        for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", text):
            p = _resolve(base, m.group(1))
            if p is None or not p.exists():
                continue
            if p.suffix.lower() == ".css":
                queue.append(p)
                out.add(p.relative_to(ROOT).as_posix())
            elif p.suffix.lower() in ASSET_EXT:
                out.add(p.relative_to(ROOT).as_posix())

        # url(...) in CSS and in a page's inline <style>
        for m in re.finditer(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", text):
            p = _resolve(base, m.group(1))
            if p is not None and p.exists() and p.suffix.lower() in ASSET_EXT:
                out.add(p.relative_to(ROOT).as_posix())

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="aimeee-2026-oct-html.zip")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # v1.html is regenerated from the built screens; it only exists once at
    # least one v1 screen has been built.
    missing = [n for n in COPY if not (ROOT / n).exists() and n != "v1.html"]
    if missing:
        raise SystemExit(f"[error] missing deliverable files: {missing}")
    copy = [n for n in COPY if (ROOT / n).exists()]

    files: list[str] = list(copy) + v1_pages() + sorted(referenced_assets())
    # a file may be reachable both as a top-level deliverable and as a
    # referenced asset — keep one entry
    files = list(dict.fromkeys(files))

    if args.dry_run:
        for n in files:
            print(n)
        return 0

    out_path = ROOT / args.out
    # A worker may end up linking the same font subset under two names; keep
    # one copy of byte-identical files so the archive does not carry the same
    # base64 payload twice.
    refs = referenced_assets()
    seen: dict[bytes, str] = {}
    deduped: list[str] = []
    for name in files:
        digest = hashlib.sha256((ROOT / name).read_bytes()).digest()
        # a referenced file is always kept — dropping it would break a page
        if digest in seen and name not in refs:
            print(f"[dedupe] {name} == {seen[digest]}")
            continue
        seen.setdefault(digest, name)
        deduped.append(name)
    files = deduped

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in files:
            z.write(ROOT / name, name)

    size = out_path.stat().st_size / 1024
    print(f"{out_path.name}: {len(files)} files, {size:.0f} KB")
    print(f"  {len(PAGES)} pages, {len(files) - len(COPY)} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
