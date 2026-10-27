"""CLI entry point for the Provenance Checker.

See `interface/cli.md`:

    hotdocs provenance check <component-id> \
        --spec-bundle-hash=<h> --gate-versions=<json> \
        [--repo-root=<dir>] [--format=json|text]

Exit codes:
  0 — command completed (a reported "miss" is still exit 0).
  2 — usage error (malformed hash, unknown component id, or malformed
      --gate-versions JSON).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

from .core import ProvenanceCheckResult, check_provenance

# A component id is either the bare slug or the full `comp-<slug>` form
# (see specs/glossary.md), always lowercase alphanumerics separated by
# single hyphens.
_COMPONENT_ID_RE = re.compile(r"^(comp-)?[a-z0-9]+(-[a-z0-9]+)*$")

# spec_bundle_hash is an opaque lowercase hex digest, produced elsewhere
# (spec-bundle-assembler's job) and only ever compared, never computed,
# here. Malformed just means "not a plausible hex digest".
_HASH_RE = re.compile(r"^[0-9a-f]{8,}$")


class UsageError(Exception):
    """Raised for malformed CLI input; maps to exit code 2."""


def _validate_component_id(component_id: str) -> None:
    if not component_id or not _COMPONENT_ID_RE.match(component_id):
        raise UsageError(f"unknown component id: {component_id!r}")


def _validate_hash(spec_bundle_hash: str) -> None:
    if not spec_bundle_hash or not _HASH_RE.match(spec_bundle_hash):
        raise UsageError(f"malformed spec bundle hash: {spec_bundle_hash!r}")


def _parse_gate_versions(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"malformed --gate-versions JSON: {exc}") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
    ):
        raise UsageError("--gate-versions must be a JSON object of string to string")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotdocs provenance", description="Provenance Checker"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    check_parser = subparsers.add_parser(
        "check", help="Report hit/miss for a component's committed provenance."
    )
    check_parser.add_argument("component_id")
    check_parser.add_argument("--spec-bundle-hash", required=True, dest="spec_bundle_hash")
    check_parser.add_argument("--gate-versions", required=True, dest="gate_versions")
    check_parser.add_argument("--repo-root", default=".", dest="repo_root")
    check_parser.add_argument(
        "--format", choices=["json", "text"], default="json", dest="format"
    )

    return parser


def _format_result(result: ProvenanceCheckResult, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(result.to_dict(), indent=2, sort_keys=True)
    return "HIT" if result.hit else "MISS"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.action != "check":
        parser.error(f"unknown action: {args.action}")
        return 2

    try:
        _validate_component_id(args.component_id)
        _validate_hash(args.spec_bundle_hash)
        gate_versions = _parse_gate_versions(args.gate_versions)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = check_provenance(
        component_id=args.component_id,
        spec_bundle_hash=args.spec_bundle_hash,
        gate_versions=gate_versions,
        repo_root=Path(args.repo_root),
    )

    print(_format_result(result, args.format))
    return 0


if __name__ == "__main__":
    sys.exit(main())