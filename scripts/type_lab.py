#!/usr/bin/env python3
"""
Type laboratory — identify which font family + weight reproduces the design's
Chinese type most faithfully.

Two metrics are computed for every candidate:

  coverage : ink pixels / area of the tight glyph bounding box.
             -> how heavy the strokes are.
  shape    : the tight glyph box, normalised to 64x64, compared pixel-wise
             against the same normalisation of the Figma export.
             -> how similar the glyph outlines are (size-independent).

  python3 scripts/type_lab.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-type-lab")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCALE = 2

# key, screen, source css rect, font-size css, weight, colour, text
SAMPLES = [
    ("card-desc",  "list-020", (93, 479, 260, 20), 12, 400, "#7089a8", "指出自己的一個身體部位。"),
    ("card-desc2", "list-020", (93, 549, 260, 20), 12, 400, "#7089a8", "用指認、拿取或說話表達一個喜好。"),
    ("card-title", "list-020", (93, 458, 200, 20), 15, 700, "#29262d", "摸摸我的小臉"),
    ("card-title2","list-020", (93, 528, 220, 20), 15, 700, "#29262d", "今天想玩哪一個"),
    ("progress",   "list-020", (20, 360, 120, 20), 13, 400, "#7089a8", "目前進度"),
    ("section",    "list-020", (49, 408, 180, 26), 18, 700, "#000000", "7 天任務清單"),
    ("caption",    "home",     (100, 592, 200, 22), 13, 400, "#78727d", "從認識自己，練習表達與接納。"),
    ("card-text",  "home",     (69, 658, 140, 40), 13, 400, "#77717c", "指出身體部位及一項喜好。"),
    ("section-lede","home",    (82, 460, 290, 56), 14, 400, "#64606a", "在家長陪伴下，認識自己的身體與喜好，嘗試"),
]

CANDIDATES = [
    ("Noto300", '"Noto Sans TC", sans-serif', 300),
    ("Noto400", '"Noto Sans TC", sans-serif', 400),
    ("Noto500", '"Noto Sans TC", sans-serif', 500),
    ("Noto600", '"Noto Sans TC", sans-serif', 600),
    ("Noto700", '"Noto Sans TC", sans-serif', 700),
    ("PingFang", '"PingFang TC", sans-serif', 400),
    ("PingFangSB",'"PingFang TC", sans-serif', 500),
    ("Hiragino", '"Hiragino Sans CNS", sans-serif', 400),
    ("Heiti",    '"Heiti TC", sans-serif', 400),
]

ROW_PITCH = 30


# ------------------------------------------------------------------ measuring

def ink_mask(patch: np.ndarray, bg: np.ndarray | None = None) -> np.ndarray:
    if bg is None:
        flat = patch.reshape(-1, 3)
        keys = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2].astype(np.int32)
        vals, counts = np.unique(keys, return_counts=True)
        k = int(vals[np.argmax(counts)])
        bg = np.array([(k >> 16) & 0xFF, (k >> 8) & 0xFF, k & 0xFF])
    return np.abs(patch - bg).sum(axis=2) > 26


def tight(mask: np.ndarray):
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    return mask[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]


def norm(box: np.ndarray, size: int = 64) -> np.ndarray:
    """normalise a glyph box to size x size, ink = 1.0"""
    img = Image.fromarray((box * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)
    return np.asarray(img).astype(np.float32) / 255.0


def load_scaled(path: Path, scale: int) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    if img.width != 390 * scale:
        img = img.resize((390 * scale, round(img.height * 390 * scale / img.width)), Image.LANCZOS)
    return np.asarray(img).astype(np.int16)


# ------------------------------------------------------------------ lab page

def build_lab():
    rows = []
    y = 0
    for key, _screen, _rect, size, weight, color, text in SAMPLES:
        for name, fam, cand_w in CANDIDATES:
            w = cand_w if name.startswith("Noto") else weight
            rows.append((key, name, size, w, color, text))
            rows.append(None)
            rows.append(None)
    # rebuild with correct pitch (one row per candidate, pitch accounts for size)
    rows = []
    y = 0
    for key, _screen, _rect, size, weight, color, text in SAMPLES:
        for name, fam, cand_w in CANDIDATES:
            w = cand_w if name.startswith("Noto") else weight
            rows.append((key, name, size, w, color, text, y))
            y += ROW_PITCH
    blocks = []
    for key, name, size, w, color, text, top in rows:
        fam = dict((c[0], c[1]) for c in CANDIDATES)[name]
        blocks.append(
            f'<div class="row" style="top:{top}px"><span style="font-size:{size}px;'
            f'font-weight:{w};font-family:{fam};color:{color};">{text}</span></div>'
        )
    html = (
        "<!DOCTYPE html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        "<link rel='stylesheet' href='assets/fonts/fonts.css'>"
        "<style>html,body{margin:0;padding:0;background:#ffffff;color:#29262d}"
        ".row{position:absolute;left:10px;height:26px;white-space:nowrap;line-height:26px}"
        "</style></head><body>" + "".join(blocks) + "</body></html>"
    )
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "lab.html"
    path.write_text(html, encoding="utf-8")
    return path, rows


def shoot(path: Path, height: int) -> Path:
    out = WORK / "lab.png"
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions", "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % SCALE,
        "--virtual-time-budget=12000",
        "--user-data-dir=%s/profile" % WORK,
        "--window-size=390,%d" % height,
        "--screenshot=%s" % out,
        "file://%s" % path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if not out.exists():
        print(res.stdout[-1500:], res.stderr[-1500:])
        raise SystemExit("chrome produced no screenshot")
    return out


def main() -> int:
    path, rows = build_lab()
    height = len(rows) * ROW_PITCH + 40
    png = shoot(path, height)
    lab = load_scaled(png, SCALE)
    print(f"lab image {lab.shape}")

    # ---- source references
    refs = {}
    for key, screen, rect, size, weight, color, text in SAMPLES:
        src = load_scaled(ROOT / "source" / f"{screen}.png", 4)
        x, y, w, h = rect
        patch = src[y * 4:(y + h) * 4, x * 4:(x + w) * 4]
        mask = ink_mask(patch)
        box = tight(mask)
        assert box is not None, key
        refs[key] = {
            "cov": float(box.mean()) * 100,
            "shape": norm(box),
            "size": (box.shape[1], box.shape[0]),
        }

    # ---- candidates
    results = {}
    for key, name, size, w, color, text, top in rows:
        patch = lab[top * SCALE:(top + 26) * SCALE, 0:390 * SCALE]
        mask = ink_mask(patch)
        box = tight(mask)
        if box is None:
            continue
        cand = {"cov": float(box.mean()) * 100, "shape": norm(box)}
        results.setdefault(key, {})[name] = cand

    print(f"\n{'sample':14s} {'source cov':>10s}   candidates (cov delta / shape dist)")
    shape_scores = {c[0]: [] for c in CANDIDATES}
    cov_scores = {c[0]: [] for c in CANDIDATES}
    for key, _s, _r, _sz, _w, _c, _t in SAMPLES:
        ref = refs[key]
        print(f"\n  {key}  source {ref['cov']:.2f}%")
        for name, _f, _w in CANDIDATES:
            cand = results.get(key, {}).get(name)
            if not cand:
                continue
            dshape = float(np.abs(cand["shape"] - ref["shape"]).mean()) * 100
            dcov = cand["cov"] - ref["cov"]
            shape_scores[name].append(dshape)
            cov_scores[name].append(abs(dcov))
            print(f"     {name:12s} cov {cand['cov']:6.2f}% ({dcov:+5.2f})   shape {dshape:5.1f}")

    print("\n\n=== overall (mean over samples) ===")
    print(f"  {'candidate':12s} {'|cov delta|':>12s} {'shape dist':>11s} {'combined':>9s}")
    scored = []
    for name, _f, _w in CANDIDATES:
        mc = float(np.mean(cov_scores[name]))
        ms = float(np.mean(shape_scores[name]))
        scored.append((name, mc, ms, mc + ms * 0.35))
    for name, mc, ms, comb in sorted(scored, key=lambda r: r[3]):
        print(f"  {name:12s} {mc:11.2f}pp {ms:10.1f} {comb:8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
