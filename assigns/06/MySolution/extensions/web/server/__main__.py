"""Start the local server: python -m server [--port N] (run from extensions/web),
or python3.12 MySolution/extensions/web/serve.py from assigns/06."""
import argparse

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="LAMBDA compiler web front-end")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app = create_app()
    print(f"Open http://127.0.0.1:{args.port}/ (Ctrl+C to quit)")
    try:
        # Loopback only; threaded so Stop can arrive while Interpret runs.
        app.run(host="127.0.0.1", port=args.port, threaded=True)
    finally:
        app.config["TOOLS"].shutdown()


if __name__ == "__main__":
    main()
