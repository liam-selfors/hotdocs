"""Command line for `hotdocs docs-site build`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    values = {"--repo-root": ".", "--out": "dist/docs-site/"}
    i = 0
    while i < len(argv):
        token = argv[i]
        name, sep, value = token.partition("=")
        if name not in values:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if i + 1 >= len(argv):
                return _usage_error(f"{name} needs a value")
            i += 1
            value = argv[i]
        values[name] = value
        i += 1
    path = Path(values["--repo-root"]) / "verification" / "corpus-graph.json"
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    out_dir = Path(values["--out"])
    render_docs_site(graph, out_dir)
    print(out_dir)
    return 0
