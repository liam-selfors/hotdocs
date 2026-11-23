"""`hotdocs docs-site build` command line."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"
FLAGS = ("--repo-root", "--out")


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    values: dict[str, str] = {}
    i = 0
    while i < len(argv):
        token = argv[i]
        name, sep, value = token.partition("=")
        if name not in FLAGS:
            return _usage_error(f"unknown argument: {token}")
        if not sep:
            if i + 1 >= len(argv):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = argv[i]
        values[name] = value
        i += 1

    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values["--out"]) if "--out" in values else repo_root / "dist" / "docs-site"
    path = repo_root / "verification" / "corpus-graph.json"
    if not path.is_file():
        print(
            f"error: {path} is missing; run hotdocs corpus-graph build first",
            file=sys.stderr,
        )
        return 1
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
        return 1
    render_docs_site(graph, out_dir)
    print(out_dir)
    return 0
