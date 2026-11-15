"""CLI for `hotdocs corpus-graph build [--repo-root=<dir>]`."""

from __future__ import annotations

import sys
from pathlib import Path

from . import build_corpus_graph, write_corpus_graph


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)
    if not args or args[0] != "build":
        return 2

    repo_root = Path.cwd()
    i = 1
    while i < len(args):
        token = args[i]
        if token.startswith("--repo-root="):
            repo_root = Path(token[len("--repo-root="):])
            i += 1
        elif token == "--repo-root" and i + 1 < len(args):
            repo_root = Path(args[i + 1])
            i += 2
        else:
            return 2

    try:
        graph = build_corpus_graph(repo_root)
        path = write_corpus_graph(graph, repo_root)
    except Exception:
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
