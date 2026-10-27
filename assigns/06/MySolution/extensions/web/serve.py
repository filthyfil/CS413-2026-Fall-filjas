"""Start the web front-end extension. From assigns/06:

    .venv/bin/python MySolution/extensions/web/serve.py [--port N]

then open http://127.0.0.1:5000/. Requires Flask (see README.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from server.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
