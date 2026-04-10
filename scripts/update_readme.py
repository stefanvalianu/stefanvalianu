#!/usr/bin/env python3
"""Build the root README.md from the assets/README.md template.

Replaces marker comments with generated content:

    <!-- HEADER -->  →  GitHub dark/light mode picture switcher
                        referencing assets/header-{dark,light}.svg
"""

import os

SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
TEMPLATE = os.path.join(REPO_ROOT, "assets", "README.md")
OUTPUT = os.path.join(REPO_ROOT, "README.md")

HEADER_HTML = """\
<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/header-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/header-light.svg">
    <img src="assets/header-dark.svg" alt="ASCII art header" width="800">
  </picture>
</div>"""

REPLACEMENTS = {
    "<!-- HEADER -->": HEADER_HTML,
}


def main():
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        content = f.read()

    for marker, replacement in REPLACEMENTS.items():
        content = content.replace(marker, replacement)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated {os.path.relpath(OUTPUT, REPO_ROOT)}")


if __name__ == "__main__":
    main()
