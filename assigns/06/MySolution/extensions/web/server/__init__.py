"""LAMBDA web front-end (extension): HTTP server and language-tool adapter.

Adapted from my Assignment 4 solution (assigns/04/MySolution/server and
web/). The HTTP layer, interpret runner, and browser MVC are kept; the
language tools now call the Assignment 6 core: the shared evaluator for
Interpret, the compiler for Compile, and the reducer and observers for
Execute. This package is an optional extension and is not imported by the
graded core.
"""
import sys
from pathlib import Path

_EXTENSIONS = Path(__file__).resolve().parents[2]      # MySolution/extensions
_CORE = _EXTENSIONS.parent                              # MySolution
for _path in (str(_CORE), str(_EXTENSIONS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
