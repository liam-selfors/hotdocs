#!/usr/bin/env python3
"""scaffold_component.py — stamp out a new component's directory layout.

HAND-AUTHORED REPO TOOL, kept for its old flags: a thin wrapper over the
`spec-scaffolder` component (`D299`), which `hotdocs component new` also
reaches. Creates empty structure and placeholder frontmatter only — never
requirements, acceptance criteria, or any other normative content.

Usage:
    python tools/scaffold_component.py <name> [--title "Human Title"]
        [--owners team1,team2] [--depends-on comp-a,comp-b]
        [--realizes P-FOO,P-BAR] [--sealed]

`<name>` is the kebab-case directory name (e.g. `my-new-thing` ->
`specs/components/my-new-thing/`, id `comp-my-new-thing`).

Refuses to overwrite an existing component directory.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _scaffolder():
    path = REPO_ROOT / "gen" / "spec-scaffolder" / "spec_scaffolder.py"
    spec = importlib.util.spec_from_file_location("spec_scaffolder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_scaffolder"] = module
    spec.loader.exec_module(module)
    return module


def _split(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name", help="kebab-case component directory name")
    parser.add_argument("--title", default=None, help="human-readable title (default: title-cased name)")
    parser.add_argument("--owners", default="pipeline-team", help="comma-separated owners list")
    parser.add_argument("--depends-on", default="", help="comma-separated comp-<id>s")
    parser.add_argument("--realizes", default="", help="comma-separated P-<id>s")
    parser.add_argument("--sealed", action="store_true", help="mark sealed: true (hand-maintained, no realizes needed)")
    args = parser.parse_args(argv)

    try:
        comp_dir = _scaffolder().new_component(
            REPO_ROOT, args.name, title=args.title, owners=_split(args.owners),
            depends_on=_split(args.depends_on), realizes=_split(args.realizes), sealed=args.sealed,
        )
    except (ValueError, FileExistsError) as exc:
        sys.exit(f"error: {exc}")

    print(f"Scaffolded {comp_dir.relative_to(REPO_ROOT)}/")
    if not args.sealed and not args.realizes:
        print("warning: no --realizes given — R-LINT-006 will fail until "
              "this non-sealed component lists at least one P-id")
    print("Next: fill in component.md's Purpose/Scope, then add real files "
          "under requirements/ and acceptance/ (not this tool's job).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
