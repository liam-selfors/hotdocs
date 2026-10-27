"""CLI entry point implementing `interface/cli.md`:

    hotdocs docs-site build [--repo-root=<dir>] [--out=<dir>]

Exit codes:
    0  Site rendered to --out.
    1  corpus-graph.json missing or unreadable.
    2  Usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .graph import CorpusGraphReadError, load_corpus_graph
from .renderer import render_docs_site

DEFAULT_OUT_DIR = Path("dist") / "docs-site"


def _strip_known_subcommand_tokens(args: "list[str]") -> "list[str]":
    """Tolerates being invoked either with the `docs-site build` subcommand
    tokens still attached (e.g. a top-level `hotdocs` dispatcher forwarding
    its full argv) or already stripped down to just this command's own
    options."""
    while args[:1] == ["docs-site"]:
        args = args[1:]
    while args[:1] == ["build"]:
        args = args[1:]
    return args


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotdocs docs-site build",
        description="Render verification/corpus-graph.json into the docs/graph explorer site.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing verification/corpus-graph.json (default: .)",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help=f"Output directory for the rendered site (default: {DEFAULT_OUT_DIR})",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = _strip_known_subcommand_tokens(raw_args)

    parser = build_arg_parser()
    try:
        ns = parser.parse_args(args)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    repo_root = Path(ns.repo_root)
    out_dir = Path(ns.out)

    try:
        graph = load_corpus_graph(repo_root)
    except CorpusGraphReadError as exc:
        print(f"hotdocs docs-site build: {exc}", file=sys.stderr)
        return 1

    render_docs_site(graph, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())