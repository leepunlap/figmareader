#!/usr/bin/env node
/**
 * Quota-frugal Figma REST client.
 *
 * Figma Tier 1 (files / nodes / images) can be as tight as 6 requests PER MONTH
 * for a file in a paid-plan folder read with a View/Collab seat, or 10 req/min
 * with a Dev/Full seat. This client is built around spending the minimum:
 *
 *   1 request  GET /v1/files/:key/nodes?ids=<frame>   full subtree, cached on disk
 *   1 request  GET /v1/images/:key?ids=id1,id2,...    ALL assets in ONE batched call
 *   0 requests downloading the returned signed URLs (plain OSS, no Figma quota)
 *
 * After that, every rebuild is free: the tree is read from the local cache.
 *
 * Token resolution order: FIGMA_TOKEN env -> FIGMA_TOKEN_FILE -> ~/.figma_token
 * The token is never printed and never written to disk by this script.
 *
 * Usage:
 *   node scripts/figma-fetch.mjs frame  <fileKey> <nodeId> [--refresh]
 *   node scripts/figma-fetch.mjs file   <fileKey> [--depth N]
 *   node scripts/figma-fetch.mjs assets <fileKey> <nodeId...> [--format svg|png] [--scale 2] [--out dir]
 *   node scripts/figma-fetch.mjs png    <fileKey> <nodeId> [--scale 2] [--out dir]
 *   node scripts/figma-fetch.mjs whoami
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

const API = 'https://api.figma.com/v1';
const ROOT = resolve(new URL('..', import.meta.url).pathname);
const CACHE = join(ROOT, '.figma-cache');

/* ------------------------------------------------------------------ token */

function readToken() {
  const candidates = [];
  if (process.env.FIGMA_TOKEN) {
    candidates.push(['env FIGMA_TOKEN', () => process.env.FIGMA_TOKEN.trim()]);
  }
  if (process.env.FIGMA_TOKEN_FILE) {
    const p = process.env.FIGMA_TOKEN_FILE;
    candidates.push([`file ${p}`, () => readFileSync(p, 'utf8').trim()]);
  }
  const home = join(homedir(), '.figma_token');
  candidates.push([`file ${home}`, () => readFileSync(home, 'utf8').trim()]);

  for (const [where, get] of candidates) {
    try {
      const t = get();
      if (t) {
        console.error(`[auth] token loaded from ${where}`);
        return t;
      }
    } catch {
      /* try next candidate */
    }
  }
  console.error(
    '[auth] No Figma token found.\n' +
      '       Figma -> Settings -> Security -> Personal access tokens -> Generate new token\n' +
      '       Scope: file_content:read  (read-only is enough)\n' +
      '       Save it OUTSIDE this repo (never paste it into chat):\n' +
      '         printf %s "figd_xxx" > ~/.figma_token && chmod 600 ~/.figma_token'
  );
  process.exit(2);
}

/* ------------------------------------------------------------------- http */

function reportRate(headers) {
  const type = headers.get('x-figma-rate-limit-type');
  const tier = headers.get('x-figma-plan-tier');
  const remaining = headers.get('x-figma-rate-limit-remaining');
  const reset = headers.get('x-figma-rate-limit-reset');
  const bits = [];
  if (type) bits.push(`seat=${type === 'low' ? 'LOW(View/Collab - monthly cap!)' : 'HIGH(Dev/Full - per minute)'}`);
  if (tier) bits.push(`plan=${tier}`);
  if (remaining) bits.push(`remaining=${remaining}`);
  if (reset) bits.push(`reset=${reset}`);
  if (bits.length) console.error(`[rate] ${bits.join(' ')}`);
}

