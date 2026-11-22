# figmareader

A toolkit that reads a Figma design and reproduces it as **plain static HTML +
CSS** with extracted image assets. No JavaScript, no framework, no build step, no
CDN — open `index.html` and it runs.

This repository tracks the **tooling** (`scripts/`) and this knowledge/design
file. The generated pages, the raw Figma exports, the extracted assets and the
OCR analysis are intermediate artefacts and are excluded by `.gitignore`; they
are regenerated from the Figma export with the commands in *Regenerating* below.

## The project it was built for

Rebuilt from the Figma design as **plain static HTML + CSS** with extracted image
assets. No JavaScript, no framework, no build step, no CDN — open `index.html`
and it runs.

Four Figma pages are reproduced:

* **Tasks** — 4 artboards (home + three task-list states).
* **Lion** — 11 artboards (activity feed & filters, organisation feeds & filters,
  two organisation-detail pages, two event-detail pages, two chat screens).
* **v1.0** — 98 artboards, the largest page in the file (home, chat, competitions,
  play, schools, products, orders, calendar, notifications, membership, search,
  invites, profile).
* **v1.0 最初版 - (7.3)** — 65 artboards, the earliest version of the same product.

The two v1 pages live in `v1.html` and are built by parallel workers against a
shared design system (`styles-v1.css`); every screen also ships its own
per-page stylesheet and font subset.

## Repository layout

```
.gitignore          what is *not* tracked (see the header of the file)
README.md           this file — the knowledge + design record
scripts/            the whole toolchain
  render_check.py     render a screen in headless Chrome and diff it vs the export
  measure_v1.py       measure every built v1 screen  -> analysis/v1-diff.json
  gallery_v1.py       rebuild the v1 gallery page
  ocr_screen.py       macOS Vision OCR of a 4x export -> analysis/ocr/<slug>.md
  ocrfit.py           fit a typeface/size/weight/position to every OCR text run
  genpage.py          emit one screen's HTML + CSS from a fitted spec
  extract.py          crop a photo/illustration out of the 4x export
  fit_gradient2d.py   fit a multi-stop or angled gradient to a small PNG bitmap
  knockout.py         flood a near-white background out of a cut-out to alpha
  placealpha.py       alpha-aware placement of a cropped asset on a render
  vshift.py           align a screen's text to the source, inline only
  v73_clone.py        clone a 7.3 screen from its identical v1 twin
  v1_segment.py       segment the four whole-section 7.3 exports into 65 screens
  sbs.py              side-by-side source|render crop, for pixel hunting
  compare_lion.py     rebuild the Lion compare screen
  package*.py         zip + verify the delivery archive
  *.swift             macOS helpers (run them directly; they have a swift shebang)
```

### Pixel-budget tooling

Getting a screen under the 6 % pixel budget is measured work, so the loop is
scripted. The rule of thumb: **the export is the ground truth, the OCR text is
the ground truth for the strings, and every change is A/B measured.**

```
  render_check.py     render a screen in headless Chrome and pixel-diff it
  measure_v1.py       measure every built v1 screen -> analysis/v1-diff.json
  prerender.py        render + diff in a private work dir (safe while other
                      agents are working) and print the hottest bands
  bandfit.py          A/B a CSS override on a band of the screen; the override
                      is injected into the rendered copy, never into the file
  autotune.py         snap every text block to one font size, then align the
                      block vertically to the export — keeps the change only
                      when the page diff improves
  linesync.py         per OCR line: source ink box vs render ink box
  fixline.py          repair an OCR'd line and re-fit its font size
  inkprof.py          ink profile of a band: coverage, IoU, best dx/dy
  char_probe.py       measure the advance width of a string in the browser
  font_of.py          the ink width of one character in one typeface
  font_ab.py          typeface A/B on the OCR lines of a screen
  weightsweep.py      font-weight sweep (the override never touches the file)
  shiftsweep.py       uniform vertical nudge sweep
  triage.py           split a screen's diff into "text" and "other"
  aa_probe.py         compare the resampling/anti-aliasing hypotheses
```

