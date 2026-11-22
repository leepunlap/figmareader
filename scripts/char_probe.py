#!/usr/bin/env python3
"""Measure the per-character advance Chrome gives a CJK string.

Why: the Figma exports lay CJK text out in PingFang SC, whose fullwidth
punctuation gets a *different* advance than the same glyph in Noto Sans TC.
That mismatch makes a rendered line drift sideways relative to the source, so
every glyph after the first punctuation lands on the wrong pixel.

This probe renders a string in the real page font stack and reports, for each
character, the x offset Chrome gave it.  Comparing that against the source's
ink positions tells us which characters need an explicit advance override.

  python3 scripts/char_probe.py --text "手捏創作班（1.5小時）：使用泥版" --size 14
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/v1/{fonts}">
<style>
 html,body {{ margin:0; padding:0; background:#fff; }}
 .probe {{ position:absolute; left:0; top:0; white-space:pre;
           font-family:'Noto Sans TC Latin','Noto Sans TC',sans-serif;
           font-size:{size}px; font-weight:{weight}; line-height:1;
           color:#000; }}
 {extra}
</style></head>
<body>
<span class="probe" id="p">{text}</span>
<pre id="out"></pre>
<script>
(function(){{
  var el = document.getElementById('p');
  var t  = el.firstChild;
  var out = [];
  for (var i = 0; i < t.length; i++) {{
    var r = document.createRange();
    r.setStart(t, i); r.setEnd(t, i + 1);
    var rects = r.getClientRects();
    var x = null, w = null;
    for (var j = 0; j < rects.length; j++) {{
      if (x === null) x = rects[j].left;
      w = rects[j].width;
    }}
    out.push({{i: i, ch: t.data[i], x: x, w: w}});
  }}
  document.getElementById('out').textContent = 'JSONSTART' + JSON.stringify(out) + 'JSONEND';
}})();
</script>
</body></html>
"""


def probe(text: str, size: float, weight: int, fonts: str, extra: str = "") -> list[dict]:
    WORK.mkdir(parents=True, exist_ok=True)
    page = WORK / "_charprobe.html"
    page.write_text(
        TEMPLATE.format(text=text, size=size, weight=weight, fonts=fonts, extra=extra),
        encoding="utf-8",
    )
    profile = WORK / f"probe-profile-{__import__('os').getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--allow-file-access-from-files",
        "--virtual-time-budget=8000",
        "--user-data-dir=%s" % profile,
        "--dump-dom",
        "file://%s" % page,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    shutil.rmtree(profile, ignore_errors=True)
    m = re.search(r"JSONSTART(\[.*?\])JSONEND", res.stdout, re.S)
    if not m:
        print(res.stdout[-3000:], res.stderr[-2000:], file=sys.stderr)
        raise SystemExit("[error] char probe produced no result")
    return json.loads(m.group(1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--size", type=float, default=14)
    ap.add_argument("--weight", type=int, default=400)
    ap.add_argument("--fonts", default="competition-detail-closed-fonts.css")
    ap.add_argument("--extra", default="")
    args = ap.parse_args()

    rows = probe(args.text, args.size, args.weight, args.fonts, args.extra)
    prev = None
    print("%-3s %-4s %8s %8s" % ("#", "ch", "x", "advance"))
    for r in rows:
        adv = None if (prev is None or r["x"] is None) else round(r["x"] - prev, 3)
        print("%-3d %-4s %8s %8s" % (r["i"], r["ch"], r["x"], adv))
        prev = r["x"]


if __name__ == "__main__":
    main()
