#!/usr/bin/env python3
"""Assemble le site statique dans _site/ (dashboard/ + data/) ; --serve pour le tester en local."""
from __future__ import annotations

import argparse
import functools
import http.server
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"


def build() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "dashboard", SITE)
    shutil.copytree(ROOT / "data", SITE / "data")
    print(f"✓ site assemblé dans {SITE}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serve", type=int, nargs="?", const=8000, metavar="PORT")
    args = ap.parse_args()
    build()
    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
        print(f"→ http://localhost:{args.serve}")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.serve), handler).serve_forever()
