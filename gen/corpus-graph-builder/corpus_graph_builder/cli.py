"""hotdocs corpus-graph build [--repo-root=<dir>]"""

import sys
from pathlib import Path

from corpus_graph_builder import build_corpus_graph, write_corpus_graph


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "build":
        return 2
    repo_root = "."
    rest = args[1:]
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--repo-root="):
            repo_root = token[len("--repo-root="):]
        elif token == "--repo-root" and i + 1 < len(rest):
            repo_root = rest[i + 1]
            i += 1
        else:
            return 2
        i += 1
    try:
        root = Path(repo_root)
        path = write_corpus_graph(build_corpus_graph(root), root)
    except Exception:
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
