#!/usr/bin/env python3
"""
Watch the v1.0 build and package every completed batch.

  python3 scripts/package_watch.py            # watch every 3 minutes
  python3 scripts/package_watch.py --once     # package right now and exit
  python3 scripts/package_watch.py --interval 120

Whenever the set of built v1 screens changes it waits for the set to be
*stable* for one full interval (workers create the HTML before the CSS, so
packing the instant a page appears would ship a half-written screen), then
measures, regenerates the gallery, rebuilds the zip, checks the asset
references and drops a dated copy of the archive next to it.

If the package fails — usually because a worker is mid-write — it retries on
the next cycle rather than marking the batch done.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def built() -> list[str]:
    return sorted(p.name for p in ROOT.glob("v1-*.html"))


def package() -> bool:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/package_v1_batch.py")],
        cwd=ROOT,
    )
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=180)
    args = ap.parse_args()

    last: list[str] | None = None
    changed_at = time.time()
    packaged: list[str] | None = None

    while True:
        now = built()
        if now != last:
            added = sorted(set(now) - set(last)) if last else []
            if added:
                print(f"[watch] {len(added)} new: {', '.join(added)}", flush=True)
            last = now
            changed_at = time.time()

        stable_for = time.time() - changed_at
        if last and stable_for >= args.interval and last != packaged:
            print(f"[watch] {len(last)} screen(s) stable for {stable_for:.0f}s — packaging", flush=True)
            if package():
                packaged = list(last)
                print(f"[watch] batch packaged", flush=True)
            else:
                print("[watch] package failed, retrying next cycle", flush=True)

        if args.once:
            return 0
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
