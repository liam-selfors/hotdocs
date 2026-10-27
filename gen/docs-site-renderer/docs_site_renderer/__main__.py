"""Allows `python -m docs_site_renderer ...` to invoke the CLI directly."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())