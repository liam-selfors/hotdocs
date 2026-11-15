"""CLI for ``hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]``.

``main`` receives only the tokens after ``hotdocs docs-site build``.
"""

import json
import sys
from pathlib import Path

from . import render_docs_site

_USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    opts = {"--repo-root": ".", "--out": None}
    i = 0
    while i < len(argv):
        name, eq, value = argv[i].partition("=")
        if name not in opts:
            print(_USAGE, file=sys.stderr)
            return 2
        if not eq:
            i += 1
            value = argv[i] if i < len(argv) else ""
        if not value:
            print(_USAGE, file=sys.stderr)
            return 2
        opts[name] = value
        i += 1

    repo_root = Path(opts["--repo-root"])
    out_dir = (
        Path(opts["--out"]) if opts["--out"] else repo_root / "dist" / "docs-site"
    )
    graph_path = repo_root / "verification" / "corpus-graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {graph_path}: {exc}", file=sys.stderr)
        return 1
    render_docs_site(graph, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
