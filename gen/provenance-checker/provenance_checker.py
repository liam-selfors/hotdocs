"""Provenance checker: decides whether a committed provenance manifest still
proves a component verified against the current spec state (R-PROVCHECK-*)."""

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_HASH_ARG_RE = re.compile(r"sha256:[0-9a-f]+")
_COMPONENT_ID_RE = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SOURCE_PATH_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?")
_SOURCE_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VERIFIER_RE = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")
_WRITTEN_AT_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "characterization", "written_at",
}
_CHARACTERIZATION_KEYS = {"overall", "criteria_passed", "criteria_total"}
_IDENTITY_KEYS = ("kind", "path", "definition_sha256", "adapter_sha256")

_USAGE = (
    "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
    "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]"
)
_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")


class ProvenanceCheckResult(dict):
    """The ProvenanceCheckResult, readable as a dict or by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict
    assets: list


@dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


# --------------------------------------------------------------------------
# helpers


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    for parent in Path(os.path.abspath(__file__)).parents:
        if parent.name == "gen":
            return parent.parent


def _load_module(name, path, package_dir=None):
    if package_dir is None:
        spec = importlib.util.spec_from_file_location(name, str(path))
    else:
        spec = importlib.util.spec_from_file_location(
            name, str(path), submodule_search_locations=[str(package_dir)]
        )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _load_dependency(slug, rel_dir, repo_root):
    module_name = slug.replace("-", "_")
    directory = repo_root / rel_dir
    if not directory.is_dir():
        directory = _tool_root() / rel_dir
    module_file = directory / f"{module_name}.py"
    if module_file.is_file():
        return _load_module(module_name, module_file)
    package_dir = directory / module_name
    return _load_module(module_name, package_dir / "__init__.py", package_dir)


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _frontmatter(repo_root, slug):
    path = repo_root / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines[:1] != ["---"]:
        return []
    rest = lines[1:]
    return rest[: rest.index("---")] if "---" in rest else rest


def _is_sealed(lines):
    return any(line.strip() == "sealed: true" for line in lines)


def _field(lines, name):
    for line in lines:
        if line.startswith(f"{name}:"):
            return line[len(name) + 1:].strip()
    return ""


def _declared_assets(lines):
    for line in lines:
        if line.startswith("assets:"):
            inner = line.partition("[")[2].partition("]")[0]
            items = [item.strip() for item in inner.split(",") if item.strip()]
            return [tuple(item.split(":", 1)) for item in items]
    return []


def _adapter_file(repo_root, kind):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    for root in (repo_root, _tool_root()):
        if (root / rel).is_file():
            return root / rel
    return None


def _current_assets(component_id, repo_root, strict):
    """Return (assets value, miss reason) per R-PROVCHECK-009."""
    lines = _frontmatter(repo_root, _slug(component_id))
    if _is_sealed(lines):
        return [], None
    entries = [("python", ".")] + _declared_assets(lines)
    per_kind = {}
    value = []
    for kind, path in entries:
        if kind not in per_kind:
            definition = repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
            definition_sha = _sha256_file(definition) if definition.is_file() else None
            adapter_file = _adapter_file(repo_root, kind)
            if adapter_file is None:
                if strict:
                    return None, f"unknown asset kind: {kind}"
                per_kind[kind] = (definition_sha, None, {}, None)
            else:
                adapter = _load_module(
                    f"_provenance_checker_adapter_kind_{kind.replace('-', '_')}", adapter_file
                )
                result = adapter.provision(repo_root)
                if strict and not _get(result, "ok"):
                    return None, _get(result, "reason")
                per_kind[kind] = (
                    definition_sha,
                    _sha256_file(adapter_file),
                    _get(result, "versions"),
                    _get(result, "lockfile_sha256"),
                )
        definition_sha, adapter_sha, versions, lockfile = per_kind[kind]
        value.append({
            "kind": kind,
            "path": path,
            "definition_sha256": definition_sha,
            "adapter_sha256": adapter_sha,
            "versions": versions,
            "lockfile_sha256": lockfile,
        })
    return value, None


def _only_environment_differs(manifest_assets, current):
    return (
        isinstance(manifest_assets, list)
        and len(manifest_assets) == len(current)
        and all(
            isinstance(m, dict)
            and set(m) == set(c)
            and all(m[k] == c[k] for k in _IDENTITY_KEYS)
            for m, c in zip(manifest_assets, current)
        )
    )


def _miss(reason):
    return ProvenanceCheckResult(
        hit=False, reason=reason, verification_report=None, license_scan=None, secret_scan=None
    )


def _trust_judge():
    return os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "").strip().lower() != "false"


# --------------------------------------------------------------------------
# generated components


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    repo_root = Path(repo_root)
    path = repo_root / "gen" / _slug(component_id) / ".provenance.json"
    if not path.is_file():
        return _miss("no manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return _miss("spec_bundle_hash differs")
    if manifest.get("gate_versions") != gate_versions:
        return _miss("gate_versions differ")
    current, reason = _current_assets(component_id, repo_root, strict=True)
    if reason is not None:
        return _miss(reason)
    manifest_assets = manifest.get("assets") or []
    if manifest_assets != current:
        if _only_environment_differs(manifest_assets, current):
            return _miss("environment differs")
        return _miss("assets differ")
    report = manifest.get("verification_report") or {}
    criteria = report.get("criteria") or []
    if any(c.get("kind") == "llm-judge" for c in criteria) and not _trust_judge():
        return _miss("llm-judge results not trusted")
    return ProvenanceCheckResult(
        hit=True,
        reason=None,
        verification_report=manifest.get("verification_report"),
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id, repo_root):
    repo_root = Path(repo_root)
    assembler = _load_dependency(
        "spec-bundle-assembler", Path("gen") / "spec-bundle-assembler", repo_root
    )
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    compiler = _load_dependency(
        "criterion-compiler", Path("pipeline") / "criterion-compiler", repo_root
    ).GATE_VERSION
    generated_test = _load_dependency(
        "test-author", Path("gen") / "test-author", repo_root
    ).GATE_VERSION
    verifier = _load_dependency(
        "verifier-orchestrator", Path("gen") / "verifier-orchestrator", repo_root
    ).GATE_VERSION
    license_version = _load_dependency(
        "license-scanner", Path("gen") / "license-scanner", repo_root
    ).gate_version(repo_root)
    secret_version = _load_dependency(
        "secret-scanner", Path("gen") / "secret-scanner", repo_root
    ).gate_version(repo_root)
    generator = _load_dependency("generator", Path("gen") / "generator", repo_root)
    generator_version = f"{generator.GATE_VERSION}+{generator.PROMPT_VERSION}"
    assets, _ = _current_assets(component_id, repo_root, strict=False)
    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_versions={
            "compiler": compiler,
            "generated_test": generated_test,
            "verifier": verifier,
            "license_scanner": license_version,
            "secret_scanner": secret_version,
            "generator": generator_version,
        },
        assets=assets,
    )


# --------------------------------------------------------------------------
# sealed components


def _parse_owners(value):
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"invalid owners: {value!r}")
    owners = [item.strip() for item in value[1:-1].split(",")]
    if not all(_OWNER_RE.fullmatch(owner) for owner in owners):
        raise ValueError(f"invalid owners: {value!r}")
    return owners


def _valid_source_path(value):
    return (
        isinstance(value, str)
        and _SOURCE_PATH_RE.fullmatch(value) is not None
        and value.split("/")[0] != "gen"
    )


def _source_hash(root):
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".sealed-provenance.json":
                full = Path(dirpath) / name
                files[full.relative_to(root).as_posix()] = full
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode("utf-8") + b"\0" + files[rel].read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    lines = _frontmatter(repo_root, _slug(component_id))
    if not _is_sealed(lines):
        return None
    owners = _parse_owners(_field(lines, "owners"))
    source_path = _field(lines, "source_path")
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid source_path: {source_path!r}")
    source_hash = _source_hash(repo_root / source_path)
    verifier_version = _load_dependency(
        "verifier-orchestrator", Path("gen") / "verifier-orchestrator", repo_root
    ).GATE_VERSION
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier_version,
    )


def _match(regex, value):
    return isinstance(value, str) and regex.fullmatch(value) is not None


def _is_count(value):
    return type(value) is int


def _valid_sealed_manifest(m):
    if not isinstance(m, dict) or set(m) != _SEALED_KEYS:
        return False
    c = m["characterization"]
    if not isinstance(c, dict) or set(c) != _CHARACTERIZATION_KEYS:
        return False
    owners = m["owners"]
    passed, total = c["criteria_passed"], c["criteria_total"]
    return (
        m["kind"] == "sealed-provenance"
        and type(m["version"]) is int
        and m["version"] == 1
        and _match(_COMPONENT_ID_RE, m["component_id"])
        and isinstance(owners, list)
        and len(owners) > 0
        and all(_match(_OWNER_RE, o) for o in owners)
        and _valid_source_path(m["source_path"])
        and _match(_SOURCE_HASH_RE, m["source_hash"])
        and _match(_VERIFIER_RE, m["verifier_version"])
        and c["overall"] in ("pass", "fail")
        and _is_count(passed)
        and _is_count(total)
        and 0 <= passed <= total
        and (c["overall"] != "pass" or (total >= 1 and passed == total))
        and _match(_WRITTEN_AT_RE, m["written_at"])
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
    if not _valid_sealed_manifest(manifest):
        return _sealed_result("manifest_invalid")
    if (manifest["component_id"] != "comp-" + _slug(component_id)
            or manifest["source_path"] != key.source_path):
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


# --------------------------------------------------------------------------
# CLI


class _UsageError(Exception):
    pass


def _parse_args(argv):
    if not argv or argv[0] != "check":
        raise _UsageError("expected subcommand 'check'")
    values = {"--repo-root": ".", "--format": "text"}
    positional = []
    i = 1
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in _FLAGS:
            if not eq:
                i += 1
                if i == len(argv):
                    raise _UsageError(f"{name} needs a value")
                value = argv[i]
            values[name] = value
        elif token.startswith("-") or positional:
            raise _UsageError(f"unknown argument: {token}")
        else:
            positional.append(token)
        i += 1
    if not positional:
        raise _UsageError("missing <component-id>")
    component_id = positional[0]
    if not _SLUG_RE.fullmatch(component_id):
        raise _UsageError(f"invalid component id: {component_id}")
    if "--spec-bundle-hash" not in values:
        raise _UsageError("missing --spec-bundle-hash")
    if not _HASH_ARG_RE.fullmatch(values["--spec-bundle-hash"]):
        raise _UsageError("invalid --spec-bundle-hash")
    if "--gate-versions" not in values:
        raise _UsageError("missing --gate-versions")
    try:
        gate_versions = json.loads(values["--gate-versions"])
    except ValueError:
        gate_versions = None
    if not isinstance(gate_versions, dict) or not all(
        isinstance(v, str) for v in gate_versions.values()
    ):
        raise _UsageError("--gate-versions must be a JSON object of strings")
    if values["--format"] not in ("json", "text"):
        raise _UsageError(f"invalid --format: {values['--format']}")
    return component_id, values["--spec-bundle-hash"], gate_versions, values


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        component_id, spec_bundle_hash, gate_versions, values = _parse_args(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    result = check_provenance(
        component_id, spec_bundle_hash, gate_versions, Path(values["--repo-root"])
    )
    if values["--format"] == "json":
        print(json.dumps(result))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
