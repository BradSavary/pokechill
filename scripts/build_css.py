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
    # Always minify, even in watch mode: the output file is committed, so it
    # must be identical whichever mode produced it.
    args = ["-i", str(SOURCE), "-o", str(OUTPUT), "--minify"]
    if "--watch" in sys.argv:
        args.append("--watch")

    # auto_install downloads the pinned binary only if it is missing
    pytailwindcss.run(args, cwd=ROOT, live_output=True, auto_install=True, version=TAILWIND_VERSION)


if __name__ == "__main__":
    main()
