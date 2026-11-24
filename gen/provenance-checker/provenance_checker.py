"""Provenance checker: decides whether a committed provenance manifest proves
a component was already verified against the current spec state."""

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

USAGE = (
    "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
    "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]"
)

_SLUG_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
_WRITTEN_AT_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"

_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}
_CHARACTERIZATION_KEYS = {"overall", "criteria_passed", "criteria_total"}
_ASSET_FIXED_KEYS = ("kind", "path", "definition_sha256", "adapter_sha256")


class ProvenanceCheckResult(dict):
    """A dict that also exposes its keys as attributes."""

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


# ---------------------------------------------------------------- helpers

def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name, file, search=None):
    spec = importlib.util.spec_from_file_location(
        name, str(file), submodule_search_locations=search
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _load_dep(repo_root, rel, module):
    directory = repo_root / rel
    if not directory.exists():
        directory = _tool_root() / rel
    file = directory / f"{module}.py"
    if file.is_file():
        return _load_module(module, file)
    package = directory / module
    return _load_module(module, package / "__init__.py", [str(package)])


def _frontmatter(repo_root, component_id):
    path = repo_root / "specs" / "components" / _slug(component_id) / "component.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    result = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        result.append(line)
    return result


def _is_sealed(lines):
    return any(line.strip() == "sealed: true" for line in lines)


def _declared_assets(lines):
    for line in lines:
        if line.startswith("assets:"):
            inner = line.partition("[")[2].partition("]")[0]
            items = [item.strip() for item in inner.split(",")]
            return [
                (item.partition(":")[0], item.partition(":")[2])
                for item in items
                if item
            ]
    return []


def _adapter_file(repo_root, kind):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    for base in (repo_root, _tool_root()):
        if (base / rel).is_file():
            return base / rel
    return None


def _assets(component_id, repo_root, check):
    """Return (value, miss_reason). In check mode, stop at the first kind
    with no adapter or whose provision reports ok false."""
    lines = _frontmatter(repo_root, component_id)
    if _is_sealed(lines):
        return [], None
    declarations = [("python", ".")] + _declared_assets(lines)
    provisioned = {}
    value = []
    for kind, path in declarations:
        if kind not in provisioned:
            adapter = _adapter_file(repo_root, kind)
            if adapter is None:
                if check:
                    return None, f"unknown asset kind: {kind}"
                provisioned[kind] = (None, {}, None)
            else:
                module = _load_module(
                    f"_provenance_checker_kind_{kind.replace('-', '_')}", adapter
                )
                report = module.provision(repo_root)
                if check and not _get(report, "ok"):
                    return None, _get(report, "reason")
                provisioned[kind] = (
                    _sha256_file(adapter),
                    _get(report, "versions"),
                    _get(report, "lockfile_sha256"),
                )
        adapter_sha, versions, lockfile = provisioned[kind]
        definition = repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
        value.append({
            "kind": kind,
            "path": path,
            "definition_sha256": _sha256_file(definition) if definition.is_file() else None,
            "adapter_sha256": adapter_sha,
            "versions": versions,
            "lockfile_sha256": lockfile,
        })
    return value, None


def _environment_only(manifest_assets, current):
    return (
        isinstance(manifest_assets, list)
        and len(manifest_assets) == len(current)
        and all(
            isinstance(entry, dict)
            and set(entry) == set(cur)
            and all(entry[k] == cur[k] for k in _ASSET_FIXED_KEYS)
            for entry, cur in zip(manifest_assets, current)
        )
    )


def _trust_judge():
    value = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "")
    return value.strip().lower() != "false"


def _miss(reason):
    return ProvenanceCheckResult(
        hit=False, reason=reason, verification_report=None,
        license_scan=None, secret_scan=None,
    )


