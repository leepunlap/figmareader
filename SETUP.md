# Figma → HTML/CSS handoff (free-plan friendly)

Two routes work without a paid plan. Pick one.

---

## Route A — manual export (no API quota at all) ✅ recommended on free plans

Figma's desktop app exports layers to PNG/SVG/PDF with **no Dev Mode seat and no
API quota**. Export the frames yourself, drop them in `source/`, and the pipeline
below measures them back into HTML/CSS.

### What to export

| What | How | Why |
|---|---|---|
| Each screen | select frame → Export → **PNG**, scale **4x** → `source/<screen>.png` | 4x gives ¼-px measurement accuracy |
| Icons, logos, illustrations | select layer → Export → **SVG** → `source/assets/<name>.svg` | keeps vectors vector |
| Photos / bitmaps | select layer → Export → **PNG** 4x → `source/assets/<name>.png` | croppable raster source |

Tips
- PNG at 4x of a 1440×900 frame is 5760×3600 — fine. Above ~1600px wide, use 2x.
- Export each screen separately, named after the screen (`home.png`, `pricing.png`).
- Background-only screens: hide the background layer before export if it fights your page colour.

### Pipeline

```bash
# 1. measure the frame -> geometry + exact colours (JSON)
python3 scripts/frame_analyze.py source/home.png --scale 4 --out analysis/home

# 2. crop an asset out of the 4x source, downscaled to 2x for the web
python3 scripts/frame_analyze.py source/home.png --scale 4 \
  --crop 512,320,128,128 --out assets/logo.png
```

`analysis/home/frame.json` then feeds the markup: measured box geometry, exact
fills, stroke colours and corner profiles become `index.html` + `styles.css`.
The result is rendered in a browser and diffed against `source/home.png` until
it matches.

---

## Route B — REST API (2 requests, then free)

Figma's free Starter plan limits **Tier 1** endpoints (`GET file`, `GET file nodes`,
`GET images`) to **10 requests/min** for a Dev/Full seat, and to as few as
**6 requests/month** for a file in a paid-plan folder read with a View/Collab seat.
The official cloud MCP server is capped at **6 tool calls/month** on free accounts,
and the desktop MCP server (`127.0.0.1:3845`) needs a paid Dev/Full seat.

### Cost per screen

| Call | Requests | Notes |
|---|---|---|
| `GET /v1/files/:key/nodes?ids=<frame>` | 1 | design tree, cached to `.figma-cache/` |
| `GET /v1/images/:key?ids=<id1>,<id2>,…` | 1 | **all** assets in one batched call |
| downloading the returned signed URLs | 0 | plain OSS, no Figma quota |

The tree is cached, so re-runs, tweaks and extra screens cost nothing after the
first read.

### One-time setup

1. Figma → **Settings → Security → Personal access tokens → Generate new token**
2. Scope: `file_content:read` only (read-only is sufficient)
3. Save it **outside this repo** (never paste it into chat or commit it):

```bash
printf %s "figd_xxxxxxxxxxxxxxxx" > ~/.figma_token && chmod 600 ~/.figma_token
```

### Commands

```bash
node scripts/figma-fetch.mjs frame  <fileKey> <nodeId>            # 1 request, cached
node scripts/figma-fetch.mjs assets <fileKey> <nodeId...> --format svg --out assets
node scripts/figma-fetch.mjs png    <fileKey> <nodeId> --scale 2 --out reference
node scripts/figma-fetch.mjs whoami                                # seat + remaining quota
```

`<fileKey>` is the segment after `/design/`; `<nodeId>` comes from `node-id`
(`12-34` → `12:34`).

---

## What each route can and cannot give you

| | Route A (PNG) | Route B (REST) |
|---|---|---|
| Exact colours | ✅ sampled pixels | ✅ fill values |
| Exact geometry | ✅ measured | ✅ node bounds |
| Vector icons | ✅ only if you export SVG | ✅ automatic |
| Font family | ❌ **only you know this** | ✅ from the design |
| Text content | ✅ via vision | ✅ exact |
| API quota spent | none | 2 per screen |

## Output

```
index.html          semantic markup rebuilt from the design
styles.css          layout, typography and colour tokens
assets/             icons (.svg) and images (.png)
source/             your original Figma exports
analysis/           measured geometry JSON per frame
```
