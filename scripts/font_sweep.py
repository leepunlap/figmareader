#!/usr/bin/env python3
"""
Sweep typography configurations and rank them by how close the rendered page
lands to the Figma export (percentage of pixels that differ).

  python3 scripts/font_sweep.py            # sweep on list-020 + home
  python3 scripts/font_sweep.py --all      # every screen for every config
  python3 scripts/font_sweep.py --verify "base"   # one config, all screens
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-sweep")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCREENS = {
    "home":     ("home.html", 1196),
    "list-020": ("list-020.html", 1074),
    "list-023": ("list-023.html", 1032),
    "list-027": ("list-027.html", 990),
}

BODY = (
    ".hero__age,.home__lede,.hero__role,.section__lede,.home__caption,.card__text,"
    ".banner__duration,.banner__age,.progress__label,.task__desc,.task__note,.task__duration"
)
BOLD = (
    ".hero__title,.hero__name,.section__title,.card__title,.card__badge,.cta,.banner__title,"
    ".progress__count,.task__title,.task__badge,.list__title h2"
)

CONFIGS = {
    "base":            "",
    "body500":         f"{BODY}{{font-weight:500}}",
    "body500-bold600": f"{BODY}{{font-weight:500}} {BOLD}{{font-weight:600}}",
    "body300":         f"{BODY}{{font-weight:300}}",
    "bold600":         f"{BOLD}{{font-weight:600}}",
    "pingfang":        "body,html{font-family:'PingFang TC',sans-serif!important}",
    "noto500":         f"{BODY}{{font-weight:500}} {BOLD}{{font-weight:500}}",
}


def prepare(page: str, css: str, tag: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    if css:
        html = html.replace("</head>", f"<style>{css}</style></head>", 1)
    out = WORK / f"{tag}-{page}"
    out.write_text(html, encoding="utf-8")
    return out


def shoot(page_path: Path, height: int, tag: str) -> Path:
    out = WORK / f"{tag}-{page_path.stem}.png"
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions", "--allow-file-access-from-files",
        "--force-device-scale-factor=2", "--virtual-time-budget=9000",
        "--user-data-dir=%s/profile" % WORK,
        "--window-size=390,%d" % height,
        "--screenshot=%s" % out,
        "file://%s" % page_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not out.exists():
        raise SystemExit(f"[error] no screenshot for {page_path}")
    return out


def diff(render: Path, source: Path) -> tuple[float, float]:
    a = np.asarray(Image.open(render).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(source).convert("RGB")).astype(np.int16)
    if a.shape != b.shape:
        b = np.asarray(
            Image.open(source).convert("RGB").resize((a.shape[1], a.shape[0]), Image.LANCZOS)
        ).astype(np.int16)
    d = np.abs(a - b).sum(axis=2)
    return float((d > 24).mean()) * 100, float(d.mean()) / 3.0


def run(tag: str, css: str, screens: list[str]) -> dict[str, tuple[float, float]]:
    out = {}
    for name in screens:
        page, height = SCREENS[name]
        p = prepare(page, css, tag)
        shot = shoot(p, height, tag)
        out[name] = diff(shot, ROOT / "source" / f"{name}.png")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--verify", default="")
    args = ap.parse_args()

    if args.verify:
        screens = list(SCREENS)
        configs = {args.verify: CONFIGS.get(args.verify, "")}
    else:
        screens = list(SCREENS) if args.all else ["list-020", "home"]
        configs = CONFIGS

    results = {}
    for tag, css in configs.items():
        res = run(tag, css, screens)
        results[tag] = res
        total = sum(v[0] for v in res.values()) / len(res)
        print(f"\n[{tag}]")
        for name in screens:
            print(f"   {name:10s} diff {res[name][0]:6.2f}%  mean {res[name][1]:5.2f}")
        print(f"   {'AVERAGE':10s} diff {total:6.2f}%")

    print("\n\n=== ranking (average diff %, lower is better) ===")
    ranked = sorted(
        results.items(),
        key=lambda kv: sum(v[0] for v in kv[1].values()) / len(kv[1]),
    )
    for tag, res in ranked:
        avg = sum(v[0] for v in res.values()) / len(res)
        detail = "  ".join(f"{n}={res[n][0]:.2f}" for n in screens)
        print(f"  {tag:18s} {avg:6.3f}%   {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
