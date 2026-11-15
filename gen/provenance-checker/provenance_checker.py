"""Provenance checker: decides whether committed provenance proves a component
was already verified against the exact current spec state (R-PROVCHECK-001..008)."""

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_CLI_COMPONENT_RE = r"(comp-)?[a-z0-9]+(-[a-z0-9]+)*"
_HASH_ARG_RE = r"sha256:[0-9a-f]+"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_VERSION_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
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


class ProvenanceCheckResult(dict):
    """A dict that also exposes its fields as attributes."""

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


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load(module_name, rel, repo_root):
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
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


def _trust_judge():
    value = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "")
    return value.strip().lower() != "false"


def _miss():
    return ProvenanceCheckResult(
        hit=False, verification_report=None, license_scan=None, secret_scan=None
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    path = Path(repo_root) / "gen" / _slug(component_id) / ".provenance.json"
    if not path.is_file():
        return _miss()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return _miss()
    if manifest.get("gate_versions") != dict(gate_versions):
        return _miss()
    report = manifest.get("verification_report")
    criteria = (report or {}).get("criteria") or []
    has_judge = any(c.get("kind") == "llm-judge" for c in criteria)
    if has_judge and not _trust_judge():
        return _miss()
    return ProvenanceCheckResult(
        hit=True,
        verification_report=report,
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id, repo_root):
    repo_root = Path(repo_root)
    assembler = _load("spec_bundle_assembler", "gen/spec-bundle-assembler", repo_root)
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    compiler = _load("criterion_compiler", "pipeline/criterion-compiler", repo_root)
    compiler_version = compiler.GATE_VERSION
    author = _load("test_author", "gen/test-author", repo_root)
    author_version = author.GATE_VERSION
    verifier = _load("verifier_orchestrator", "gen/verifier-orchestrator", repo_root)
    verifier_version = verifier.GATE_VERSION
    license_mod = _load("license_scanner", "gen/license-scanner", repo_root)
    license_version = license_mod.gate_version(repo_root)
    secret_mod = _load("secret_scanner", "gen/secret-scanner", repo_root)
    secret_version = secret_mod.gate_version(repo_root)
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


def _match(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _valid_owners(owners):
    return (
        isinstance(owners, list)
        and len(owners) > 0
        and all(_match(_OWNER_RE, o) for o in owners)
    )


def _valid_source_path(source_path):
    return _match(_SOURCE_PATH_RE, source_path) and source_path.split("/")[0] != "gen"


def _is_int(value):
    return type(value) is int


def _valid_manifest(m):
    if not isinstance(m, dict) or set(m) != _MANIFEST_KEYS:
        return False
    ch = m["characterization"]
    if not isinstance(ch, dict) or set(ch) != _CHARACTERIZATION_KEYS:
        return False
    if m["kind"] != "sealed-provenance":
        return False
    if not (_is_int(m["version"]) and m["version"] == 1):
        return False
    if not _match(_COMPONENT_ID_RE, m["component_id"]):
        return False
    if not _valid_owners(m["owners"]):
        return False
    if not _valid_source_path(m["source_path"]):
        return False
    if not _match(_SOURCE_HASH_RE, m["source_hash"]):
        return False
    if not _match(_VERIFIER_VERSION_RE, m["verifier_version"]):
        return False
    overall = ch["overall"]
    passed = ch["criteria_passed"]
    total = ch["criteria_total"]
    if overall not in ("pass", "fail"):
        return False
    if not (_is_int(passed) and _is_int(total)):
        return False
    if not (0 <= passed <= total):
        return False
    if overall == "pass" and not (total >= 1 and passed == total):
        return False
    return _match(_WRITTEN_AT_RE, m["written_at"])


def _frontmatter(text):
    lines = text.splitlines()
    fields = {}
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _parse_owners(value):
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"invalid owners: {value!r}")
    owners = [item.strip() for item in value[1:-1].split(",")]
    if not _valid_owners(owners):
        raise ValueError(f"invalid owners: {value!r}")
    return owners


def _source_hash(source_dir):
    entries = []
    for dirpath, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name == ".sealed-provenance.json":
                continue
            full = Path(dirpath) / name
            entries.append((full.relative_to(source_dir).as_posix(), full))
    entries.sort(key=lambda e: e[0])
    digest = hashlib.sha256()
    for rel, full in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(full.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    component_md = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not component_md.is_file():
        return None
    fields = _frontmatter(component_md.read_text(encoding="utf-8"))
    if fields.get("sealed") != "true":
        return None
    if "owners" not in fields:
        raise ValueError("component.md frontmatter has no owners line")
    owners = _parse_owners(fields["owners"])
    if "source_path" not in fields:
        raise ValueError("component.md frontmatter has no source_path line")
    source_path = fields["source_path"]
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid source_path: {source_path!r}")
    source_hash = _source_hash(repo_root / source_path)
    verifier = _load("verifier_orchestrator", "gen/verifier-orchestrator", repo_root)
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier.GATE_VERSION,
    )


def _sealed_result(reason, sealed=True):
    return {
        "hit": False,
        "sealed": sealed,
        "reason": reason,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }


def check_sealed_provenance(component_id, repo_root):
    repo_root = Path(repo_root)
    key = current_sealed_key(component_id, repo_root)
    if key is None:
        return _sealed_result("not_sealed", sealed=False)
    path = repo_root / key.source_path / ".sealed-provenance.json"
    if not path.exists():
        return _sealed_result("manifest_missing")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _sealed_result("manifest_invalid")
    if not _valid_manifest(manifest):
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
    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": manifest["characterization"]["overall"]},
        "license_scan": None,
        "secret_scan": None,
        "owners": manifest["owners"],
        "source_hash": manifest["source_hash"],
        "written_at": manifest["written_at"],
    }


def _usage(message):
    print(f"usage error: {message}", file=sys.stderr)
    print(
        "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
        "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]",
        file=sys.stderr,
    )
    return 2


def main(argv):
    argv = list(argv)
    if not argv or argv[0] != "check":
        return _usage("expected subcommand 'check'")
    values = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, sep, value = token.partition("=")
            if name not in _FLAGS:
                return _usage(f"unknown argument {token!r}")
            if not sep:
                if i + 1 >= len(argv):
                    return _usage(f"{name} requires a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif component_id is None:
            component_id = token
        else:
            return _usage(f"unknown argument {token!r}")
        i += 1
    if component_id is None:
        return _usage("missing <component-id>")
    if re.fullmatch(_CLI_COMPONENT_RE, component_id) is None:
        return _usage(f"invalid component id {component_id!r}")
    if "--spec-bundle-hash" not in values:
        return _usage("missing --spec-bundle-hash")
    spec_bundle_hash = values["--spec-bundle-hash"]
    if re.fullmatch(_HASH_ARG_RE, spec_bundle_hash) is None:
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
    fmt = values["--format"]
    if fmt not in ("json", "text"):
        return _usage(f"invalid --format {fmt!r}")
    result = check_provenance(
        component_id, spec_bundle_hash, gate_versions, Path(values["--repo-root"])
    )
    if fmt == "json":
        print(json.dumps(result))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
