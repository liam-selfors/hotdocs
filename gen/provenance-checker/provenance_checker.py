"""provenance-checker: decides whether committed provenance proves a component
was already verified against the exact current spec state.

Read-only: never writes, modifies, or deletes any file. No network access,
no model calls, never a cache-manager client.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ProvenanceCheckResult",
    "ProvenanceKey",
    "SealedKey",
    "check_provenance",
    "current_provenance_key",
    "current_sealed_key",
    "check_sealed_provenance",
    "main",
]

_COMPONENT_ID_RE = r"(comp-)?[a-z0-9]+(-[a-z0-9]+)*"
_HASH_ARG_RE = r"sha256:[0-9a-f]+"
_COMP_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
_WRITTEN_AT_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"

_MANIFEST_KEYS = {
    "kind",
    "version",
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "characterization",
    "written_at",
}
_CHARACTERIZATION_KEYS = {"overall", "criteria_passed", "criteria_total"}

_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")


# ---------------------------------------------------------------------------
# Result / key types
# ---------------------------------------------------------------------------


class ProvenanceCheckResult(dict):
    """A dict of the `ProvenanceCheckResult` fields, also readable as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict


@dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _get(obj, key):
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


def _tool_root() -> Path:
    gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen.parent


def _load(repo_root, rel: str, module_name: str):
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / f"{module_name}.py"
    if not path.is_file():
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _match(pattern: str, value) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _valid_source_path(value) -> bool:
    return _match(_SOURCE_PATH_RE, value) and value.split("/")[0] != "gen"


def _trust_judge_provenance() -> bool:
    return os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "").strip().lower() != "false"


def _miss() -> ProvenanceCheckResult:
    return ProvenanceCheckResult(
        hit=False, verification_report=None, license_scan=None, secret_scan=None
    )


# ---------------------------------------------------------------------------
# Generated components
# ---------------------------------------------------------------------------


