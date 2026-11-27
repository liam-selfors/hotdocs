"""Command line for `hotdocs docs-site build`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"

_FLAGS = {"--repo-root": "repo_root", "--out": "out"}


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    values = {"repo_root": ".", "out": "dist/docs-site/"}
    index = 0
    while index < len(args):
        token = args[index]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if index + 1 == len(args):
                return _usage_error(f"{name} needs a value")
            index += 1
            value = args[index]
        values[_FLAGS[name]] = value
        index += 1

    path = Path(values["repo_root"]) / "verification" / "corpus-graph.json"
    if not path.is_file():
        print(f"error: {path} is missing; run hotdocs corpus-graph build first", file=sys.stderr)
        return 1
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print(f"error: {path} is not valid JSON", file=sys.stderr)
        return 1
    render_docs_site(graph, Path(values["out"]))
    return 0
