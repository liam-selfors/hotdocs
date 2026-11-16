"""CLI: ``hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]``.

``main`` receives only the tokens after ``hotdocs docs-site build``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

_USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    opts: dict = {"--repo-root": ".", "--out": None}

    i = 0
    while i < len(args):
        name, sep, value = args[i].partition("=")
        if name not in opts:
            print(_USAGE, file=sys.stderr)
            return 2
        if not sep:
            i += 1
            if i >= len(args):
                print(_USAGE, file=sys.stderr)
                return 2
            value = args[i]
        if not value:
            print(_USAGE, file=sys.stderr)
            return 2
        opts[name] = value
        i += 1

    repo_root = Path(opts["--repo-root"])
    out_dir = Path(opts["--out"]) if opts["--out"] is not None else repo_root / "dist" / "docs-site"
    graph_path = repo_root / "verification" / "corpus-graph.json"

    try:
        graph = json.loads(graph_path.read_bytes())
    except (OSError, ValueError) as exc:
        print(f"cannot read {graph_path}: {exc}", file=sys.stderr)
        return 1

    render_docs_site(graph, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
