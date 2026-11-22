#!/usr/bin/env python3
"""
Compare candidate CJK typefaces against the Figma export.

Each candidate is downloaded as a subset (only the glyphs the pages use),
wired up as a local @font-face, and the pages are rendered and diffed.

  python3 scripts/font_family_sweep.py
"""

from __future__ import annotations

import html
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-famsweep")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SCREENS = {"home": ("home.html", 1196), "list-020": ("list-020.html", 1074)}

# name, google fonts family, weights
CANDIDATES = [
    ("NotoSansTC", "Noto Sans TC", ["400", "700"]),
    ("MPLUSRounded", "M PLUS Rounded 1c", ["400", "700"]),
    ("ZenKaku", "Zen Kaku Gothic New", ["400", "700"]),
    ("KosugiMaru", "Kosugi Maru", ["400", "500"]),
    ("ZenMaru", "Zen Maru Gothic", ["400", "500", "700"]),
    ("NotoSansHK", "Noto Sans HK", ["400", "500", "700"]),
    ("Chiron", "Chiron Sans HK", ["400", "500", "700"]),
]


def page_text() -> str:
    out = []
    for page in ("home.html", "list-020.html", "list-023.html", "list-027.html"):
        raw = (ROOT / page).read_text(encoding="utf-8")
        raw = re.sub(r"<[^>]+>", " ", raw)
        out.append(html.unescape(raw))
    return " ".join(out)


def subset(family: str, weight: str, text: str) -> bytes:
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
    css = urllib.request.urlopen(req, timeout=60).read().decode()
    m = re.search(r"src:\s*url\((https://[^)]+)\)\s*format\('woff2'\)", css)
    if not m:
        raise SystemExit(f"[error] no woff2 for {family} {weight}")
    req = urllib.request.Request(m.group(1), headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()


def build_family(cand, text) -> Path:
    name, family, weights = cand
    d = WORK / name
    d.mkdir(parents=True, exist_ok=True)
    rules = []
    for w in weights:
        try:
            data = subset(family, w, text)
        except Exception as e:  # family may not ship every weight
            print(f"  [skip] {family} {w}: {e}")
            continue
        (d / f"{name}-{w}.woff2").write_bytes(data)
        rules.append(
            "@font-face{font-family:'%s';font-style:normal;font-weight:%s;"
            "font-display:swap;src:url('%s-%s.woff2') format('woff2')}" % (name, w, name, w)
        )
    if not rules:
        raise SystemExit(f"[error] no usable weight for {family}")
    css = "\n".join(rules) + "\n"
    (d / "f.css").write_text(css, encoding="utf-8")
    print(f"  [font] {name}: {sum(f.stat().st_size for f in d.glob('*.woff2'))/1024:.0f} KB")
    return d


def prepare(page: str, fontdir: Path, family: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html_ = (ROOT / page).read_text(encoding="utf-8")
    html_ = html_.replace("<body>", '<body class="render">')
    html_ = html_.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    html_ = html_.replace(
        "</head>",
        f'<link rel="stylesheet" href="file://{fontdir}/f.css">'
        f"<style>:root{{--font:'Poppins','{family}',sans-serif}}</style></head>",
        1,
    )
    out = WORK / f"{family}-{page}"
    out.write_text(html_, encoding="utf-8")
    return out


def shoot(path: Path, height: int, family: str) -> Path:
    out = WORK / f"{family}-{path.stem}.png"
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions", "--allow-file-access-from-files",
        "--force-device-scale-factor=2", "--virtual-time-budget=9000",
        "--user-data-dir=%s/profile" % WORK,
        "--window-size=390,%d" % height,
        "--screenshot=%s" % out,
        "file://%s" % path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return out


def diff(render: Path, source: Path) -> float:
    a = np.asarray(Image.open(render).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(source).convert("RGB").resize((a.shape[1], a.shape[0]), Image.LANCZOS)).astype(np.int16)
    d = np.abs(a - b).sum(axis=2)
    return float((d > 24).mean()) * 100


def main() -> int:
    text = page_text()
    cjk = "".join(sorted({c for c in text if ord(c) > 0x2000}))
    print(f"subsetting {len(cjk)} glyphs per family\n")
    results = {}
    for cand in CANDIDATES:
        name = cand[0]
        try:
            d = build_family(cand, cjk)
        except SystemExit as e:
            print(" ", e)
            continue
        except Exception as e:
            print(f"  [error] {name}: {e}")
            continue
        tot = 0.0
        for screen, (page, height) in SCREENS.items():
            p = prepare(page, d, name)
            shot = shoot(p, height, name)
            v = diff(shot, ROOT / "source" / f"{screen}.png")
            tot += v
            print(f"    {screen:10s} {v:6.2f}%")
        results[name] = tot / len(SCREENS)
        print(f"  [{name}] average {results[name]:.3f}%\n")
    print("=== ranking ===")
    for name, v in sorted(results.items(), key=lambda kv: kv[1]):
        print(f"  {name:14s} {v:6.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