async function api(path, { method = 'GET', retry = true } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { 'X-Figma-Token': TOKEN, Accept: 'application/json' },
  });
  reportRate(res.headers);

  if (res.status === 429) {
    const retryAfter = Number(res.headers.get('retry-after') || 5);
    const type = res.headers.get('x-figma-rate-limit-type') || 'unknown';
    const tier = res.headers.get('x-figma-plan-tier') || '?';
    const upgrade = res.headers.get('x-figma-upgrade-link') || '';
    const body = await res.text().catch(() => '');
    if (retry && retryAfter <= 20) {
      console.error(`[429] seat=${type} plan=${tier}; retrying in ${retryAfter}s`);
      await new Promise((r) => setTimeout(r, retryAfter * 1000));
      return api(path, { method, retry: false });
    }
    console.error(
      `[429] Quota exhausted (seat=${type}, plan=${tier}).\n${body.slice(0, 300)}\n` +
        `       This is a monthly cap for View/Collab seats - it will not reset by waiting.\n` +
        `       Upgrade link: ${upgrade}\n` +
        `       Fallback: export the frame from the Figma desktop app and rebuild from the PNG.`
    );
    process.exit(3);
  }

  if (res.status === 403) {
    console.error(
      '[403] Token cannot read this file.\n' +
        '       - confirm the token scope includes file_content:read\n' +
        '       - confirm the file\'s sharing permissions include your account\n' +
        '       - confirm you can open the file in the Figma app yourself'
    );
    process.exit(4);
  }
  if (res.status === 404) {
    console.error('[404] File or node not found. Check the file key and the node id (12-34 -> 12:34).');
    process.exit(5);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    console.error(`[http ${res.status}] ${body.slice(0, 400)}`);
    process.exit(6);
  }
  return res.json();
}

/* ------------------------------------------------------------------ cache */

const cachePath = (key) => join(CACHE, `${key.replace(/[^\w.-]/g, '_')}.json`);

function cacheRead(key) {
  const p = cachePath(key);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
}

function cacheWrite(key, data) {
  mkdirSync(CACHE, { recursive: true });
  const p = cachePath(key);
  writeFileSync(p, JSON.stringify(data));
  console.error(`[cache] saved ${p}`);
  return p;
}

/* ----------------------------------------------------------------- assets */

const safeName = (id, ext) => `${String(id).replace(/[^0-9a-zA-Z_-]/g, '_')}.${ext}`;

async function download(url, dest) {
  const res = await fetch(url); // signed OSS url - no Figma quota
  if (!res.ok) {
    console.error(`[download] HTTP ${res.status} -> ${dest}`);
    return false;
  }
  const buf = Buffer.from(await res.arrayBuffer());
  mkdirSync(resolve(dest, '..'), { recursive: true });
  writeFileSync(dest, buf);
  console.error(`[download] ${dest} (${(statSync(dest).size / 1024).toFixed(1)} KB)`);
  return true;
}

/* ------------------------------------------------------------------ steps */

/** Full subtree of one node. 1 request. Cached forever. */
async function stepFrame(fileKey, nodeId, refresh) {
  const cacheKey = `${fileKey}-${nodeId}-subtree`;
  if (!refresh) {
    const hit = cacheRead(cacheKey);
    if (hit) {
      console.error(`[cache] HIT ${cachePath(cacheKey)} - no API call spent`);
      console.log(JSON.stringify(hit));
      return;
    }
  }
  const path = `/files/${fileKey}/nodes?ids=${encodeURIComponent(nodeId)}`;
  console.error(`[api] GET ${path}   (1 request, full subtree of ${nodeId})`);
  const data = await api(path);
  cacheWrite(cacheKey, data);
  console.log(JSON.stringify(data));
}

/** Whole file or a depth-limited slice. 1 request. */
async function stepFile(fileKey, depth, refresh) {
  const cacheKey = `${fileKey}-root-d${depth}`;
  if (!refresh) {
    const hit = cacheRead(cacheKey);
    if (hit) {
      console.error(`[cache] HIT ${cachePath(cacheKey)} - no API call spent`);
      console.log(JSON.stringify(hit));
      return;
    }
  }
  const path = `/files/${fileKey}?depth=${depth}`;
  console.error(`[api] GET ${path}`);
  const data = await api(path);
  cacheWrite(cacheKey, data);
  console.log(JSON.stringify(data));
}

