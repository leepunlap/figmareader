# Building a v1.0 screen — the worker brief

You are rebuilding **one** Figma screen as plain static HTML + CSS, in
`/Users/blee/src/figma`.

Read `WORKER-BRIEF.md` (this file) fully before you touch anything, then read
`styles-v1.css` (the shared design system) and these two for the
*construction* conventions — they use exactly the same artboard technique:

* `lion-01.html` + `styles-lion.css` — a phone screen built the same way
* `home.html` + `styles.css` — the Tasks page screen

Neither is the v1.0 design — take the palette, metrics and layout from your
own source PNG, and the *technique* from those files.

## What "done" means

1. A file `v1-<slug>.html` in the workspace root — the artboard is
   `<div class="v1">` sized to the source (e.g. `style="width:390px;height:844px"`).
2. A file `assets/v1/<slug>.css` with **everything specific to this screen**.
   The shared `styles-v1.css` holds the design system; your file may override
   any of it but must not duplicate it.
3. Every image the page shows is a real file in `assets/v1/`, cropped from the
   source PNG (see below).
4. The page links, in this order:
   ```html
   <link rel="stylesheet" href="assets/fonts/fonts.css">
   <link rel="stylesheet" href="styles-v1.css">
   <link rel="stylesheet" href="assets/v1/<slug>.css">
   <link rel="stylesheet" href="assets/v1/<slug>-fonts.css">
   ```
   The per-page font subset must be **last** — same family + weight means the
   last declaration wins.
5. **No JavaScript in the page.** No framework, no build step, no CDN.
   Everything is static HTML + CSS.
6. All text is real HTML text (not images). Multi-line copy uses explicit `<br>`.

## The source of truth

Your screen's source PNG is
`source/v1raw/screens/<slug>.png` (or `source/v1raw73/screens/<slug>.png`).

It is the **4× Figma export**: 1560 px wide = 390 css px. So

> **css px = source px ÷ 4**

`source/v1raw/screens/manifest.json` lists every screen with its
`slug`, the original Chinese `title` and its `css` size.

### READ THE OCR FIRST — it has the real Chinese copy

`analysis/ocr/<slug>.md` is a **macOS Vision OCR** dump of your screen: every
recognised text run with its exact 1× css bounding box and the confidence.

```
| x0 | y0 | x1 | y1 | conf | text |
| 20 | 250 | 196 | 273 | 1.00 | 中國語文菁英計劃 |
| 35 | 284 | 206 | 302 | 0.50 | 報名截止：4月22日22:00 |
```

**Use the OCR text verbatim.** The AI vision spec (`analysis/vision/<slug>.md`)
is good at *layout* but it **hallucinates Chinese copy** — it will happily
invent plausible-looking paragraphs that are not in the design, and every wrong
glyph costs you real diff. The OCR is ground truth for the strings.

Use the two sources together:

| you need | use |
|---|---|
| the exact Chinese/latin string | `analysis/ocr/<slug>.md` |
| where the text sits, its box | `analysis/ocr/<slug>.md` (x0,y0,x1,y1) |
| colours, radii, card layout, image boxes | `analysis/vision/<slug>.md` |
| anything the OCR missed (tiny/light text) | measure the source pixels |

`analysis/ocr/<slug>.tsv` is the same data without the table, if you prefer
to parse it.

If your screen's OCR file is missing, make it:

```bash
python3 scripts/ocr_screen.py v1-<slug>        # -> analysis/ocr/<slug>.md
```

### THE AUTO-FIT PIPELINE — let the scripts place the text for you

Hand-writing the CSS for every text run is slow and the font is not PingFang,
so the glyphs never match the export exactly.  Three scripts do the work for
you:

```bash
cd /Users/blee/src/figma

# 1. measure every OCR run in the 4x export and fit a font size + position
#    that reproduces its ink box exactly in the self-hosted Noto Sans TC
python3 scripts/ocrfit.py v1-<slug>
#    -> analysis/ocr/<slug>-fit.json   (per run: fs, left, top, colour)
#    and a ready-to-paste list of <p> elements on stdout

# 2. describe the screen: bands, card rectangles, ink colours
python3 scripts/blueprint.py v1-<slug> --bands --cards

# 3. check what the render got wrong, run by run
python3 scripts/fitcmp.py v1-<slug>
```

`scripts/genpage.py` assembles the whole page from a JSON spec: the spec holds
the structural markup (images, cards, buttons) plus the OCR runs to skip, and
`genpage.py` writes the HTML with every remaining run already positioned:

