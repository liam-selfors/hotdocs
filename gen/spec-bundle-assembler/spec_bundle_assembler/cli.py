from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path


def _default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for p in (cwd, *cwd.parents):
        if (p / ".git").exists():
            return p
    return cwd


def main(argv: list[str] | None = None) -> int:
    from . import PreconditionFailure, assemble

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="hotdocs assemble")
    parser.add_argument("component_id")
    parser.add_argument("--mode", choices=["cold", "hint"], default="cold")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _default_repo_root()

    try:
        bundle = assemble(args.component_id, repo_root, mode=args.mode)
    except PreconditionFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(dataclasses.asdict(bundle), indent=2))
    else:
        print(f"component: {bundle.component_id}")
        print(f"mode: {args.mode}")
        print(f"hash: {bundle.spec_bundle_hash}")
        deps = ", ".join(sorted(bundle.dependency_interfaces)) or "(none)"
        print(f"dependencies: {deps}")

    return 0