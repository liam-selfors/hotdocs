"""`hotdocs corpus-graph build [--repo-root=<dir>]`."""

from __future__ import annotations

import sys
from pathlib import Path

USAGE = "usage: hotdocs corpus-graph build [--repo-root=<dir>]"


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "build":
        return _usage_error("expected 'build'")

    repo_root = "."
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--repo-root="):
            repo_root = tok[len("--repo-root="):]
        elif tok == "--repo-root":
            if i + 1 >= len(argv):
                return _usage_error("--repo-root requires a value")
            i += 1
            repo_root = argv[i]
        else:
            return _usage_error(f"unknown argument {tok!r}")
        i += 1

    from . import build_corpus_graph, write_corpus_graph

    try:
        root = Path(repo_root)
        graph = build_corpus_graph(root)
        path = write_corpus_graph(graph, root)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0