The pipeline is one direction only:

```
Figma desktop export (4× PNG)
  -> source/…            raw exports
  -> ocr_screen.py       ground-truth strings (Vision OCR)
  -> ocrfit.py           per-run font, size, weight, position
  -> genpage.py          screen HTML + per-screen CSS + font subset
  -> extract.py          photos and illustrations cropped from the export
  -> render_check.py     Chrome render, downsampled, pixel-diffed vs the export
```

OCR is the ground truth for every string; the layout is read from the export
pixels, not from a design description. A pixel counts as different when the
summed |ΔRGB| exceeds 24.

## Open it

```bash
# simplest
open index.html

# or serve it (recommended — matches how it was verified)
python3 -m http.server 8766 --bind 127.0.0.1
# → http://127.0.0.1:8766/index.html
```

`file://` works too: the fonts are embedded as base64 data URIs inside
`assets/fonts/fonts.css` and `assets/lion/lion-NN-fonts.css`, so nothing is
fetched over the network.

## Layout

```
index.html          gallery — every artboard in an iframe, grouped per Figma page
compare-lion.html   Lion compare screen — Figma export next to the live HTML
                    render for each of the 11 screens, with the measured diff %
v1.html             gallery — the two v1.0 pages, every screen in an iframe with
                    its measured diff %

--- Tasks page -------------------------------------------------------------
home.html           HOME screen          (390 × 1196)
list-020.html       LIST 0/7 screen      (390 × 1074)
list-023.html       LIST 3/7 screen      (390 × 1032)
list-027.html       LIST 7/7 screen      (390 ×  990)
styles.css          shared stylesheet (also holds the gallery chrome)

--- Lion page --------------------------------------------------------------
lion-01.html        活動 · 音樂           (390 ×  874)
lion-02.html        活動 · 分類篩選        (390 ×  874)
lion-03.html        課程 · 機構           (390 ×  848)
lion-04.html        活動 · 機構           (390 ×  848)
lion-05.html        機構 · 分類篩選        (390 ×  848)
lion-06.html        機構詳情 · 樂活獅子會   (390 × 1428)
lion-07.html        活動詳情 · Rosewood   (402 × 1918)
lion-08.html        家教顧問 · 對話 1      (390 ×  928)
lion-09.html        機構詳情 · 新時代獅子會 (390 × 1428)
lion-10.html        活動詳情 · 新時代獅子會 (402 × 1918)
lion-11.html        家教顧問 · 對話 2      (390 ×  928)
styles-lion.css     shared design system for the Lion page

--- v1.0 pages ---------------------------------------------------------------
v1-<slug>.html      the 98 screens of the big `v1.0` page, one file per screen
v73-<slug>.html     the 65 screens of the `v1.0 最初版 - (7.3)` page
styles-v1.css       shared design system for both v1 pages
assets/v1/
  <slug>.css          per-screen stylesheet for one v1 screen
  <slug>-fonts.css    per-screen font subset: Noto Sans TC + Poppins/Arimo, inlined
  <slug>-*.png        photos and illustrations cropped from the 4× export

--- source exports ----------------------------------------------------------
source/v1raw/screens/          the 4× PNG of every big-page screen + manifest.json
source/v1raw73/screens/        the 4× PNG of every 7.3 screen + manifest.json
source/v1raw73/*-section.png   the 7.3 page exported as four whole sections

assets/
  hero-home.png       home photo, 350 × 180
  hero-list.png       list hero (list-020 / list-023), 390 × 360
  hero-list-027.png   list hero (list-027), 390 × 360
  avatar-ellen.png    instructor avatar, 112 × 112
  banner.png          list-screen gradient banner, 390 × 96
  fonts/fonts.css     Noto Sans TC + Poppins, subsetted & base64-inlined
  lion/
    lion-NN.css         per-screen stylesheet (one file owns several screens)
    lion-NN-fonts.css   per-screen font subset: Noto Sans TC + Arimo, inlined
    lion-type.css       measured typography corrections shared by the card UI
    compare/*.png       2× copies of the Figma exports, used by compare-lion.html
    *.png               photos cropped from the 4× export, gradients, logos
```

