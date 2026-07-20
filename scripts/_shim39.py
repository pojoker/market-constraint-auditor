"""Run a project script under Python 3.9 by injecting `from __future__ import annotations`.

Usage: python3 scripts/_shim39.py <script> [args...]
Workaround for PEP 604 (`int | None`) annotations when only system Python 3.9 is available.
"""
import sys

path = sys.argv[1]
with open(path) as f:
    src = "from __future__ import annotations\n" + f.read()
sys.argv = [path] + sys.argv[2:]
g = dict(__name__="__main__", __file__=path)
exec(compile(src, path, "exec"), g)
