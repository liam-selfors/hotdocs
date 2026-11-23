"""CLI for `hotdocs docs-site build`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

USAGE = "usage: hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]"
_FLAGS = ("--repo-root", "--out")


class _UsageError(Exception):
    pass


def _parse(argv: list[str]) -> dict:
    opts: dict = {}
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name not in _FLAGS:
            raise _UsageError(f"unknown argument {token}")
        if not eq:
            if i + 1 >= len(argv):
                raise _UsageError(f"{name} requires a value")
            value = argv[i + 1]
            i += 1
        opts[name] = value
        i += 1
    return opts


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    repo_root = Path(opts.get("--repo-root", "."))
    if "--out" in opts:
        out_dir = Path(opts["--out"])
    else:
        out_dir = repo_root / "dist" / "docs-site"

    path = repo_root / "verification" / "corpus-graph.json"
    if not path.exists():
        print(
            f"error: {path} is missing; run hotdocs corpus-graph build first",
            file=sys.stderr,
        )
        return 1
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        message = str(exc).replace("\n", " ")
        print(f"error: cannot read {path}: {message}", file=sys.stderr)
        return 1

    from . import render_docs_site

    render_docs_site(graph, out_dir)
    print(out_dir)
    return 0