Each page is one fixed-size artboard (`.phone` on the Tasks page, `.lion` on the
Lion page) with absolutely positioned children — the same construction as the
Figma frames, so it scales and prints predictably.

## Accuracy

Rendered in headless Chrome and diffed against the 4× Figma PNGs at 2×. A pixel
counts as different when the summed |ΔRGB| exceeds 24.

**Tasks**

| Screen | Differing pixels |
|---|---|
| home | 3.53 % |
| list-020 | 3.13 % |
| list-023 | 3.55 % |
| list-027 | 4.10 % |

**Lion**

| Screen | Differing pixels |
|---|---|
| lion-01 | 4.38 % |
| lion-02 | 4.53 % |
| lion-03 | 4.12 % |
| lion-04 | 4.26 % |
| lion-05 | 3.81 % |
| lion-06 | 7.34 % |
| lion-07 | 6.15 % |
| lion-08 | 7.52 % |
| lion-09 | 9.10 % |
| lion-10 | 3.77 % |
| lion-11 | 9.24 % |

**v1.0 and v1.0 最初版 (7.3)**

Both v1 pages use the same pipeline: one HTML file per screen, a shared design
system in `styles-v1.css`, a per-screen stylesheet, a per-screen font subset and
the images cropped from the 4× export. Every screen is measured the same way and
the result is written to `analysis/v1-diff.json`; `v1.html` shows it per screen.

The 7.3 page was exported as four whole *sections* rather than per frame, so it
is segmented locally: `scripts/v1_segment.py` separates the canvas grey
(`#EFEFEF`), the annotation-panel orange (`#FFB486`) and the thin connector
lines (`#D9D9D9`) from the screen content, erodes the content by 5 px to break
the lines, takes the connected components, and snaps each one to the true
artboard edges with a 60 % majority vote per row and column. That yields 65
screens at exact artboard bounds (375, 390, 402, 403 or 404 css px wide), each
auto-matched against the big v1.0 page so the 7.3 screens reuse the same
components.

The residual is concentrated in glyph rasterisation: the exact Figma typeface
is not recoverable from a raster export, so the faces were chosen by sweeping
candidate families against the source pixels.

* **Tasks page** — **Noto Sans TC + Poppins**. Every other family tested
  (PingFang TC, M PLUS Rounded 1c, Zen Kaku Gothic New, Zen Maru Gothic,
  Kosugi Maru, Noto Sans HK) scored worse.
* **Lion page** — **Noto Sans TC** for CJK and **Arimo** for Latin. The Lion
  design sets Latin in a Helvetica-class grotesque rather than the geometric
  Poppins the Tasks page uses (the export's `HK$480` is 50.5 × 12.5 px at
  43.6 % ink coverage, which is Arial Regular at 14 px; Poppins is 56 px wide at
  that size). Direct A/B on `lion-03`: Noto + Arimo 6.43 %, Noto + system
  Helvetica 6.52 %, all-system 6.68 %.
* **Ideographic punctuation.** The Lion export sets the full stop `。` and comma
  `，` on the **left** of their em box (Simplified-Chinese punctuation) while
  Noto Sans TC centres them. On `lion-06` / `lion-09` the body copy therefore
  leads with `"Noto Sans SC"` — 2.0 percentage points better in the affected
  region than Noto Sans TC alone.
* **Ink colour.** Every Lion screen sets its primary text in **pure black**
  (`#000`), not the `#181b17` the palette suggests; the muted blue `#7089a8`
  and the purple accent `#7258ff` are correct as-is.
* **Stem weight.** The 4× export is downsampled for the comparison, which
  softens and fattens the stems. A `text-shadow: 0 0 0.2px currentColor` on
  the black body copy restores the stem weight (measured −0.11 pp).

### What the v1.0 pages taught us

The two v1.0 pages are text-heavy, and three systematic defects showed up
again and again. All three are fixed globally rather than per screen:

