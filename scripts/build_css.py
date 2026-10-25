"""Compile the Tailwind CSS source into the static stylesheet.

Usage:
    uv run python scripts/build_css.py           # one-off minified build
    uv run python scripts/build_css.py --watch   # rebuild on every template change

The Tailwind standalone binary is downloaded by pytailwindcss on first use, so
no Node.js toolchain is needed. The version is pinned here to keep builds
reproducible across machines.
"""

import sys
from pathlib import Path

import pytailwindcss

TAILWIND_VERSION = "v4.3.3"

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "css" / "input.css"
OUTPUT = ROOT / "static" / "css" / "main.css"


def main() -> None:
    watch = "--watch" in sys.argv
    args = ["-i", str(SOURCE), "-o", str(OUTPUT)]
    # Minify the committed file; keep it readable while developing.
    args.append("--watch" if watch else "--minify")

    pytailwindcss.install(TAILWIND_VERSION)
    pytailwindcss.run(args, cwd=ROOT, live_output=True)


if __name__ == "__main__":
    main()
