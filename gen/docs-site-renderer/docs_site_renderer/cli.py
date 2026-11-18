"""CLI for `hotdocs docs-site build`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

_FLAGS = ("--repo-root", "--out")


def _parse(argv):
    values = {}
    i = 0
    while i < len(argv):
        token = argv[i]
        if "=" in token:
            name, value = token.split("=", 1)
        else:
            name = token
            if i + 1 >= len(argv):
                return None
            i += 1
            value = argv[i]
        if name not in _FLAGS or not value:
            return None
        values[name] = value
        i += 1
    return values


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    values = _parse(list(argv))
    if values is None:
        print("usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]", file=sys.stderr)
        return 2
    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values["--out"]) if "--out" in values else repo_root / "dist" / "docs-site"
    graph_path = repo_root / "verification" / "corpus-graph.json"
    try:
        graph = json.loads(graph_path.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print("cannot read %s: %s" % (graph_path, exc), file=sys.stderr)
        return 1
    render_docs_site(graph, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
