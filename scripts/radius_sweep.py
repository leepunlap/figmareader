#!/usr/bin/env python3
"""
Empirically pick border radii / offsets by rendering the page with a CSS
override and measuring the pixel diff against the Figma export.

  python3 scripts/radius_sweep.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-sweep")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCREENS = {"home": ("home.html", 1196), "list-020": ("list-020.html", 1074), "list-027": ("list-027.html", 990)}

TRIALS = [
    ("baseline",      "list-020", ""),
    ("sheet332",      "list-020", ".sheet{top:332px}"),
    ("sheet332r24",   "list-020", ".sheet{top:332px;border-radius:24px 24px 0 0}"),
    ("sheet332r30",   "list-020", ".sheet{top:332px;border-radius:30px 30px 0 0}"),
    ("sheet331r28",   "list-020", ".sheet{top:331px}"),
    ("taskr15",       "list-020", ".task{border-radius:15px}"),
    ("taskr18",       "list-020", ".task{border-radius:18px}"),
    ("taskr19",       "list-020", ".task{border-radius:19px}"),
    ("cardr18",       "home",     ".card{border-radius:18px}"),
    ("cardr21",       "home",     ".card{border-radius:21px}"),
    ("cardr24",       "home",     ".card{border-radius:24px}"),
    ("cardr26",       "home",     ".card{border-radius:26px}"),
]


def run(tag: str, screen: str, css: str) -> float:
    page, height = SCREENS[screen]
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    if css:
        html = html.replace("</head>", f"<style>{css}</style></head>", 1)
    p = WORK / f"{tag}.html"
    p.write_text(html, encoding="utf-8")
    out = WORK / f"{tag}.png"
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions", "--allow-file-access-from-files",
        "--force-device-scale-factor=2", "--virtual-time-budget=9000",
        "--user-data-dir=%s/profile" % WORK,
        "--window-size=390,%d" % height,
        "--screenshot=%s" % out,
        "file://%s" % p,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    a = np.asarray(Image.open(out).convert("RGB")).astype(np.int16)
    b = np.asarray(
        Image.open(ROOT / "source" / f"{screen}.png").convert("RGB").resize((a.shape[1], a.shape[0]), Image.LANCZOS)
    ).astype(np.int16)
    d = np.abs(a - b).sum(axis=2)
    return float((d > 24).mean()) * 100


def main() -> int:
    for tag, screen, css in TRIALS:
        v = run(tag, screen, css)
        print(f"  {tag:14s} {screen:10s} {v:6.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
