/*
 * MCode Export — main thread (Figma Plugin API, not rate-limited).
 *
 * Reads the live document, exports the chosen frames as PNG at up to 4x,
 * exports every vector/icon as real SVG and every bitmap as PNG, and dumps an
 * exact design tree (fonts, fills, auto-layout, effects) as JSON.
 *
 * The payload is handed to the UI iframe, which POSTs it to the local
 * receiver in scripts/figma-receive.py so it lands straight in the project.
 */

figma.showUI(__html__, { width: 420, height: 560, themeColors: true });

const MAX_EXPORT_DIM = 4096;

/* ---------------------------------------------------------------- helpers */

const isMixed = (v) => typeof v === 'symbol' || v === figma.mixed;

function safe(v) {
  if (isMixed(v)) return 'mixed';
  if (v === undefined) return undefined;
  if (v === null) return null;
  if (typeof v === 'object') {
    if (Array.isArray(v)) return v.map(safe);
    const out = {};
    for (const [k, val] of Object.entries(v)) {
      if (k === 'boundVariables' || k === 'styles' || k === 'styleOverrideTable') continue;
      out[k] = safe(val);
    }
    return out;
  }
  return v;
}

async function fontOf(node) {
  try {
    if (node.fontName && !isMixed(node.fontName)) return { ...node.fontName };
    if (node.characters && node.characters.length) {
      const r = await node.getRangeFontName(0, node.characters.length);
      if (r && !isMixed(r)) return { ...r };
    }
  } catch {
    /* fall through */
  }
  return node.fontName && !isMixed(node.fontName) ? { ...node.fontName } : 'mixed';
}

/* --------------------------------------------------------- tree serializer */

async function serialize(node, depth = 0) {
  const b = node.absoluteBoundingBox;
  const out = {
    id: node.id,
    name: node.name,
    type: node.type,
    visible: node.visible !== false,
    opacity: typeof node.opacity === 'number' ? node.opacity : 1,
    visible_ancestors: true,
    box: b ? { x: b.x, y: b.y, w: b.width, h: b.height } : null,
  };

  if (node.type === 'FRAME' || node.type === 'GROUP' || node.type === 'COMPONENT' || node.type === 'COMPONENT_SET' || node.type === 'INSTANCE') {
    out.clipsContent = node.clipsContent === true;
    out.layoutMode = node.layoutMode || 'NONE';
    out.layoutWrap = node.layoutWrap || 'NO_WRAP';
    out.itemSpacing = node.itemSpacing ?? 0;
    out.padding = [node.paddingTop ?? 0, node.paddingRight ?? 0, node.paddingBottom ?? 0, node.paddingLeft ?? 0];
    out.primaryAxisAlignItems = node.primaryAxisAlignItems || 'MIN';
    out.counterAxisAlignItems = node.counterAxisAlignItems || 'MIN';
    out.primaryAxisSizingMode = node.primaryAxisSizingMode || 'AUTO';
    out.counterAxisSizingMode = node.counterAxisSizingMode || 'AUTO';
    out.counterAxisSpacing = node.counterAxisSpacing ?? null;
    out.layoutAlign = node.layoutAlign || 'INHERIT';
    out.layoutGrow = node.layoutGrow ?? 0;
    out.layoutPositioning = node.layoutPositioning || 'AUTO';
    out.layoutPositioning = node.layoutPositioning || 'AUTO';
    out.counterAxisSizingMode = node.counterAxisSizingMode || 'AUTO';
    out.constraints = node.constraints || null;
    out.cornerRadius = node.cornerRadius ?? 0;
    out.rectangleCornerRadii = node.rectangleCornerRadii ?? null;
    if (node.layoutMode === 'GRID') {
      out.gridLayout = node.gridLayout ? safe(node.gridLayout) : null;
    }
    if (node.type === 'INSTANCE' && node.componentProperties) {
      out.componentProperties = node.componentProperties;
    }
  }

  if (node.fills !== undefined) out.fills = safe(node.fills);
  if (node.strokes !== undefined) out.strokes = safe(node.strokes);
  if (node.strokeWeight !== undefined) out.strokeWeight = node.strokeWeight;
  if (node.strokeAlign !== undefined) out.strokeAlign = node.strokeAlign;
  if (node.dashPattern) out.dashPattern = node.dashPattern;
  if (node.effects !== undefined) out.effects = safe(node.effects);
  if (node.backgroundColor) out.backgroundColor = safe(node.backgroundColor);
  if (node.styles) out.styleRefs = node.styles;

  if (node.type === 'TEXT') {
    out.characters = node.characters;
    out.textAutoResize = node.textAutoResize || 'NONE';
    out.textAlignHorizontal = node.textAlignHorizontal || 'LEFT';
    out.textAlignVertical = node.textAlignVertical || 'TOP';
    out.textCase = node.textCase || 'ORIGINAL';
    out.textDecoration = node.textDecoration || 'NONE';
    out.maxLines = node.maxLines ?? null;
    out.letterSpacing = node.letterSpacing ?? 0;
    out.lineHeight = safe(node.lineHeight);
    out.paragraphSpacing = node.paragraphSpacing ?? 0;
    out.paragraphIndent = node.paragraphIndent ?? 0;
    out.listSpacing = node.listSpacing ?? 0;
    const f = await fontOf(node);
    out.fontName = f;
    if (f && typeof f === 'object') {
      out.fontSize = node.fontSize ?? null;
      out.fontWeight = node.fontWeight ?? null;
    }
  }

  if (node.type === 'VECTOR' || node.type === 'ELLIPSE' || node.type === 'STAR' || node.type === 'POLYGON' || node.type === 'LINE' || node.type === 'BOOLEAN_OPERATION') {
    out.starCount = node.starCount ?? null;
    out.pointCount = node.pointCount ?? null;
  }

  return out;
}