def check_provenance(
    component_id: str, spec_bundle_hash: str, gate_versions: dict, repo_root: Path
) -> ProvenanceCheckResult:
    path = Path(repo_root) / "gen" / _slug(component_id) / ".provenance.json"
    if not path.is_file():
        return _miss()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return _miss()
    if manifest.get("gate_versions") != gate_versions:
        return _miss()
    report = manifest.get("verification_report") or {}
    criteria = report.get("criteria") or []
    has_judge = any(c.get("kind") == "llm-judge" for c in criteria)
    if has_judge and not _trust_judge_provenance():
        return _miss()
    return ProvenanceCheckResult(
        hit=True,
        verification_report=manifest.get("verification_report"),
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey:
    repo_root = Path(repo_root)
    assembler = _load(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    compiler = _load(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
    compiler_version = compiler.GATE_VERSION
    author = _load(repo_root, "gen/test-author", "test_author")
    author_version = author.GATE_VERSION
    verifier = _load(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    verifier_version = verifier.GATE_VERSION
    license_scanner = _load(repo_root, "gen/license-scanner", "license_scanner")
    license_version = license_scanner.gate_version(repo_root)
    secret_scanner = _load(repo_root, "gen/secret-scanner", "secret_scanner")
    secret_version = secret_scanner.gate_version(repo_root)
    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_versions={
            "compiler": compiler_version,
            "generated_test": author_version,
            "verifier": verifier_version,
            "license_scanner": license_version,
            "secret_scanner": secret_version,
        },
    )


# ---------------------------------------------------------------------------
# Sealed components
# ---------------------------------------------------------------------------


def _frontmatter_field(lines: list, name: str) -> str:
    prefix = name + ":"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise ValueError(f"component.md frontmatter has no {name} line")


def _source_hash(base: Path) -> str:
    entries = []
    for path in base.rglob("*"):
        rel = path.relative_to(base)
        if (
            path.is_file()
            and "__pycache__" not in rel.parts[:-1]
            and path.name != ".sealed-provenance.json"
        ):
            entries.append((rel.as_posix(), path))
    digest = hashlib.sha256()
    for rel, path in sorted(entries):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id: str, repo_root: Path):
    repo_root = Path(repo_root)
    component_md = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not component_md.is_file():
        return None
    text = component_md.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.split("\n---", 1)[0].splitlines()]
    if "sealed: true" not in lines:
        return None
    owners_raw = _frontmatter_field(lines, "owners")
    owners_match = re.fullmatch(r"\[(.*)\]", owners_raw)
    owners = [item.strip() for item in owners_match.group(1).split(",")] if owners_match else []
    if not owners or not all(_match(_OWNER_RE, o) for o in owners):
        raise ValueError(f"invalid owners in component.md: {owners_raw!r}")
    source_path = _frontmatter_field(lines, "source_path")
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid source_path in component.md: {source_path!r}")
    source_hash = _source_hash(repo_root / source_path)
    verifier = _load(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier.GATE_VERSION,
    )


def _valid_sealed_manifest(m) -> bool:
    if not isinstance(m, dict) or set(m) != _MANIFEST_KEYS:
        return False
    c = m["characterization"]
    if not isinstance(c, dict) or set(c) != _CHARACTERIZATION_KEYS:
        return False
    owners = m["owners"]
    passed = c["criteria_passed"]
    total = c["criteria_total"]
    return (
        m["kind"] == "sealed-provenance"
        and type(m["version"]) is int
        and m["version"] == 1
        and _match(_COMP_RE, m["component_id"])
        and isinstance(owners, list)
        and len(owners) > 0
        and all(_match(_OWNER_RE, o) for o in owners)
        and _valid_source_path(m["source_path"])
        and _match(_SOURCE_HASH_RE, m["source_hash"])
        and _match(_VERIFIER_RE, m["verifier_version"])
        and c["overall"] in ("pass", "fail")
        and type(passed) is int
        and type(total) is int
        and 0 <= passed <= total
        and (c["overall"] != "pass" or (total >= 1 and passed == total))
        and _match(_WRITTEN_AT_RE, m["written_at"])
    )


def _sealed_miss(reason: str) -> dict:
    return {
        "hit": False,
        "sealed": reason != "not_sealed",
        "reason": reason,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }


def check_sealed_provenance(component_id: str, repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    key = current_sealed_key(component_id, repo_root)
    if key is None:
        return _sealed_miss("not_sealed")
    manifest_path = repo_root / key.source_path / ".sealed-provenance.json"
    if not manifest_path.exists():
        return _sealed_miss("manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _sealed_miss("manifest_invalid")
    if not _valid_sealed_manifest(manifest):
        return _sealed_miss("manifest_invalid")
    if (
        manifest["component_id"] != "comp-" + _slug(component_id)
        or manifest["source_path"] != key.source_path
    ):
        return _sealed_miss("component_mismatch")
    if manifest["source_hash"] != key.source_hash:
        return _sealed_miss("source_changed")
    if manifest["owners"] != key.owners:
        return _sealed_miss("owners_changed")
    if manifest["verifier_version"] != key.verifier_version:
        return _sealed_miss("verifier_changed")
    if manifest["characterization"]["overall"] != "pass":
        return _sealed_miss("characterization_failed")
    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": manifest["characterization"]["overall"]},
        "license_scan": None,
        "secret_scan": None,
        "owners": list(manifest["owners"]),
        "source_hash": manifest["source_hash"],
        "written_at": manifest["written_at"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _usage(message: str) -> int:
    print(f"usage error: {message}", file=sys.stderr)
    print(
        "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
        "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]",
        file=sys.stderr,
    )
    return 2


def main(argv) -> int:
    argv = list(argv)
    if argv[:1] != ["check"]:
        return _usage("expected subcommand 'check'")
    rest = argv[1:]
    values = {}
    positionals = []
    i = 0
    while i < len(rest):
        token = rest[i]
        name, eq, value = token.partition("=")
        if name in _FLAGS:
            if not eq:
                if i + 1 >= len(rest):
                    return _usage(f"{name} requires a value")
                i += 1
                value = rest[i]
            values[name] = value
        elif token.startswith("-"):
            return _usage(f"unknown argument {token!r}")
        else:
            positionals.append(token)
        i += 1

    if len(positionals) != 1:
        return _usage("expected exactly one <component-id>")
    component_id = positionals[0]
    if not _match(_COMPONENT_ID_RE, component_id):
        return _usage(f"invalid component id {component_id!r}")
    if "--spec-bundle-hash" not in values:
        return _usage("missing --spec-bundle-hash")
    spec_bundle_hash = values["--spec-bundle-hash"]
    if not _match(_HASH_ARG_RE, spec_bundle_hash):
        return _usage(f"invalid --spec-bundle-hash {spec_bundle_hash!r}")
    if "--gate-versions" not in values:
        return _usage("missing --gate-versions")
    try:
        gate_versions = json.loads(values["--gate-versions"])
    except ValueError:
        return _usage("--gate-versions is not valid JSON")
    if not isinstance(gate_versions, dict) or not all(
        isinstance(v, str) for v in gate_versions.values()
    ):
        return _usage("--gate-versions must be a JSON object of strings to strings")
    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format {fmt!r}")
    repo_root = Path(values.get("--repo-root", "."))

    result = check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    if fmt == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