```bash
python3 scripts/genpage.py specs/<name>.json    # specs/ holds worked examples
```

**The font subset matters.**  `assets/fonts/fonts.css` only contains the
glyphs of the screens that were built before it was generated.  Always build
the per-page subset *after* the OCR exists and link it **last**:

```bash
python3 scripts/fetch_v1_fonts.py v1-<slug> --out assets/v1/<slug>-fonts.css
```

If a page links no subset at all, Chrome silently falls back to the system
PingFang and the glyph widths stop matching the export.

### Measuring — always measure, never guess

```bash
cd /Users/blee/src/figma

# the pixel diff of your screen against the source (the number that matters)
python3 scripts/render_check.py v1-<slug>

# A LAYOUT SPEC WRITTEN BY A VISION MODEL — run this first for every screen.
# It reads the 4x export, downscales it to 1x, and asks the vision connector
# for the exact text, positions, colours, radii and image boxes.
python3 scripts/vision_spec.py v1-<slug>      # -> analysis/vision/v1-<slug>.md
# The 1x preview it leaves at /tmp/<slug>-1x.png can be cropped for detail.

# the OCR text dump (ground truth for the copy)  <-- READ THIS
python3 scripts/ocr_screen.py v1-<slug>        # -> analysis/ocr/v1-<slug>.md

# ink bounding box of a rectangle in the source (find a text block's extent)
python3 scripts/inkbox.py v1-<slug> --rect 39,798,307,14

# try CSS overrides and keep only what lowers the diff
python3 scripts/sweep.py v1-<slug> --cand ".card__title{font-size:15.5px}"

# ...or measure one small region, far more sensitive than the page metric
python3 scripts/sweep.py v1-<slug> --region 30,120,300,40 \
    --cand ".card__title{font-size:15.5px}"

# per-region diff, to find where the error actually is
python3 scripts/diff_regions.py v1-<slug> --grid 30

# horizontal drift of one text row (source vs render)
python3 scripts/drift_scan.py v1-<slug>

# side-by-side crop of source and render
python3 scripts/compare.py v1-<slug> --y0 130 --y1 290 --scale 1.25
```

A **region-scoped** measurement (`--region`) is far more sensitive than the
page metric: a 25 % font-size change on a 45×11 px label moves the page metric
by only 0.02 %. Use the region metric for small elements and the page metric
for the final check.

**Always A/B a change**: render, measure, and keep the change only if the diff
drops. Never change something you have not measured.

### Target

**≤ 6 % differing pixels** at 2× for a finished screen. (Tasks page: 3.1–4.1 %.
Lion page: 3.8–9.2 %.) The residual is dominated by glyph rasterisation — the
exact Figma typeface cannot be recovered from a raster export — so do not chase
the last 2 %.

## Cutting out images

Photos and illustrations must be cropped from the 4× source and must land on
**integer device pixels** (i.e. crop at multiples of 4, then place at a
position that is a multiple of 4 css px... actually: the crop box must have
sides that are multiples of 4, so the image lands cleanly).

```bash
# crop a region of the source (coordinates are in 4x source pixels)
python3 scripts/extract.py source/v1raw/screens/<slug>.png \
    --rect 40,120,1560,900 --out assets/v1/<slug>-hero.png --prescale 2
```

`--prescale 2` writes the crop at 2× (half the source resolution) so the page
loads it at the right CSS size and the file stays small. Keep it if the source
is 4× — a 1:1 crop of a 4× export at 2× display size is what the rest of the
project does.

Simple icons (chevrons, arrows, the small glyphs in the tab bar) should be
**inline SVG** rather than cropped bitmaps.

## Typography

The design's CJK face is a rounded/grotesque that is not recoverable from a
raster export. The project uses:

* **CJK** — `Noto Sans TC` (the per-page subset in `assets/v1/<slug>-fonts.css`
  carries exactly the glyphs your page needs).
* **Latin** — `Arimo` (Arial metrics) or `Poppins` (geometric) — the v1 design
  sets its big numerals and English headings in a geometric face, body Latin in
  a grotesque. Pick per element and measure.

Primary ink is **pure black `#000000`**, not `#181b17`.

Generate your page's font subset when the HTML is in place:

```bash
python3 scripts/fetch_v1_fonts.py v1-<slug> --out assets/v1/<slug>-fonts.css
```