# ---------------------------------------------------------------- library

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
    current, reason = _assets(component_id, repo_root, check=True)
    if reason is not None:
        return _miss(reason)
    manifest_assets = manifest.get("assets")
    if manifest_assets is None:
        manifest_assets = []
    if manifest_assets != current:
        if _environment_only(manifest_assets, current):
            return _miss("environment differs")
        return _miss("assets differ")
    report = manifest.get("verification_report")
    criteria = (report or {}).get("criteria") or []
    has_judge = any(c.get("kind") == "llm-judge" for c in criteria)
    if has_judge and not _trust_judge():
        return _miss("llm-judge results not trusted")
    return ProvenanceCheckResult(
        hit=True,
        reason=None,
        verification_report=report,
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id, repo_root):
    repo_root = Path(repo_root)
    assembler = _load_dep(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    compiler = _get(
        _load_dep(repo_root, "pipeline/criterion-compiler", "criterion_compiler"),
        "GATE_VERSION",
    )
    generated_test = _get(_load_dep(repo_root, "gen/test-author", "test_author"), "GATE_VERSION")
    verifier = _get(
        _load_dep(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator"),
        "GATE_VERSION",
    )
    license_scanner = _load_dep(repo_root, "gen/license-scanner", "license_scanner")
    license_version = license_scanner.gate_version(repo_root)
    secret_scanner = _load_dep(repo_root, "gen/secret-scanner", "secret_scanner")
    secret_version = secret_scanner.gate_version(repo_root)
    generator = _load_dep(repo_root, "gen/generator", "generator")
    generator_version = f"{_get(generator, 'GATE_VERSION')}+{_get(generator, 'PROMPT_VERSION')}"
    assets, _ = _assets(component_id, repo_root, check=False)
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


def _match(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_owners(owners):
    return (
        isinstance(owners, list)
        and len(owners) > 0
        and all(_match(_OWNER_RE, owner) for owner in owners)
    )


def _valid_source_path(source_path):
    return _match(_SOURCE_PATH_RE, source_path) and source_path.split("/")[0] != "gen"


def _frontmatter_value(lines, pattern):
    for line in lines:
        found = re.fullmatch(pattern, line.strip())
        if found:
            return found.group(1)
    return None


def _source_hash(base):
    entries = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".sealed-provenance.json":
                full = Path(dirpath) / name
                entries.append((full.relative_to(base).as_posix(), full))
    entries.sort(key=lambda entry: entry[0])
    digest = hashlib.sha256()
    for rel, full in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(full.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    lines = _frontmatter(repo_root, component_id)
    if not _is_sealed(lines):
        return None
    owners_text = _frontmatter_value(lines, r"owners:\s*\[(.*)\]")
    if owners_text is None:
        raise ValueError("component.md frontmatter has no owners: [..] line")
    owners = [owner.strip() for owner in owners_text.split(",")]
    if not _valid_owners(owners):
        raise ValueError(f"invalid owners: {owners_text!r}")
    source_path = _frontmatter_value(lines, r"source_path:\s*(.*?)")
    if source_path is None:
        raise ValueError("component.md frontmatter has no source_path line")
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid source_path: {source_path!r}")
    source_hash = _source_hash(repo_root / source_path)
    verifier = _load_dep(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=_get(verifier, "GATE_VERSION"),
    )


def _valid_sealed_manifest(data):
    if not isinstance(data, dict) or set(data) != _SEALED_KEYS:
        return False
    char = data["characterization"]
    if not isinstance(char, dict) or set(char) != _CHARACTERIZATION_KEYS:
        return False
    passed = char["criteria_passed"]
    total = char["criteria_total"]
    overall = char["overall"]
    return (
        data["kind"] == "sealed-provenance"
        and _is_int(data["version"]) and data["version"] == 1
        and _match(_COMPONENT_ID_RE, data["component_id"])
        and _valid_owners(data["owners"])
        and _valid_source_path(data["source_path"])
        and _match(_SOURCE_HASH_RE, data["source_hash"])
        and _match(_VERIFIER_RE, data["verifier_version"])
        and overall in ("pass", "fail")
        and _is_int(passed) and _is_int(total)
        and 0 <= passed <= total
        and (overall != "pass" or (total >= 1 and passed == total))
        and _match(_WRITTEN_AT_RE, data["written_at"])
    )


def _sealed_result(reason, sealed=True, data=None):
    hit = reason is None
    return {
        "hit": hit,
        "sealed": sealed,
        "reason": reason,
        "verification_report": {"overall": data["characterization"]["overall"]} if hit else None,
        "license_scan": None,
        "secret_scan": None,
        "owners": data["owners"] if hit else None,
        "source_hash": data["source_hash"] if hit else None,
        "written_at": data["written_at"] if hit else None,
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
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _sealed_result("manifest_invalid")
    if not _valid_sealed_manifest(data):
        return _sealed_result("manifest_invalid")
    if (data["component_id"] != "comp-" + _slug(component_id)
            or data["source_path"] != key.source_path):
        return _sealed_result("component_mismatch")
    if data["source_hash"] != key.source_hash:
        return _sealed_result("source_changed")
    if data["owners"] != key.owners:
        return _sealed_result("owners_changed")
    if data["verifier_version"] != key.verifier_version:
        return _sealed_result("verifier_changed")
    if data["characterization"]["overall"] != "pass":
        return _sealed_result("characterization_failed")
    return _sealed_result(None, data=data)


# ---------------------------------------------------------------- CLI

def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv or argv[0] != "check":
        return _usage("expected subcommand 'check'")
    flags = {
        "--spec-bundle-hash": None,
        "--gate-versions": None,
        "--repo-root": ".",
        "--format": "text",
    }
    positional = []
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in flags:
                return _usage(f"unknown argument: {token}")
            if not eq:
                if i + 1 >= len(argv):
                    return _usage(f"{name} requires a value")
                i += 1
                value = argv[i]
            flags[name] = value
        else:
            positional.append(token)
        i += 1
    if len(positional) > 1:
        return _usage(f"unknown argument: {positional[1]}")
    if not positional:
        return _usage("missing <component-id>")
    component_id = positional[0]
    if not re.fullmatch(_SLUG_RE, component_id):
        return _usage(f"invalid component id: {component_id}")
    spec_bundle_hash = flags["--spec-bundle-hash"]
    if spec_bundle_hash is None:
        return _usage("missing --spec-bundle-hash")
    if not re.fullmatch(r"sha256:[0-9a-f]+", spec_bundle_hash):
        return _usage(f"invalid --spec-bundle-hash: {spec_bundle_hash}")
    gate_text = flags["--gate-versions"]
    if gate_text is None:
        return _usage("missing --gate-versions")
    try:
        gate_versions = json.loads(gate_text)
    except ValueError:
        return _usage("--gate-versions is not valid JSON")
    if not isinstance(gate_versions, dict) or not all(
        isinstance(v, str) for v in gate_versions.values()
    ):
        return _usage("--gate-versions must be a JSON object of strings")
    output_format = flags["--format"]
    if output_format not in ("json", "text"):
        return _usage(f"invalid --format: {output_format}")
    result = check_provenance(
        component_id, spec_bundle_hash, gate_versions, Path(flags["--repo-root"])
    )
    if output_format == "json":
        print(json.dumps(dict(result)))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