* **Fullwidth punctuation advance.** Chrome's default `text-spacing-trim:
  normal` halves the advance of a closing fullwidth bracket that stands next
  to another fullwidth mark, so `）` became 7 px wide instead of 14 px at
  14 px and every later glyph in the line drifted sideways.
  `styles-v1.css` therefore sets `text-spacing-trim: space-all` on `body`
  (measured with `scripts/char_probe.py`); this alone took
  `v1-competition-detail-closed` from 9.51 % to 8.54 %.
* **One font size per text block.** The fitter solves for the font size that
  makes a line's *ink width* match the export, so a line whose OCR text lost
  a character gets a larger font size and the wrong glyph size. A design
  block uses one size, so `scripts/autotune.py` snaps every line of a block to
  the block's own size (13.55, 14.0, 15.28 … → 14) and then aligns the block
  vertically to the export. Measured on `v1-competition-detail-open`:
  10.69 % → 8.97 %, on `v1-competition-detail-closed`: 8.54 % → 7.97 %.
* **Text blocks sit one or two pixels low.** `scripts/bandfit.py` registers
  each band of the render against the export and reports the best `dx`/`dy`;
  the shift is then written into the page. This is worth more than any
  typeface change on a text-heavy screen.

Because every page uses a different set of glyphs, each screen ships its own
subsetted font stylesheet (`assets/lion/lion-NN-fonts.css`, ~80–200 KB) with
only the characters that screen needs, inlined as base64 data URIs. It is
linked **after** `assets/fonts/fonts.css` so the matching family+weight
declaration wins.

## Current state

<!-- status:begin -->

| | screens | mean diff | over the 6 % budget |
|---|---|---|---|
| v1.0 page | 98 | 4.74 % | 20 |
| v1.0 最初版 (7.3) page | 63 | 4.33 % | 15 |
| **all** | **161** | **4.58 %** | **35** |

Best 0.00 %, worst 9.87 %.

Screens still above the 6 % budget:

* `v73-competition2-03` — 9.87 %
* `v1-svip-membership-yearly` — 9.41 %
* `v1-ssvip-membership-monthly` — 9.28 %
* `v1-vip-membership-yearly` — 9.16 %
* `v1-chat-recommended-task-pack` — 9.05 %
* `v1-competition-detail-open` — 8.97 %
* `v1-svip-membership-monthly` — 8.72 %
* `v1-invite-1` — 8.61 %
* `v73-competition2-02` — 8.54 %
* `v1-vip-membership-monthly` — 8.39 %
* `v73-competition-01` — 8.33 %
* `v1-competition-detail-closed` — 7.97 %
* `v1-school-detail` — 7.95 %
* `v73-activity-03` — 7.90 %
* `v1-ssvip-membership-yearly` — 7.60 %
* `v73-activity-15` — 7.39 %
* `v1-home` — 7.29 %
* `v1-favourites-expired` — 7.14 %
* `v1-img-1142-1` — 7.13 %
* `v73-mine-04` — 7.02 %
* `v73-competition2-15` — 6.92 %
* `v1-chat-answer-ready` — 6.79 %
* `v1-chat-dislike-feedback` — 6.79 %
* `v1-chat-like-feedback` — 6.79 %
* `v1-my-competition-all` — 6.79 %
* `v73-competition2-13` — 6.77 %
* `v73-activity-06` — 6.76 %
* `v73-competition-02` — 6.73 %
* `v73-activity-04` — 6.59 %
* `v73-competition-04` — 6.54 %
* `v73-activity-02` — 6.43 %
* `v73-competition-03` — 6.43 %
* `v1-ai-agreement-modal` — 6.21 %
* `v73-activity-09` — 6.21 %
* `v1-quota-exhausted-ssvip` — 6.10 %

These are the text-heavy screens. The residual is glyph anti-aliasing: the export is a 4× raster that Figma drew with its own renderer, Chrome rasterises natively at 2×, and even with identical glyph geometry ~29 % of the pixels of a text row differ by more than the 24/765 comparison threshold. The typeface, weight, size, sub-pixel position and the resampling pipeline were all swept and are already at their best (see *What the v1.0 pages taught us* above).

<!-- status:end -->

## Known limitations

- **Typeface.** Noto Sans TC / Arimo are close matches, not the original fonts.
  The remaining difference is spread evenly across every text band. Measured:
  the export's CJK glyphs carry an ink height of 0.89–0.92 em against Noto
  Sans TC's 0.93 em, and their Latin has a cap height ~1 px taller at the same
  advance width — the original face is therefore slightly taller-and-narrower
  than any family available here, and cannot be recovered from a raster.
- **Sub-pixel text position.** Chrome rasterises a text origin at 1/4 CSS px at
  4× and 1/2 CSS px at 2×, so a line can only land on the export's exact
  sub-pixel offset by luck. Positions are tuned to the nearest half pixel.
- **List-screen status bar + nav buttons** (back, bookmark, star, share) are
  baked into `hero-list.png` / `hero-list-027.png` because the Figma export
  rasterised them into the photo crop. Equivalent HTML/SVG markup already
  exists behind the `.lscreen--chrome` class in `styles.css` — swap
  `visibility: hidden` for `visible` if you re-export a clean photo.
- The peach `#ffddd5` card border is applied to **card 1** positionally, which
  is what the source pixels show in all three list frames.
