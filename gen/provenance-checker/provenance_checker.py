"""provenance-checker: decides whether committed provenance proves a component
was already verified against the exact current spec state (R-PROVCHECK-001..008).

Read-only: never writes, modifies or deletes any file. No network, no model call.
"""

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Result / key types
# ---------------------------------------------------------------------------


class ProvenanceCheckResult(dict):
    """`ProvenanceCheckResult`: a dict that also exposes its fields as attributes."""

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

_COMPONENT_ID_RE = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SOURCE_PATH_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
)
_SOURCE_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VERIFIER_VERSION_RE = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")
_WRITTEN_AT_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

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

_SEALED_MANIFEST_NAME = ".sealed-provenance.json"


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read(obj, key):
    """Dual dict-or-attribute access for any value read from a dependency."""
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load(module_name, rel_path, repo_root):
    """Load a dependency from `<repo_root>/<rel_path>`, else from the tool root's."""
    base = Path(repo_root) / rel_path
    if not base.is_dir():
        base = _tool_root() / rel_path
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _trust_judge_provenance():
    value = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "")
    return value.strip().lower() != "false"


def _matches(regex, value):
    return isinstance(value, str) and regex.fullmatch(value) is not None


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_owners(owners):
    return (
        isinstance(owners, list)
        and len(owners) > 0
        and all(_matches(_OWNER_RE, o) for o in owners)
    )


def _valid_source_path(source_path):
    return _matches(_SOURCE_PATH_RE, source_path) and source_path.split("/")[0] != "gen"


def _valid_sealed_manifest(data):
    if not isinstance(data, dict) or set(data) != _MANIFEST_KEYS:
        return False
    ch = data["characterization"]
    if not isinstance(ch, dict) or set(ch) != _CHARACTERIZATION_KEYS:
        return False
    passed = ch["criteria_passed"]
    total = ch["criteria_total"]
    if not (_is_int(passed) and _is_int(total) and 0 <= passed <= total):
        return False
    if ch["overall"] == "pass":
        overall_ok = total >= 1 and passed == total
    else:
        overall_ok = ch["overall"] == "fail"
    return (
        overall_ok
        and data["kind"] == "sealed-provenance"
        and _is_int(data["version"])
        and data["version"] == 1
        and _matches(_COMPONENT_ID_RE, data["component_id"])
        and _valid_owners(data["owners"])
        and _valid_source_path(data["source_path"])
        and _matches(_SOURCE_HASH_RE, data["source_hash"])
        and _matches(_VERIFIER_VERSION_RE, data["verifier_version"])
        and _matches(_WRITTEN_AT_RE, data["written_at"])
    )


def _frontmatter(text):
    lines = text.splitlines()
    fields = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
    return fields


def _source_hash(base):
    # A missing directory yields no files from rglob, so it hashes as no files.
    entries = []
    for path in base.rglob("*"):
        rel = path.relative_to(base)
        if (
            path.is_file()
            and "__pycache__" not in rel.parts[:-1]
            and path.name != _SEALED_MANIFEST_NAME
        ):
            entries.append((rel.as_posix(), path))
    entries.sort(key=lambda e: e[0])
    digest = hashlib.sha256()
    for rel, path in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    """R-PROVCHECK-001..004: hit/miss for a generated component's committed manifest."""
    miss = ProvenanceCheckResult(
        hit=False, verification_report=None, license_scan=None, secret_scan=None
    )
    path = Path(repo_root) / "gen" / _slug(component_id) / ".provenance.json"
    if not path.is_file():
        return miss
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("spec_bundle_hash") != spec_bundle_hash
        or manifest.get("gate_versions") != gate_versions
    ):
        return miss
    report = manifest.get("verification_report")
    criteria = (report or {}).get("criteria") or []
    has_judge = any(c.get("kind") == "llm-judge" for c in criteria)
    if has_judge and not _trust_judge_provenance():
        return miss
    return ProvenanceCheckResult(
        hit=True,
        verification_report=report,
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id, repo_root):
    """R-PROVCHECK-005: the one definition of a generated component's current key."""
    repo_root = Path(repo_root)
    assembler = _load("spec_bundle_assembler", "gen/spec-bundle-assembler", repo_root)
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _read(bundle, "spec_bundle_hash")
    compiler = _load("criterion_compiler", "pipeline/criterion-compiler", repo_root)
    compiler_version = compiler.GATE_VERSION
    author = _load("test_author", "gen/test-author", repo_root)
    author_version = author.GATE_VERSION
    verifier = _load("verifier_orchestrator", "gen/verifier-orchestrator", repo_root)
    verifier_version = verifier.GATE_VERSION
    license_scanner = _load("license_scanner", "gen/license-scanner", repo_root)
    license_version = license_scanner.gate_version(repo_root)
    secret_scanner = _load("secret_scanner", "gen/secret-scanner", repo_root)
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