async function serializeTree(node, maxDepth = 12) {
  const root = await serialize(node);
  const walk = async (n, d) => {
    if (d > maxDepth) return;
    const kids = [];
    if ('children' in n) {
      const children = await n.getChildrenAsync();
      for (const c of children) {
        kids.push(await walk(c, d + 1));
      }
    }
    root.children = root.children || [];
    return { ...root, children: kids };
  };
  return walk(node, 0);
}

/* --------------------------------------------------------- asset collection */

const VECTOR_TYPES = new Set(['VECTOR', 'ELLIPSE', 'STAR', 'POLYGON', 'LINE', 'BOOLEAN_OPERATION']);

function hasImageFill(node) {
  if (!node.fills || !Array.isArray(node.fills)) return false;
  return node.fills.some((f) => f && f.type === 'IMAGE' && f.visible !== false);
}

function isRenderable(node) {
  if (node.visible === false) return false;
  if (typeof node.opacity === 'number' && node.opacity === 0) return false;
  const b = node.absoluteBoundingBox;
  if (!b || b.width <= 0 || b.height <= 0) return false;
  return true;
}

async function collectAssets(frame, wanted) {
  const assets = [];
  const seen = new Set();

  const visit = async (node, depth) => {
    if (depth > 14) return;
    // instances / component sets: export the whole thing, never their children
    if (node.type === 'INSTANCE' || node.type === 'COMPONENT_SET') {
      if (VECTOR_TYPES.has(node.type)) { /* not possible, but keep logic explicit */ }
      if (node.type === 'INSTANCE' && isRenderable(node) && wanted.assets) {
        seen.add(node.id);
        assets.push({ node: node, kind: 'vector' });
      }
      return;
    }
    if (VECTOR_TYPES.has(node.type) && isRenderable(node)) {
      seen.add(node.id);
      assets.push({ node, kind: 'vector' });
    } else if (hasImageFill(node) && isRenderable(node)) {
      seen.add(node.id);
      assets.push({ node, kind: 'raster' });
    }
    if ('children' in node) {
      const children = await node.getChildrenAsync();
      for (const c of children) await visit(c, depth + 1);
    }
  };

  await visit(frame, 0);
  return assets;
}

/* ------------------------------------------------------------- exporting */

async function exportPng(node, scale) {
  // Figma caps exports; back off the scale rather than fail the whole run.
  const candidates = [scale, 2, 1].filter((s, i, a) => s <= scale && a.indexOf(s) === i);
  for (const s of candidates) {
    try {
      const bytes = await node.exportAsync({ format: 'PNG', constraint: { type: 'SCALE', value: s } });
      return { bytes, scale: s };
    } catch (err) {
      const msg = String(err && err.message ? err.message : err);
      if (/too large|exceeds|maximum|4096|scale/i.test(msg) && s > 1) continue;
      throw err;
    }
  }
  throw new Error('PNG export failed at every scale');
}

async function exportSvg(node) {
  const bytes = await node.exportAsync({ format: 'SVG' });
  return bytes;
}

async function exportRaster(node, scale = 2) {
  const bytes = await node.exportAsync({ format: 'PNG', constraint: { type: 'SCALE', value: scale } });
  return bytes;
}

/* ------------------------------------------------------------------ flow */

/* Walk the whole page tree and collect every node that looks like a phone
   screen: a frame-ish node roughly 320-460 css px wide and tall. The design
   pages bury the real screens inside big sections and groups, so the
   page-children list is not enough. */
const SCREEN_MIN_W = 300;
const SCREEN_MAX_W = 470;
const SCREEN_MIN_H = 420;

function isScreenShape(b) {
  if (!b) return false;
  return b.width >= SCREEN_MIN_W && b.width <= SCREEN_MAX_W && b.height >= SCREEN_MIN_H;
}

