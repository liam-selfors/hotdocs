"""CLI for `hotdocs corpus-graph build`."""

from __future__ import annotations

import sys
from pathlib import Path

from . import build_corpus_graph, write_corpus_graph


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "build":
        return 2
    repo_root = Path.cwd()
    rest = args[1:]
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--repo-root="):
            repo_root = Path(token[len("--repo-root="):])
        elif token == "--repo-root" and i + 1 < len(rest):
            i += 1
            repo_root = Path(rest[i])
        else:
            return 2
        i += 1
    try:
        graph = build_corpus_graph(repo_root)
        path = write_corpus_graph(graph, repo_root)
    except Exception:
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
