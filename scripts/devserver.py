#!/usr/bin/env python3
"""Minimal static file server for local preview of the 4D survey site.

Serves the repo root on the given port without relying on os.getcwd()
(which is unavailable in some sandboxes). Not used in production — GitHub
Pages serves the static files directly.

Usage: python scripts/devserver.py [port]
"""
import functools
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8766

Handler = functools.partial(SimpleHTTPRequestHandler, directory=ROOT)
print(f"Serving {ROOT} at http://localhost:{PORT}/")
ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
