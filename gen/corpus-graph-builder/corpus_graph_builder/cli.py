"""hotdocs corpus-graph build [--repo-root=<dir>]"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "build":
        return 2

    repo_root = Path.cwd()
    rest = argv[1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("--repo-root="):
            repo_root = Path(tok[len("--repo-root="):])
        elif tok == "--repo-root" and i + 1 < len(rest):
            i += 1
            repo_root = Path(rest[i])
        else:
            return 2
        i += 1

    try:
        from corpus_graph_builder import build_corpus_graph, write_corpus_graph

        graph = build_corpus_graph(repo_root)
        path = write_corpus_graph(graph, repo_root)
    except Exception:
        return 1
    print(str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
