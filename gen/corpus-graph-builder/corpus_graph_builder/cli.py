"""`hotdocs corpus-graph build [--repo-root=<dir>]` (`interface/cli.md`).

Exit codes:
    0  verification/corpus-graph.json written
    1  a required upstream result was missing
    2  usage error

Intended to be invoked on every merge to `main` (R-GRAPH-007) — this
module makes no scheduling decisions of its own; whatever drives CI is
responsible for the cadence.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .builder import build_corpus_graph, write_corpus_graph


def _default_repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return Path.cwd()
    return Path(completed.stdout.strip())


def _build(repo_root: Path | None) -> int:
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    try:
        graph = build_corpus_graph(root)
    except Exception as exc:  # any upstream/query failure maps to exit 1
        print(f"corpus-graph build: {exc}", file=sys.stderr)
        return 1
    write_corpus_graph(graph, root)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs corpus-graph")
    subparsers = parser.add_subparsers(dest="action")
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--repo-root", dest="repo_root", type=Path, default=None)

    args = sys.argv[1:] if argv is None else argv
    try:
        namespace = parser.parse_args(args)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    if namespace.action != "build":
        parser.print_usage(sys.stderr)
        return 2

    return _build(namespace.repo_root)


if __name__ == "__main__":
    sys.exit(main())
