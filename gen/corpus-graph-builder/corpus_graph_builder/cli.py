"""CLI entry point: hotdocs corpus-graph build [--repo-root=<dir>]."""
from __future__ import annotations

import sys
from pathlib import Path

from . import build_corpus_graph, write_corpus_graph


def main(argv: list[str] | None = None) -> int:
    try:
        if argv is None:
            argv = sys.argv[1:]

        if len(argv) == 0 or argv[0] != "build":
            return 2

        rest = argv[1:]
        repo_root = Path(".")
        i = 0
        while i < len(rest):
            arg = rest[i]
            if arg == "--repo-root":
                if i + 1 >= len(rest):
                    return 2
                repo_root = Path(rest[i + 1])
                i += 2
            elif arg.startswith("--repo-root="):
                repo_root = Path(arg[len("--repo-root="):])
                i += 1
            else:
                return 2
    except Exception:
        return 2

    try:
        graph = build_corpus_graph(repo_root)
        path = write_corpus_graph(graph, repo_root)
    except Exception:
        return 1

    print(path)
    return 0