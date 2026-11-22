#!/usr/bin/env python3
"""
Snap every <img> in a screen onto integer device pixels.

Why
---
The verifier compares the Chrome render (captured at device scale 2) with the
4x Figma export downsampled to 2x with PIL LANCZOS.  If an <img> sits on a
fractional device pixel, Chrome resamples it with its own filter and the
photo region ends up ~33-50% different.  If the image is placed on integer
device pixels and the asset is cropped from the very same 2x raster the
verifier uses, Chrome draws it 1:1 and the region matches to ~1%.

So for every image we:
  1. ask the browser where it actually lands (device pixels),
  2. round that position to integer device pixels,
  3. re-crop the asset from the 2x source at exactly that rectangle,
  4. nudge the <img> with a relative offset so it really lands there.

Usage:
  python3 scripts/snap_photos.py lion-03
  python3 scripts/snap_photos.py lion-03 --dry-run
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-snap")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ANNOTATE = """
<script>
window.addEventListener('load', function () {
  var out = [];
  var imgs = document.querySelectorAll('img');
  for (var i = 0; i < imgs.length; i++) {
    var r = imgs[i].getBoundingClientRect();
    out.push([i, r.left, r.top, r.width, r.height,
              imgs[i].getAttribute('src') || ''].join('|'));
  }
  var d = document.createElement('div');
  d.id = '__snap__';
  d.textContent = out.join('\\n');
  document.body.appendChild(d);
});
</script>
"""


def source2x(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if im.width % 4 == 0 and im.width // 4 in (390, 402):
        return im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    return im


def probe_rects(html: Path) -> list[dict]:
    """Render the page and read back every <img>'s CSS rect."""
    WORK.mkdir(parents=True, exist_ok=True)
    probe = WORK / (html.stem + "-probe.html")
    body = html.read_text(encoding="utf-8")
    body = body.replace("<body>", '<body class="render">')
    body = body.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    body = body.replace("</body>", ANNOTATE + "</body>")
    probe.write_text(body, encoding="utf-8")

    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files", "--force-device-scale-factor=2",
        "--virtual-time-budget=8000", "--user-data-dir=%s/profile" % WORK,
        "--dump-dom", "file://%s" % probe,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    m = re.search(r'<div id="__snap__">(.*?)</div>', res.stdout, re.S)
    if not m:
        print("[error] could not read image rects from the rendered page")
        return []
    rows = []
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        i, l, t, w, h, src = parts[:6]
        rows.append({
            "i": int(i), "left": float(l), "top": float(t),
            "w": float(w), "h": float(h), "src": src,
        })
    return rows


def snap_one(html_path: Path, rows: list[dict], src2: Image.Image,
             dry: bool) -> list[str]:
    """Rewrite the html so every image lands on integer device pixels."""
    body = html_path.read_text(encoding="utf-8")
    notes = []
    made = []
    edits: list[tuple[int, int, str]] = []

    # collect the <img> tags in document order
    tags = list(re.finditer(r"<img\b[^>]*>", body, re.S))
    if len(tags) != len(rows):
        print(f"[warn] {html_path.name}: {len(tags)} <img> tags but {len(rows)} rects")

    for row in rows:
        if row["i"] >= len(tags):
            continue
        tag = tags[row["i"]]
        old = tag.group(0)
        m_src = re.search(r'src="([^"]*)"', old)
        if not m_src:
            continue
        src = m_src.group(1)
        if src.startswith("data:"):
            continue

        dx = row["left"] * 2.0
        dy = row["top"] * 2.0
        dw = row["w"] * 2.0
        dh = row["h"] * 2.0

        sx = int(round(dx))
        sy = int(round(dy))
        iw = max(1, int(round(dw)))
        ih = max(1, int(round(dh)))

        offx = (sx - dx) / 2.0
        offy = (sy - dy) / 2.0

        moved = (abs(offx) > 0.01 or abs(offy) > 0.01 or
                 abs(iw - dw) > 0.01 or abs(ih - dh) > 0.01)
        if not moved:
            notes.append(f"  img#{row['i']} {src}: already aligned "
                         f"dev=({dx:.1f},{dy:.1f}) {dw:.1f}x{dh:.1f}")
            continue

        # crop the asset from the same 2x raster the verifier uses
        stem = Path(src).stem
        out = ROOT / "assets/lion" / f"{html_path.stem}-{row['i']}-{stem}-snap.png"
        crop = src2.crop((sx, sy, min(sx + iw, src2.width),
                           min(sy + ih, src2.height)))
        # A page-level scrim (a dim overlay above the sheet) means the source
        # crop is already darkened; replacing the undimmed asset with it would
        # darken the photo twice.  Skip those.
        old = ROOT / src
        if old.exists():
            try:
                prev = np.asarray(Image.open(old).convert("RGB")).astype(float)
                if prev.shape[:2] == crop.shape[:2]:
                    if prev.mean() - crop.mean() > 12:
                        notes.append(f"  img#{row['i']} {src}: SKIPPED — the source "
                                     f"crop is dimmed by a scrim ({prev.mean():.0f} "
                                     f"vs {crop.mean():.0f})")
                        continue
            except Exception:
                pass
        if not dry:
            crop.save(out)
            made.append(str(out.relative_to(ROOT)))

        new_tag = old
        new_tag = re.sub(r'src="[^"]*"', 'src="%s"' % out.relative_to(ROOT).as_posix(),
                         new_tag, count=1)
        style = ("position:relative;left:%.3fpx;top:%.3fpx;width:%dpx;height:%dpx;"
                 % (offx, offy, iw / 2.0, ih / 2.0))
        if re.search(r'style="', new_tag):
            new_tag = re.sub(r'style="([^"]*)"',
                             lambda mm: 'style="%s%s"' % (mm.group(1), style),
                             new_tag, count=1)
        else:
            new_tag = new_tag.replace("<img", '<img style="%s"' % style, 1)
        edits.append((tag.start(), tag.end(), new_tag))
        notes.append(f"  img#{row['i']} {src}: dev ({dx:.1f},{dy:.1f}) {dw:.1f}x{dh:.1f}"
                     f" -> ({sx},{sy}) {iw}x{ih}  offset({offx:+.2f},{offy:+.2f})")

    # apply the tag rewrites back to front so earlier offsets stay valid
    for start, end, new_tag in reversed(edits):
        body = body[:start] + new_tag + body[end:]
    if not dry and made:
        html_path.write_text(body, encoding="utf-8")
    return notes, made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screens", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--source-dir", default="source/lion")
    args = ap.parse_args()

    from render_check import SCREENS  # local import keeps the manifest in one place

    for name in args.screens:
        if name not in SCREENS:
            print(f"[skip] unknown screen {name}")
            continue
        spec = SCREENS[name]
        html_path = ROOT / spec["page"]
        src_path = ROOT / spec["source"]
        if not html_path.exists():
            print(f"[skip] {name}: {html_path.name} not built yet")
            continue
        print(f"== {name} ({html_path.name})")
        rows = probe_rects(html_path)
        if not rows:
            continue
        src2 = source2x(src_path)
        notes, made = snap_one(html_path, rows, src2, args.dry_run)
        for n in notes:
            print(n)
        for m in made:
            print(f"  wrote {m}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