async function collectScreens(page) {
  // One API call instead of a per-node round trip — the design pages have tens
  // of thousands of nodes and a manual walk is far too slow.
  let candidates = [];
  try {
    candidates = page.findAllWithCriteria({
      types: ['FRAME', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE', 'GROUP'],
    });
  } catch (err) {
    // older API: fall back to a plain walk, filtered by type
    const TYPES = ['FRAME', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE', 'GROUP'];
    try {
      candidates = page.findAll().filter((n) => TYPES.indexOf(n.type) >= 0);
    } catch (err2) {
      candidates = [];
    }
  }
  const byId = new Map();
  const out = [];
  for (const node of candidates) {
    if (node.visible === false) continue;
    const b = node.absoluteBoundingBox;
    if (!isScreenShape(b)) continue;
    // skip a screen nested inside another screen
    if (hasScreenAncestor(node, byId)) continue;
    out.push({
      id: node.id,
      name: node.name,
      type: node.type,
      w: Math.round(b.width),
      h: Math.round(b.height),
      path: node.name,
    });
  }
  out.sort((a, b) => a.name.localeCompare(b.name));
  return out;
}

/* Walk up the parent chain looking for an ancestor that is itself a screen. */
function hasScreenAncestor(node, cache) {
  let p = node.parent;
  while (p) {
    if (cache.has(p.id)) return true;
    const b = p.absoluteBoundingBox;
    if (b && isScreenShape(b)) return true;
    p = p.parent;
  }
  return false;
}

/* Resolve an id to a node anywhere in the page tree. */
async function findById(root, id) {
  if (root.id === id) return root;
  if (!('children' in root)) return null;
  const children = await root.getChildrenAsync();
  for (const c of children) {
    const hit = await findById(c, id);
    if (hit) return hit;
  }
  return null;
}

figma.ui.onmessage = async (msg) => {
  if (msg.type === 'ui-ready') {
    try {
      const page = figma.currentPage;
      const children = await page.getChildrenAsync();
      const items = [];
      for (const n of children) {
        const b = n.absoluteBoundingBox;
        items.push({
          id: n.id,
          name: n.name,
          type: n.type,
          w: b ? Math.round(b.width) : 0,
          h: b ? Math.round(b.height) : 0,
          path: n.name,
        });
      }
      const sel = page.selection.map((n) => n.id);
      figma.ui.postMessage({
        type: 'frames',
        page: page.name,
        items,
        screens: [],
        selection: sel,
        file: { name: figma.root.name, key: figma.root.id },
      });
    } catch (err) {
      figma.ui.postMessage({ type: 'error', where: 'ui-ready', error: String(err && err.message ? err.message : err) });
    }
    return;
  }

  if (msg.type === 'discover') {
    try {
      figma.ui.postMessage({ type: 'progress', phase: 'discovering' });
      const screens = await collectScreens(figma.currentPage);
      figma.ui.postMessage({ type: 'discovered', screens });
    } catch (err) {
      figma.ui.postMessage({ type: 'error', where: 'discover', error: String(err && err.message ? err.message : err) });
    }
    return;
  }

  if (msg.type === 'export') {
    const { frameIds = [], scale = 4, wantAssets = true, wantTree = true } = msg;
    const page = figma.currentPage;
    const children = await page.getChildrenAsync();
    const byId = new Map(children.map((n) => [n.id, n]));
    // every node on the page, so a screen nested deep in a section resolves
    let all = [];
    try {
      all = page.findAll();
    } catch (err) {
      all = [];
    }
    for (const n of all) byId.set(n.id, n);

    for (const id of frameIds) {
      const frame = byId.get(id);
      if (!frame) continue;
      try {
        figma.ui.postMessage({ type: 'progress', id, phase: 'rendering', name: frame.name });

        let png = null;
        if (msg.wantPng !== false) {
          png = await exportPng(frame, scale);
        }

        let assets = [];
        if (wantAssets) {
          const found = await collectAssets(frame, { assets: true });
          figma.ui.postMessage({ type: 'progress', id, phase: 'assets', name: frame.name, count: found.length });
          for (const a of found) {
            try {
              if (a.kind === 'vector') {
                const bytes = await exportSvg(a.node);
                assets.push({ id: a.node.id, name: a.node.name, type: a.node.type, format: 'svg', bytes });
              } else {
                const bytes = await exportRaster(a.node, 2);
                assets.push({ id: a.node.id, name: a.node.name, type: a.node.type, format: 'png', bytes });
              }
            } catch (err) {
              figma.ui.postMessage({ type: 'progress', id, phase: 'asset-failed', name: a.node.name, error: String(err && err.message ? err.message : err) });
            }
          }
        }

        const tree = wantTree ? await serializeTree(frame) : null;

        figma.ui.postMessage({
          type: 'frame-done',
          id,
          name: frame.name,
          page: page.name,
          pngBytes: png ? png.bytes : null,
          pngScale: png ? png.scale : null,
          box: frame.absoluteBoundingBox
            ? { w: frame.absoluteBoundingBox.width, h: frame.absoluteBoundingBox.height }
            : null,
          assets,
          tree,
        });
      } catch (err) {
        figma.ui.postMessage({
          type: 'frame-failed',
          id,
          name: frame.name,
          error: String(err && err.message ? err.message : err),
        });
      }
    }
    figma.ui.postMessage({ type: 'all-done' });
    return;
  }
};
