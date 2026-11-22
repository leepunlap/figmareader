#!/usr/bin/env python3
"""
Integrity-check the packaged archive.

Extracts the zip to a temp directory and verifies, for every shipped page and
stylesheet, that every asset it references is actually present in the archive.
This catches a packaging bug that would otherwise ship a broken page.

  python3 scripts/check_package.py
"""

from __future__ import annotations

import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "aimeee-2026-oct-html.zip"

ASSET_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".css")
SKIP_PREFIX = ("http://", "https://", "data:", "#", "mailto:", "//")


def main() -> int:
    if not ARCHIVE.exists():
        print(f"[error] {ARCHIVE.name} not found — run scripts/package.py first")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        with zipfile.ZipFile(ARCHIVE) as z:
            names = z.namelist()
            z.extractall(dest)

        missing: list[str] = []
        checked = 0

        for name in names:
            if not name.endswith((".html", ".css")):
                continue
            src = dest / name
            text = src.read_text(encoding="utf-8", errors="replace")
            base = src.parent

            refs: list[str] = []
            for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", text):
                refs.append(m.group(1))
            for m in re.finditer(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", text):
                refs.append(m.group(1))

            for href in refs:
                if not href or href.startswith(SKIP_PREFIX):
                    continue
                href = href.split("?")[0].split("#")[0]
                if not href or not href.lower().endswith(ASSET_EXT):
                    continue
                checked += 1
                if not (base / href).resolve().exists():
                    missing.append(f"{name} -> {href}")

        print(f"archive : {ARCHIVE.name}")
        print(f"files   : {len(names)}")
        print(f"checked : {checked} asset references")

        if missing:
            print(f"\n[FAIL] {len(missing)} broken reference(s):")
            for m in missing[:40]:
                print("  ", m)
            return 1

        print("\n[OK] every asset reference resolves inside the archive")
        return 0


if __name__ == "__main__":
    sys.exit(main())
