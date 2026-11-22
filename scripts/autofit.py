#!/usr/bin/env python3
"""Closed-loop auto-fit of the text of an existing page.

For every OCR run of a screen this tool

  1. finds the page element that renders that run,
  2. measures the ink of the run in the Figma export and in the render,
  3. corrects the font size (from the ink height ratio) and the position
     (from the ink offset), and
  4. writes the corrected values back into the page's own stylesheet.

Every step is measured, so a correction that makes a screen worse can be
detected and rolled back.

    python3 scripts/autofit.py v1-vip-membership-yearly
    python3 scripts/autofit.py v1-vip-membership-yearly --apply
    python3 scripts/autofit.py --all --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-autofit")


# --------------------------------------------------------------------- io --

def manifest() -> list[dict]:
    rows = []
    for folder, pref in (("v1raw", "v1"), ("v1raw73", "v73")):
        m = ROOT / "source" / folder / "screens" / "manifest.json"
        if not m.exists():
            continue
        for r in json.loads(m.read_text(encoding="utf-8")):
            slug = r["slug"]
            rows.append({
                "slug": slug,
                "page": r.get("page") or f"v1-{slug}.html",
                "src": ROOT / "source" / folder / "screens" / r["file"],
                "w": r["css"][0], "h": r["css"][1],
            })
    return rows


def css_path(page: str) -> Path:
    name = page[:-5]
    for pref in ("v1-", "v73-"):
        if name.startswith(pref):
            name = name[len(pref):]
            break
    return ROOT / "assets" / "v1" / f"{name}.css"


def load_runs(page: str) -> list[dict]:
    stem = page[:-5] if page.endswith(".html") else page
    p = ROOT / "analysis" / "ocr" / f"{stem}.tsv"
    if not p.exists():
        return []
    runs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            x0, y0, x1, y1 = (float(parts[i]) for i in range(4))
        except ValueError:
            continue
        runs.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": parts[5]})
    return runs


# ------------------------------------------------------------- page model --

TEXT_TAGS = "p|span|h[1-6]|div|li|td|th|label|a"


def parse_page(html: str) -> list[dict]:
    """Every element that carries text, with its class and inline style."""
    out = []
    pat = re.compile(
        r"<(?:(" + TEXT_TAGS + r"))\b([^>]*)>([^<]*)</", re.S)
    for m in pat.finditer(html):
        tag, attrs, text = m.group(1), m.group(2), m.group(3).strip()
        if not text:
            continue
        cm = re.search(r'class="([^"]*)"', attrs)
        sm = re.search(r'style="([^"]*)"', attrs)
        style = {}
        if sm:
            for prop in sm.group(1).split(";"):
                if ":" in prop:
                    k, v = prop.split(":", 1)
                    style[k.strip()] = v.strip()
        out.append({
            "tag": tag, "attrs": attrs, "text": text,
            "classes": cm.group(1).split() if cm else [],
            "style": style,
            "start": m.start(), "end": m.end(),
        })
    return out


def rules(css: str) -> list[tuple[str, str, int, int]]:
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        out.append((m.group(1).strip(), m.group(2), m.start(2), m.end(2)))
    return out


def decl(body: str, prop: str) -> str | None:
    m = re.search(r"(?:^|;)\s*%s\s*:\s*([^;]+)" % prop, body)
    return m.group(1).strip() if m else None


def num(v: str | None) -> float | None:
    if not v:
        return None
    m = re.match(r"-?[\d.]+", v)
    return float(m.group(0)) if m else None


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


# ------------------------------------------------------------- measuring --

def ink_box(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int,
            thr: int = 90) -> tuple[int, int, int, int] | None:
    h, w, _ = arr.shape
    x0 = max(0, x0); y0 = max(0, y0); x1 = min(w, x1); y1 = min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    reg = arr[y0:y1, x0:x1]
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    mask = np.abs(reg - bg).sum(axis=2) > thr
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)


def css_arrays(src: Path, shot: Path) -> tuple[np.ndarray, np.ndarray]:
    """Source and render, both at 1x css pixels."""
    si = Image.open(src).convert("RGB")
    s = np.array(si.resize((si.size[0] // 4, si.size[1] // 4), Image.LANCZOS)).astype(int)
    ri = Image.open(shot).convert("RGB")
    r = np.array(ri.resize((ri.size[0] // 2, ri.size[1] // 2), Image.LANCZOS)).astype(int)
    return s, r


def best_ink(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int,
             radius: int = 3):
    """Ink box of a region, searched a few pixels around it."""
    best = None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            box = ink_box(arr, x0 + dx - 1, y0 + dy - 1, x1 + dx + 1, y1 + dy + 1)
            if box is None:
                continue
            w = box[2] - box[0]
            h = box[3] - box[1]
            # prefer the box that fills the requested region best
            fill = (w * h) / max(1, (x1 - x0 + 2) * (y1 - y0 + 2))
            score = fill
            if best is None or score > best[0]:
                best = (score, box)
    return best[1] if best else None


# --------------------------------------------------------------- render --

def render(page: str, w: int, h: int) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    out_html = WORK / page
    out_html.write_text(html, encoding="utf-8")
    out = WORK / (page[:-5] + ".png")
    profile = WORK / f"profile-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files", "--force-device-scale-factor=2",
        "--virtual-time-budget=12000", f"--user-data-dir={profile}",
        f"--window-size={w},{h}", f"--screenshot={out}",
        f"file://{out_html}",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] no render for {page}")
    return out


def diff_pct(src: Path, shot: Path) -> float:
    si = Image.open(src).convert("RGB")
    ri = Image.open(shot).convert("RGB")
    if si.size != ri.size:
        ri = ri.resize(si.size, Image.LANCZOS)
    A = np.asarray(ri).astype(np.int16)
    B = np.asarray(si).astype(np.int16)
    d = np.abs(A - B).sum(axis=2)
    return float((d > 24).mean()) * 100


# ------------------------------------------------------------- the fixer --

def element_targets(page: str, css: str, html: str):
    """(element, css rule index) pairs for every positioned text element.

    An element is either absolutely positioned by an inline style (the
    competition-detail style) or by a class rule in the page stylesheet.
    """
    els = parse_page(html)
    rl = rules(css)
    # class -> (rule index, body)
    class_rule: dict[str, int] = {}
    for i, (sel, body, _s, _e) in enumerate(rl):
        if num(decl(body, "left")) is None or num(decl(body, "top")) is None:
            continue
        for c in re.findall(r"\.([\w-]+)", sel):
            class_rule.setdefault(c, i)

    out = []
    for el in els:
        if el["style"].get("left") and el["style"].get("top"):
            out.append((el, None))
            continue
        for c in el["classes"]:
            if c in class_rule:
                out.append((el, class_rule[c]))
                break
    return out, rl


def fit_page(spec: dict, apply: bool, rounds: int = 2) -> dict:
    page = spec["page"]
    html_p = ROOT / page
    css_p = css_path(page)
    if not html_p.exists() or not css_p.exists():
        return {"page": page, "skipped": "not built"}
    html = html_p.read_text(encoding="utf-8")
    css = css_p.read_text(encoding="utf-8")
    runs = load_runs(page)
    if not runs:
        return {"page": page, "skipped": "no OCR"}

    before = None
    for rnd in range(rounds):
        shot = render(page, spec["w"], spec["h"])
        s_arr, r_arr = css_arrays(spec["src"], shot)
        if before is None:
            before = diff_pct(spec["src"], shot)

        targets, rl = element_targets(page, css, html)
        used: set[int] = set()
        edits: list[tuple[int, int, str]] = []   # css body replacements
        html_edits: list[tuple[int, int, str]] = []  # inline style replacements

        for el, rule_i in targets:
            want = norm(el["text"])
            if not want:
                continue
            # find the OCR run that renders this text
            best = None
            for i, r in enumerate(runs):
                if i in used:
                    continue
                sim = SequenceMatcher(None, want, norm(r["text"])).ratio()
                if sim < 0.6:
                    continue
                if best is None or sim > best[0]:
                    best = (sim, i)
            if best is None:
                continue
            sim, i = best
            r = runs[i]
            sb = ink_box(s_arr, int(r["x0"]) - 2, int(r["y0"]) - 2,
                         int(r["x1"]) + 2, int(r["y1"]) + 2)
            rb = best_ink(r_arr, int(r["x0"]) - 2, int(r["y0"]) - 2,
                          int(r["x1"]) + 2, int(r["y1"]) + 2)
            if sb is None or rb is None:
                continue
            sh = sb[3] - sb[1]
            rh = rb[3] - rb[1]
            if sh < 5 or rh < 5:
                continue
            used.add(i)

            dL = sb[0] - rb[0]
            dT = sb[1] - rb[1]
            ratio = sh / rh

            if rule_i is not None:
                _sel, body, bs, be = rl[rule_i]
                fs = num(decl(body, "font-size"))
                if fs is None:
                    continue
                new_fs = fs * ratio
                if abs(new_fs - fs) < 0.35:
                    new_fs = fs
                else:
                    new_fs = round(new_fs, 2)
                nb = re.sub(r"font-size:\s*[^;]+", f"font-size: {new_fs}px", body)
                left = num(decl(nb, "left"))
                top = num(decl(nb, "top"))
                if left is not None:
                    nb = re.sub(r"left\s*:\s*[^;]+", f"left: {round(left + dL, 2)}px", nb)
                if top is not None:
                    nb = re.sub(r"top\s*:\s*[^;]+", f"top: {round(top + dT, 2)}px", nb)
                edits.append((bs, be, nb))
            else:
                st = el["style"]
                fs = num(st.get("font-size"))
                if fs is None:
                    continue
                new_fs = fs * ratio
                if abs(new_fs - fs) >= 0.35:
                    st = dict(st)
                    st["font-size"] = f"{round(new_fs, 2)}px"
                if "left" in st:
                    st["left"] = f"{round(num(st['left']) + dL, 2)}px"
                if "top" in st:
                    st["top"] = f"{round(num(st['top']) + dT, 2)}px"
                style = ";".join(f"{k}: {v}" for k, v in st.items())
                html_edits.append((el["start"], el["end"],
                                   el["attrs"] + f' style="{style}">'
                                   + el["text"] + "</"))

        if not edits and not html_edits:
            break

        for s, e, nb in sorted(edits, reverse=True):
            css = css[:s] + nb + css[e:]
        if html_edits:
            new_html = html
            for s, e, frag in sorted(html_edits, reverse=True):
                new_html = new_html[:s] + frag + new_html[e:]
            html = new_html

        if not apply:
            return {"page": page, "dry": True, "rounds": rnd + 1}
        css_p.write_text(css, encoding="utf-8")
        html_p.write_text(html, encoding="utf-8")

    shot = render(page, spec["w"], spec["h"])
    after = diff_pct(spec["src"], shot)
    return {"page": page, "before": round(before, 2), "after": round(after, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=[])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()

    wanted = set()
    for p in args.pages:
        wanted.add(p if p.endswith(".html") else p + ".html")

    specs = [s for s in manifest()
             if (not wanted or s["page"] in wanted)
             and (ROOT / s["page"]).exists()]

    for spec in specs:
        res = fit_page(spec, args.apply, args.rounds)
        if "skipped" in res:
            print(f"[skip] {res['page']}: {res['skipped']}")
            continue
        if res.get("dry"):
            print(f"[dry ] {res['page']}")
            continue
        delta = res["after"] - res["before"]
        flag = "OK " if delta <= 0 else "WORSE"
        print(f"[{flag}] {res['page']:34s} {res['before']:6.2f}% -> "
              f"{res['after']:6.2f}%  ({delta:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
