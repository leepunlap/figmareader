#!/usr/bin/env python3
"""
Local receiver for the "MCode Export" Figma plugin.

The plugin UI POSTs each exported frame here; this writes them straight into the
project:

    source/<frame>.png              4x frame render
    source/assets/<frame>__<name>.svg|png   icons and bitmaps
    analysis/<frame>-tree.json      exact design tree (fonts, fills, layout)
    source/_export-manifest.json    index of everything received

Binds to 127.0.0.1 only. No Figma API quota involved - this is the plugin path.

Usage:  python3 scripts/figma-receive.py [--port 8765]
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"
ASSETS = SOURCE / "assets"
ANALYSIS = ROOT / "analysis"
MAX_BODY = 512 * 1024 * 1024  # generous: a 4x frame PNG base64-encoded can be big

_slug_lock = threading.Lock()
_used_slugs: set[str] = set()


def slugify(value: str, fallback: str = "frame") -> str:
    """Filesystem-safe, stable, never traverses directories."""
    s = re.sub(r"[^0-9A-Za-z._-]+", "-", (value or "").strip()).strip("-.")
    s = re.sub(r"-{2,}", "-", s)
    if not s:
        s = fallback
    with _slug_lock:
        base = s
        n = 2
        while s.lower() in _used_slugs:
            s = f"{base}-{n}"
            n += 1
        _used_slugs.add(s.lower())
    return s


def safe_child(base: Path, name: str) -> Path:
    """Resolve `name` inside `base`, refusing anything that escapes it."""
    target = (base / name).resolve()
    if not str(target).startswith(str(base.resolve()) + "/") and target != base.resolve():
        raise ValueError(f"refusing to write outside {base}: {name}")
    return target


def decode(data_b64: str) -> bytes:
    if not data_b64:
        return b""
    if "," in data_b64[:64] and data_b64.startswith("data:"):
        data_b64 = data_b64.split(",", 1)[1]
    return base64.b64decode(data_b64)


class Handler(BaseHTTPRequestHandler):
    server_version = "MCodeFigmaReceiver/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _reply(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/ping":
            self._reply(200, {"ok": True, "root": str(ROOT), "source": str(SOURCE)})
        else:
            self._reply(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") != "/save":
            self._reply(404, {"ok": False, "error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._reply(413, {"ok": False, "error": "bad body size"})
            return

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._reply(400, {"ok": False, "error": f"invalid json: {exc}"})
            return

        try:
            result = self._save(payload)
        except Exception as exc:  # noqa: BLE001
            self._reply(500, {"ok": False, "error": str(exc)})
            return
        self._reply(200, {"ok": True, **result})

    # ------------------------------------------------------------------ save

    def _save(self, payload: dict) -> dict:
        SOURCE.mkdir(parents=True, exist_ok=True)
        ASSETS.mkdir(parents=True, exist_ok=True)
        ANALYSIS.mkdir(parents=True, exist_ok=True)

        raw_name = payload.get("name") or payload.get("id") or "frame"
        frame_slug = slugify(raw_name)

        written = []

        png = payload.get("png")
        if png and png.get("data"):
            data = decode(png["data"])
            dest = safe_child(SOURCE, f"{frame_slug}.png")
            dest.write_bytes(data)
            written.append(str(dest.relative_to(ROOT)))

        asset_count = 0
        for asset in payload.get("assets") or []:
            fmt = (asset.get("format") or "png").lower()
            if fmt not in ("svg", "png", "jpg", "jpeg"):
                fmt = "png"
            name = slugify(asset.get("name") or asset.get("id") or "asset", fallback=asset.get("id") or "asset")
            fname = f"{frame_slug}__{name}.{fmt}"
            dest = safe_child(ASSETS, fname)
            dest.write_bytes(decode(asset.get("data", "")))
            asset_count += 1
            written.append(str(dest.relative_to(ROOT)))

        tree = payload.get("tree")
        if tree:
            dest = safe_child(ANALYSIS, f"{frame_slug}-tree.json")
            dest.write_text(json.dumps(tree, indent=2, ensure_ascii=False))
            written.append(str(dest.relative_to(ROOT)))

        manifest_path = SOURCE / "_export-manifest.json"
        manifest = []
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except json.JSONDecodeError:
                manifest = []
        manifest.append(
            {
                "frame": frame_slug,
                "page": payload.get("page"),
                "id": payload.get("id"),
                "png": f"source/{frame_slug}.png" if png else None,
                "pngScale": png.get("scale") if png else None,
                "assets": asset_count,
                "tree": f"analysis/{frame_slug}-tree.json" if tree else None,
                "receivedAt": None,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

        return {
            "frame": f"source/{frame_slug}.png",
            "assets": asset_count,
            "tree": f"analysis/{frame_slug}-tree.json" if tree else None,
            "written": written,
        }

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[receiver] {self.address_string()} {fmt % args}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[receiver] listening on http://127.0.0.1:{args.port}")
    print(f"[receiver] writing into {ROOT}")
    print("[receiver] open the MCode Export plugin in Figma and press 'Export to project'")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[receiver] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