It writes `assets/v1/<slug>-fonts.css` and inserts the `<link>` for you.
**Always pass `--out`** — without it the script derives the name from the HTML
file name, which would give `v1-<slug>-fonts.css` and leave a stale duplicate
`<link>` in the page.

## The shape of a page

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=390, initial-scale=1">
<title>活動 · 比賽</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/<slug>.css">
<link rel="stylesheet" href="assets/v1/<slug>-fonts.css">
</head>
<body>
  <div class="v1" style="width:390px;height:844px">
    ...
  </div>
</body>
</html>
```

Children of `.v1` are **absolutely positioned** (`.v1 * { position:absolute }`),
so give each element an explicit `left`/`top` in css px, measured from the
source ÷ 4.

## Rules that save a lot of time

* **Measure, don't eyeball.** Every position comes from the source pixels.
* **Text is text.** Never bake a text string into an image.
* **Colour**: sample it from the source PNG
  (`python3 scripts/inkbox.py ...` or a tiny PIL snippet), don't guess.
* **Sub-pixel positions**: Chrome snaps a text origin to 1/4 css px at 4× and
  1/2 css px at 2×. Tune positions to the nearest half pixel and accept the
  rest — it is glyph shape, not placement.
* **Fonts**: link the per-page subset **last**.
* Do **not** edit `styles-v1.css`, `styles.css`, `styles-lion.css`,
  `assets/fonts/fonts.css`, `scripts/*`, or any file that is not yours.
  If you need a shared rule changed, say so in your final report instead.
* Your screen's files are `v1-<slug>.html`, `assets/v1/<slug>.css`,
  `assets/v1/<slug>-fonts.css` and any `assets/v1/<slug>-*.png` you create.
  **Do not touch another screen's files** — several workers run in parallel.

## The `v1.0 最初版 - (7.3)` page — the `v73-*` screens

The Figma file has a second v1 page, `v1.0 最初版 - (7.3)`. It was exported as
four big section images and segmented locally into **65 individual screens**,
which live in `source/v1raw73/screens/` with their own manifest at
`source/v1raw73/screens/manifest.json`.

Those screens are named `v73-<section>-<nn>` — the sections are `activity`,
`mine`, `competition` and `competition2`.

### Naming and file ownership for a 7.3 screen

| what | name |
|---|---|
| source PNG | `source/v1raw73/screens/v73-<slug>.png` |
| page | `v73-<slug>.html`  ← **not** `v1-…` |
| screen CSS | `assets/v1/v73-<slug>.css` |
| font subset | `assets/v1/v73-<slug>-fonts.css` |
| images | `assets/v1/v73-<slug>-*.png` |

The 7.3 screens are the *earliest* version of the same product, so most of them
are a simpler cousin of a screen on the big `v1.0` page. The manifest row
carries a `match` field naming that screen:

```bash
python3 - <<'PY'
import json
for r in json.load(open('source/v1raw73/screens/manifest.json')):
    print(r['slug'], r['css'], r['title'], '->', r.get('match'), r.get('score'))
PY
```

**Start from the matched screen.** Copy its `v1-<match>.html` and
`assets/v1/<match>.css` as your starting point, then strip what the 7.3 design
does not have. That is far faster and far more accurate than building from
scratch. Rows with no `match` are unique to the 7.3 page — build those from the
source PNG alone.

The matched screen is a *reference*, not a copy: the 7.3 design differs in
detail (older layouts, fewer sections, different accents), so verify every
element against your own source PNG.

### Measuring a 7.3 screen

Everything is the same, only the name changes:

```bash
python3 scripts/vision_spec.py v73-<slug>     # the layout spec (run this first)
python3 scripts/render_check.py v73-<slug>
python3 scripts/sweep.py v73-<slug> --cand ".card__title{font-size:15.5px}"
python3 scripts/compare.py v73-<slug> --y0 130 --y1 290 --scale 1.25
python3 scripts/fetch_v1_fonts.py v73-<slug>
```

`scripts/fetch_v1_fonts.py` takes the page stem, so `v73-activity-01` works
as-is.

### Widths

The 7.3 artboards are **not all 390 css wide**. They are 375, 390, 402, 403 or
404. Always take the width from the manifest row's `css[0]` — never assume.

## Reporting

Finish with a short report:
* the final diff % per screen you built (from `render_check.py`),
* the font families you settled on,
* anything you could not reproduce and why,
* the exact files you created.