/** ALL assets in ONE batched request. */
async function stepAssets(fileKey, nodeIds, format, scale, outDir) {
  const params = new URLSearchParams({ ids: nodeIds.join(','), format });
  if (format !== 'svg') params.set('scale', String(scale));
  if (format === 'svg') {
    params.set('svg_include_node_id', 'true'); // data-node-id -> lets us map files back to layers
    params.set('svg_outline_text', 'false');
  }
  console.error(`[api] GET /images/${fileKey}?${params.toString()}   (1 batched request for ${nodeIds.length} assets)`);
  const data = await api(pathOf(fileKey, params));

  const out = resolve(ROOT, outDir);
  mkdirSync(out, { recursive: true });
  const manifest = { fileKey, format, generatedAt: new Date().toISOString(), files: [] };

  for (const [id, info] of Object.entries(data.images || {})) {
    if (!info.url) {
      console.error(`[asset] no url for ${id}: ${info.error || 'render failed (invisible or 0% opacity?)'}`);
      continue;
    }
    const ext = format === 'svg' ? 'svg' : 'png';
    const name = safeName(id, ext);
    const ok = await download(info.url, join(out, name));
    manifest.files.push({
      nodeId: id,
      file: `${outDir}/${name}`,
      bytes: ok ? statSync(join(out, name)).size : 0,
      ...info,
    });
  }

  const manifestPath = join(out, '_assets.json');
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.error(`[manifest] ${manifestPath}`);
  console.log(JSON.stringify(manifest, null, 2));
}

const pathOf = (fileKey, params) => `/images/${fileKey}?${params.toString()}`;

/* ------------------------------------------------------------------- main */

function flag(args, name, fallback = undefined) {
  const i = args.indexOf(`--${name}`);
  if (i === -1) return fallback;
  const v = args[i + 1];
  return v && !v.startsWith('--') ? v : true;
}

const [cmd, ...rest] = process.argv.slice(2);
const TOKEN = readToken();

try {
  switch (cmd) {
    case 'frame': {
      const [fileKey, nodeId] = rest.filter((a) => !a.startsWith('--'));
      await stepFrame(fileKey, nodeId, !!flag(rest, 'refresh'));
      break;
    }
    case 'file': {
      const [fileKey] = rest.filter((a) => !a.startsWith('--'));
      await stepFile(fileKey, Number(flag(rest, 'depth', 2)), !!flag(rest, 'refresh'));
      break;
    }
    case 'assets': {
      const ids = rest.filter((a) => !a.startsWith('--'));
      await stepAssets(
        ids[0],
        ids.slice(1),
        String(flag(rest, 'format', 'svg')),
        Number(flag(rest, 'scale', 2)),
        String(flag(rest, 'out', 'assets'))
      );
      break;
    }
    case 'png': {
      const ids = rest.filter((a) => !a.startsWith('--'));
      const params = new URLSearchParams({ ids: ids[1], format: 'png', scale: String(Number(flag(rest, 'scale', 2))) });
      console.error(`[api] GET /images/${ids[0]}?${params.toString()}`);
      const data = await api(pathOf(ids[0], params));
      const url = data.images?.[ids[1]]?.url;
      if (!url) {
        console.error(`[png] no url for ${ids[1]}`);
        process.exit(7);
      }
      const out = resolve(ROOT, String(flag(rest, 'out', 'reference')));
      mkdirSync(out, { recursive: true });
      const name = `${safeName(ids[1], 'png').replace('.png', '')}.png`;
      await download(url, join(out, name));
      console.log(join(out, name));
      break;
    }
    case 'whoami': {
      const res = await fetch(`${API}/me`, { headers: { 'X-Figma-Token': TOKEN } });
      reportRate(res.headers);
      console.log(JSON.stringify(await res.json(), null, 2));
      break;
    }
    default:
      console.error('Usage: frame | file | assets | png | whoami');
      process.exit(1);
  }
} catch (err) {
  console.error(`[error] ${err?.message || err}`);
  process.exit(1);
}
