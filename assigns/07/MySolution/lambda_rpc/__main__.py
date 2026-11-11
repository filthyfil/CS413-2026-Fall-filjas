"""Start the development server: ``python -m lambda_rpc [--host H] [--port P]``."""

import argparse
import logging

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="LAMBDA3 JSON-RPC service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_app().run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
