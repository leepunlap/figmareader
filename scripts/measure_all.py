#!/usr/bin/env python3
"""
Measure every built screen in a private work directory.

scripts/measure_v1.py renders into /tmp/figma-render, which the background
workers also use, so two agents measuring the same screen at the same time
can read each other's screenshot.  This tool keeps its own directory, so it
is safe to run while the workers are still going.

  python3 scripts/measure_all.py                 # every built screen
  python3 scripts/measure_all.py v1-home v1-play # only some

Writes analysis/v1-diff.json, the same file the gallery and the README read.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("MEASURE_WORK", "/tmp/measure-all"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = ROOT / "analysis/v1-diff.json"
ROW = re.compile(r"^(\S+)\s+\(\d+,\s*\d+\)\s+\(\d+,\s*\d+\)\s+([\d.]+)%")

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import SCREENS, WIDTHS, HEIGHTS  # noqa: E402


def prepare(page: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    out = WORK / page
    out.write_text(html, encoding="utf-8")
    return out


def shoot(page: str, height: int, width: int, scale: int = 2) -> Path:
    out = WORK / page.replace(".html", ".png")
    profile = WORK / f"profile-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=12000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://%s" % (WORK / page),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot: {res.stderr[-800:]}")
    return out


def compare(render: Path, source: Path) -> float:
    a = Image.open(render).convert("RGB")
    b = Image.open(source).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    A = np.asarray(a).astype(np.int16)
    B = np.asarray(b).astype(np.int16)
    d = np.abs(A - B).sum(axis=2)
    return float((d > 24).mean() * 100)


def main() -> int:
    names = sys.argv[1:] or sorted(SCREENS)
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    done = []
    for name in names:
        spec = SCREENS.get(name)
        if not spec or not (ROOT / spec["page"]).exists():
            continue
        try:
            prepare(spec["page"])
            shot = shoot(spec["page"], HEIGHTS[name],
                         width=WIDTHS.get(name, 390))
            pct = compare(shot, ROOT / spec["source"])
        except Exception as exc:  # noqa: BLE001
            print(f"{name:34s} ERROR {exc}")
            continue
        data[name] = round(pct, 2)
        done.append(pct)
        flag = "  <<<" if pct > 6.0 else ""
        print(f"{name:34s} {pct:6.2f}%{flag}", flush=True)
    known = set(SCREENS)
    for k in [k for k in data if k not in known]:
        del data[k]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")
    over = sorted(((v, k) for k, v in data.items() if v > 6.0), reverse=True)
    print(f"\n{len(done)} measured  mean {sum(done)/max(len(done),1):.2f}%  "
          f"over 6%: {len(over)}")
    for v, k in over:
        print(f"   {v:6.2f}%  {k}")


if __name__ == "__main__":
    raise SystemExit(main())
