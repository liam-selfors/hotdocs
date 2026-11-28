"""``hotdocs docs-site build`` command line."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"
_FLAGS = ("--repo-root", "--out")


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    values = {}
    i = 0
    while i < len(args):
        token = args[i]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if i + 1 >= len(args):
                return _usage_error(f"{name} needs a value")
            i += 1
            value = args[i]
        values[name] = value
        i += 1

    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values.get("--out", repo_root / "dist" / "docs-site"))
    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        print(
            f"error: {graph_path} is missing; run hotdocs corpus-graph build first",
            file=sys.stderr,
        )
        return 1
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except ValueError:
        print(f"error: {graph_path} is not valid JSON", file=sys.stderr)
        return 1
    render_docs_site(graph, out_dir)
    return 0