def current_sealed_key(component_id, repo_root):
    """R-PROVCHECK-007: a sealed component's current key, or None if not sealed."""
    repo_root = Path(repo_root)
    component_md = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not component_md.is_file():
        return None
    fields = _frontmatter(component_md.read_text(encoding="utf-8"))
    if fields.get("sealed") != "true":
        return None
    raw_owners = fields.get("owners")
    if raw_owners is None or not (raw_owners.startswith("[") and raw_owners.endswith("]")):
        raise ValueError(f"{component_id}: missing or malformed 'owners' frontmatter line")
    owners = [o.strip() for o in raw_owners[1:-1].split(",")]
    if not _valid_owners(owners):
        raise ValueError(f"{component_id}: invalid 'owners' frontmatter line")
    source_path = fields.get("source_path")
    if source_path is None or not _valid_source_path(source_path):
        raise ValueError(f"{component_id}: missing or invalid 'source_path' frontmatter line")
    source_hash = _source_hash(repo_root / source_path)
    verifier = _load("verifier_orchestrator", "gen/verifier-orchestrator", repo_root)
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier.GATE_VERSION,
    )


def _sealed_result(reason, sealed=True, manifest=None):
    hit = reason is None
    return {
        "hit": hit,
        "sealed": sealed,
        "reason": reason,
        "verification_report": (
            {"overall": manifest["characterization"]["overall"]} if hit else None
        ),
        "license_scan": None,
        "secret_scan": None,
        "owners": manifest["owners"] if hit else None,
        "source_hash": manifest["source_hash"] if hit else None,
        "written_at": manifest["written_at"] if hit else None,
    }


def check_sealed_provenance(component_id, repo_root):
    """R-PROVCHECK-008: whether a sealed component's manifest is valid and current."""
    repo_root = Path(repo_root)
    key = current_sealed_key(component_id, repo_root)
    if key is None:
        return _sealed_result("not_sealed", sealed=False)
    path = repo_root / key.source_path / _SEALED_MANIFEST_NAME
    if not path.exists():
        return _sealed_result("manifest_missing")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _sealed_result("manifest_invalid")
    if not _valid_sealed_manifest(manifest):
        return _sealed_result("manifest_invalid")
    if (
        manifest["component_id"] != "comp-" + _slug(component_id)
        or manifest["source_path"] != key.source_path
    ):
        return _sealed_result("component_mismatch")
    if manifest["source_hash"] != key.source_hash:
        return _sealed_result("source_changed")
    if manifest["owners"] != key.owners:
        return _sealed_result("owners_changed")
    if manifest["verifier_version"] != key.verifier_version:
        return _sealed_result("verifier_changed")
    if manifest["characterization"]["overall"] != "pass":
        return _sealed_result("characterization_failed")
    return _sealed_result(None, manifest=manifest)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_USAGE = (
    "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
    "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]"
)
_CLI_COMPONENT_RE = re.compile(r"(comp-)?[a-z0-9]+(-[a-z0-9]+)*")
_CLI_HASH_RE = re.compile(r"sha256:[0-9a-f]+")
_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")


def _usage_error(message):
    print(f"error: {message}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv):
    """R-PROVCHECK-006: `hotdocs provenance check ...`; returns the exit code."""
    argv = list(argv)
    if not argv or argv[0] != "check":
        return _usage_error("expected subcommand 'check'")
    values = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 1
    while i < len(argv):
        token = argv[i]
        name, sep, value = token.partition("=")
        if name in _FLAGS:
            if not sep:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif token.startswith("--") or component_id is not None:
            return _usage_error(f"unknown argument: {token}")
        else:
            component_id = token
        i += 1

    if component_id is None:
        return _usage_error("missing <component-id>")
    if _CLI_COMPONENT_RE.fullmatch(component_id) is None:
        return _usage_error(f"invalid component id: {component_id}")
    spec_bundle_hash = values.get("--spec-bundle-hash")
    if spec_bundle_hash is None:
        return _usage_error("missing --spec-bundle-hash")
    if _CLI_HASH_RE.fullmatch(spec_bundle_hash) is None:
        return _usage_error(f"invalid --spec-bundle-hash: {spec_bundle_hash}")
    raw_gate_versions = values.get("--gate-versions")
    if raw_gate_versions is None:
        return _usage_error("missing --gate-versions")
    try:
        gate_versions = json.loads(raw_gate_versions)
    except ValueError:
        return _usage_error("--gate-versions is not valid JSON")
    if not isinstance(gate_versions, dict) or not all(
        isinstance(v, str) for v in gate_versions.values()
    ):
        return _usage_error("--gate-versions must be a JSON object of strings")
    fmt = values["--format"]
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt}")

    result = check_provenance(
        component_id, spec_bundle_hash, gate_versions, Path(values["--repo-root"])
    )
    if fmt == "json":
        print(json.dumps(dict(result), indent=2, sort_keys=True))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