- Some gradients that a single CSS linear gradient cannot reproduce ship as
  fitted 2-D polynomial PNG bitmaps (`assets/lion/*-grad.png`).

## Regenerating

```bash
python3 scripts/render_check.py              # render + diff every screen
python3 scripts/render_check.py lion-03       # one screen
python3 scripts/fetch_lion_fonts.py lion-01 lion-02 …   # rebuild a font subset
python3 scripts/preview.py                   # rebuild preview.png + compare.png
python3 scripts/compare_lion.py              # rebuild compare-lion.html + .png
```

For the two v1 pages:

```bash
python3 scripts/measure_v1.py                # measure every built v1 screen
python3 scripts/gallery_v1.py                # rebuild v1.html
python3 scripts/ensure_v1_fonts.py           # make sure every page ships its subset
python3 scripts/package_v1_batch.py          # measure + gallery + zip + check
python3 scripts/v1_segment.py                # re-segment the 7.3 sections
```

`scripts/build_pages.py` is an authoring aid only — the shipped output is the
static HTML/CSS itself.

Useful extras while tuning a screen:

```bash
python3 scripts/diff_bands.py lion-03 --rows 16                  # diff per band
python3 scripts/diff_regions.py lion-03 --grid 40                # worst regions
python3 scripts/compare.py lion-03 --y0 130 --y1 290 --scale 1.25 # side by side
python3 scripts/inkbox.py lion-03 --rect 118,186,186,208 --bg '#ffffff'
python3 scripts/type_match.py lion-03 --samples /tmp/samples03c.json
```

Tuning helpers:

```bash
# try CSS overrides and keep only what lowers the diff
python3 scripts/sweep.py lion-11 --cand ".rbubble{padding-left:18.5px}"

# ...or measure one small region, which is far more sensitive than the page
python3 scripts/sweep.py lion-08 --region 290,76,72,22 \
    --cand ".chead__mename{font-size:10.75px}"

# measure the sub-pixel drift of a text block (source vs render)
python3 scripts/align_text.py lion-09 --rect 39,798,307,14,"body l1"

# fit a typeface / size / weight to one line of the export
python3 scripts/fit_text.py --ink-only \
    --source source/lion/lion-11-chat-2.png --rect 70,634,260,17 \
    --text "齊做賀年小食、笑口葉手作、遊戲同樂同" \
    --family "Noto Sans TC" --size 14 --weight 400
```

`preview.png` is a contact sheet of the rendered screens; `compare.png` puts
the Figma export next to the render for each screen, with the measured diff %.
`compare-lion.html` does the same for the Lion page as a browsable screen —
each row shows the Figma export on the left and the live HTML render (in an
iframe, so it is the actual delivered file) on the right. `compare-lion.png` is
the flat version of the same table. The Tasks-page `preview.png` / `compare.png`
are untouched by `scripts/compare_lion.py`.
