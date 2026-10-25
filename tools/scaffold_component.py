#!/usr/bin/env python3
"""scaffold_component.py — stamp out a new component's D15 directory layout.

HAND-AUTHORED REPO TOOL, not a spec-driven component (SPEC_GUIDELINES.md
§1's `tools/` entry). Creates empty structure and placeholder frontmatter
only — it never authors requirements, acceptance criteria, or any other
normative content. That remains a human's (or an assist agent's) job; this
just removes the mechanical cost of typing out the same directory shape
and frontmatter block by hand every time, which is all D15's
one-file-per-unit layout actually costs a new component's author.

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
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

COMPONENT_MD_TEMPLATE = """---
id: comp-{name}
title: {title}
status: draft
owners: [{owners}]
depends_on: [{depends_on}]
realizes: [{realizes}]
sealed: {sealed}
---

# {title}

## Purpose

TODO: one paragraph. What does this component do, and why does it exist
— what would be missing from the pipeline without it? Dependent-safe
(D34): no decision citations, no historical justification — that
belongs in Rationale below. Delete the Rationale section entirely if
this component genuinely needs none.

## Rationale

TODO, or delete this section — decision citations, historical
justification, why this design was arrived at. Never included in
anything assembled for a dependent.

## Scope

**In scope:** TODO.

**Out of scope:** TODO.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

TODO — or `None.` if there genuinely are none yet.

## Change log

- Initial draft.
"""

CONSTRAINTS_TEMPLATE = """# {title} — Non-Functional Constraints

- TODO: at least one real constraint (determinism, performance, network/
  model-call posture, idempotency — see other components' `constraints.md`
  for the shape these usually take). Delete this file's placeholder bullet
  once real ones exist; `constraints.md` stays one flat file (D15/SPEC_
  GUIDELINES.md §3.4), never split per-constraint.
"""

DIR_README_TEMPLATE = """# {heading}

{body}

Remove this file once real content exists here — it is scaffolding, not
a governed spec (`SPEC_GUIDELINES.md` §1: a `README.md` under `specs/`
is always skipped by the linter and every other tool).
"""

DIR_README_BODIES = {
    "requirements": (
        "One `R-{NAME}-NNN.md` per requirement (SPEC_GUIDELINES.md §3.4). "
        "Each file is exactly one requirement, using at least one RFC 2119 "
        "keyword (MUST / MUST NOT / SHOULD / SHOULD NOT / MAY)."
    ),
    "acceptance": (
        "One `AC-{NAME}-NNN.md` per acceptance criterion (SPEC_GUIDELINES.md "
        "§5). Each file needs a `Covers: R-<id>` tag, a `Kind:` tag "
        "(`compiled` / `generated-test` / `llm-judge`), and a complete "
        "Given/When/Then Gherkin block."
    ),
    "interface": (
        "`cli.md` and/or `library.md` for this component's public contract "
        "(both optional — a component with neither is purely internal); "
        "`data/<TypeName>.md`, one schema per file, for any data types it "
        "defines; `guarantees/G-{NAME}-NNN.md`, one behavioral/non-"
        "functional guarantee per file, for anything a *dependent* might "
        "want to narrow its own blast-radius inclusion to (D16, optional)."
    ),
}


def _validate_name(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", name):
        sys.exit(f"error: '{name}' is not kebab-case (e.g. 'my-new-thing')")


def _title_case(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("-"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name", help="kebab-case component directory name")
    parser.add_argument("--title", default=None, help="human-readable title (default: title-cased name)")
    parser.add_argument("--owners", default="pipeline-team", help="comma-separated owners list")
    parser.add_argument("--depends-on", default="", help="comma-separated comp-<id>s")
    parser.add_argument("--realizes", default="", help="comma-separated P-<id>s")
    parser.add_argument("--sealed", action="store_true", help="mark sealed: true (hand-maintained, no realizes needed)")
    args = parser.parse_args(argv)

    _validate_name(args.name)
    title = args.title or _title_case(args.name)
    comp_dir = REPO_ROOT / "specs" / "components" / args.name
    if comp_dir.exists():
        sys.exit(f"error: {comp_dir} already exists — refusing to overwrite")

    depends_on = ", ".join(s.strip() for s in args.depends_on.split(",") if s.strip())
    realizes = ", ".join(s.strip() for s in args.realizes.split(",") if s.strip())
    owners = ", ".join(s.strip() for s in args.owners.split(",") if s.strip())

    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "interface" / "data").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)

    (comp_dir / "component.md").write_text(COMPONENT_MD_TEMPLATE.format(
        name=args.name, title=title, owners=owners, depends_on=depends_on,
        realizes=realizes, sealed="true" if args.sealed else "false",
    ))
    (comp_dir / "constraints.md").write_text(CONSTRAINTS_TEMPLATE.format(title=title))

    name_upper = args.name.upper().replace("-", "")
    for dirname, body in DIR_README_BODIES.items():
        heading = dirname.capitalize()
        (comp_dir / dirname / "README.md").write_text(DIR_README_TEMPLATE.format(
            heading=heading, body=body.format(NAME=name_upper),
        ))

    print(f"Scaffolded {comp_dir.relative_to(REPO_ROOT)}/")
    if not args.sealed and not realizes:
        print("warning: no --realizes given — R-LINT-006 will fail until "
              "this non-sealed component lists at least one P-id")
    print("Next: fill in component.md's Purpose/Scope, then add real files "
          "under requirements/ and acceptance/ (not this tool's job).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
