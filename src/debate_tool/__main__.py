"""Lets `python -m debate_tool` run the CLI, same as the `debate-tool` console script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
