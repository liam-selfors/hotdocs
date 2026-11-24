"""CLI for `hotdocs docs-site build`."""

import json
import sys
from pathlib import Path

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: "list[str] | None" = None) -> int:
    from . import render_docs_site

    if argv is None:
        argv = sys.argv[1:]
    options = {"--repo-root": ".", "--out": None}
    index = 0
    while index < len(argv):
        token = argv[index]
        name, eq, value = token.partition("=")
        if name not in options:
            return _usage_error("unknown argument " + token)
        if not eq:
            if index + 1 >= len(argv):
                return _usage_error(name + " requires a value")
            index += 1
            value = argv[index]
        options[name] = value
        index += 1

    repo_root = Path(options["--repo-root"])
    out_dir = Path(options["--out"]) if options["--out"] is not None else repo_root / "dist" / "docs-site"
    path = repo_root / "verification" / "corpus-graph.json"
    if not path.is_file():
        print("error: " + str(path) + " is missing; run hotdocs corpus-graph build first", file=sys.stderr)
        return 1
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print("error: " + str(path) + " is not valid JSON", file=sys.stderr)
        return 1
    render_docs_site(graph, out_dir)
    print(out_dir)
    return 0
