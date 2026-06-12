"""ArchMotion CLI entry point.

Usage:
    python -m archmotion <script.py>
    python -m archmotion --version
"""

from __future__ import annotations

import sys

from archmotion import __version__


def main() -> None:
    """CLI entry point for ArchMotion."""
    if "--version" in sys.argv:
        print(f"archmotion {__version__}")  # noqa: T201
        return

    if len(sys.argv) < 2:
        print(  # noqa: T201
            "Usage: python -m archmotion <script.py>\n"
            f"       archmotion {__version__}"
        )
        sys.exit(1)

    # TODO: Execute user script or YAML file
    script_path = sys.argv[1]
    print(f"Running: {script_path}")  # noqa: T201


if __name__ == "__main__":
    main()
