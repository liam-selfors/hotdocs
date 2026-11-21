"""CLI for `hotdocs docs-site build`."""

import json
import sys
from pathlib import Path

from . import render_docs_site

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: "list[str] | None" = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    opts = {"--repo-root": ".", "--out": None}
    i = 0
    while i < len(argv):
        token = argv[i]
        name, sep, value = token.partition("=")
        if name not in opts:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if i + 1 >= len(argv):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = argv[i]
        opts[name] = value
        i += 1
    repo_root = Path(opts["--repo-root"])
    out = repo_root / "dist" / "docs-site"
    if opts["--out"] is not None:
        out = Path(opts["--out"])
    graph_path = repo_root / "verification" / "corpus-graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {graph_path}: {exc}", file=sys.stderr)
        return 1
    render_docs_site(graph, out)
    print(str(out))
    return 0
