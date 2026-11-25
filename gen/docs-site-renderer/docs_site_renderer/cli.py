"""``hotdocs docs-site build`` command line."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import render_docs_site

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"
_FLAGS = ("--repo-root", "--out")


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    tokens = list(argv)
    values: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if i + 1 >= len(tokens):
                return _usage_error(f"{name} needs a value")
            i += 1
            value = tokens[i]
        values[name] = value
        i += 1

    repo_root = Path(values.get("--repo-root", "."))
    if "--out" in values:
        out_dir = Path(values["--out"])
    else:
        out_dir = repo_root / "dist" / "docs-site"

    path = repo_root / "verification" / "corpus-graph.json"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        print(
            f"error: {path} is missing; run hotdocs corpus-graph build first",
            file=sys.stderr,
        )
        return 1
    try:
        graph = json.loads(data)
    except ValueError as exc:
        message = str(exc).replace("\n", " ")
        print(f"error: {path} is not valid JSON: {message}", file=sys.stderr)
        return 1

    render_docs_site(graph, out_dir)
    print(str(out_dir))
    return 0
