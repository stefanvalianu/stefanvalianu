#!/usr/bin/env python3
"""Build the root README.md from the assets/README.md template.

Replaces marker comments with generated content.
"""

import glob
import os

SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
TEMPLATE = os.path.join(ASSETS_DIR, "README.md")
OUTPUT = os.path.join(REPO_ROOT, "README.md")


def find_header(variant):
    """Find the current header-<variant>-<seed>.svg in assets/."""
    pattern = os.path.join(ASSETS_DIR, f"header-{variant}-*.svg")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No header found for {variant!r}: {pattern}")
    # Most recent if somehow multiple exist
    path = max(matches, key=os.path.getmtime)
    return f"assets/{os.path.basename(path)}"


def main():
    replacements = {
        "<!-- HEADER_DARK -->": find_header("dark"),
        "<!-- HEADER_LIGHT -->": find_header("light"),
    }

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        content = f.read()

    for marker, replacement in replacements.items():
        content = content.replace(marker, replacement)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated {os.path.relpath(OUTPUT, REPO_ROOT)}")


if __name__ == "__main__":
    main()
