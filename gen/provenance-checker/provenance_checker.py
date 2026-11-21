"""Provenance checker: decides whether a committed provenance manifest proves
a component was already verified against the exact current spec state."""

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_USAGE = (
    "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
    "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]"
)
_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")

_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
_WRITTEN_AT_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "characterization", "written_at",
}
_CHAR_KEYS = {"overall", "criteria_passed", "criteria_total"}


class ProvenanceCheckResult(dict):
    """A ProvenanceCheckResult: a dict whose keys also read as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


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
    return getattr(obj, name, None)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _tool_root():
    here = Path(__file__).resolve().parent
    for d in (here, *here.parents):
        if d.name == "gen":
            return d.parent
    return here.parent


def _load_file(name, path, search=None):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=search)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


def _load_dependency(repo_root, rel, module):
    directory = repo_root / rel
    if not directory.exists():
        directory = _tool_root() / rel
    flat = directory / f"{module}.py"
    if flat.is_file():
        return _load_file(module, flat)
    package = directory / module
    return _load_file(module, package / "__init__.py", [str(package)])


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _frontmatter(repo_root, slug):
    path = repo_root / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    if not lines or lines[0] != "---":
        return []
    out = []
    for line in lines[1:]:
        if line == "---":
            break
        out.append(line)
    return out


def _field(lines, key):
    return next((line[len(key):].strip() for line in lines if line.startswith(key)), None)


def _bracket_items(value):
    return [item.strip() for item in value.partition("[")[2].partition("]")[0].split(",")]


def _is_sealed(lines):
    return "sealed: true" in lines


def _adapter_path(repo_root, kind):
    rel = Path("gen", f"kind-{kind}", f"kind_{kind}.py")
    for base in (repo_root, _tool_root()):
        if (base / rel).is_file():
            return base / rel
    return None


def _current_assets(repo_root, slug, strict):
    """Return (assets, None), or (None, reason) when strict and a kind fails."""
    lines = _frontmatter(repo_root, slug)
    if _is_sealed(lines):
        return [], None
    entries = [("python", ".")]
    declared = _field(lines, "assets:")
    if declared is not None:
        for item in _bracket_items(declared):
            if item:
                kind, _, path = item.partition(":")
                entries.append((kind, path))
    provisioned = {}
    assets = []
    for kind, path in entries:
        adapter_file = _adapter_path(repo_root, kind)
        if kind not in provisioned:
            versions, lockfile = {}, None
            if adapter_file is None:
                if strict:
                    return None, f"unknown asset kind: {kind}"
            else:
                adapter = _load_file(f"_provenance_checker_adapter_kind_{kind}", adapter_file)
                report = adapter.provision(repo_root)
                if strict and not _get(report, "ok"):
                    return None, _get(report, "reason")
                versions, lockfile = _get(report, "versions"), _get(report, "lockfile_sha256")
            provisioned[kind] = (versions, lockfile)
        definition = repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
        versions, lockfile = provisioned[kind]
        assets.append({
            "kind": kind,
            "path": path,
            "definition_sha256": _sha256_file(definition) if definition.is_file() else None,
            "adapter_sha256": _sha256_file(adapter_file) if adapter_file is not None else None,
            "versions": versions,
            "lockfile_sha256": lockfile,
        })
    return assets, None


def _assets_reason(recorded, current):
    if isinstance(recorded, list) and len(recorded) == len(current) and all(
        isinstance(old, dict)
        and set(old) == set(new)
        and all(old[k] == new[k] for k in ("kind", "path", "definition_sha256", "adapter_sha256"))
        for old, new in zip(recorded, current)
    ):
        return "environment differs"
    return "assets differ"


def _trust_judge():
    return os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "").strip().lower() != "false"


def _miss(reason):
    return ProvenanceCheckResult(
        hit=False, reason=reason, verification_report=None, license_scan=None, secret_scan=None
    )


# ---------------------------------------------------------------- library

def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    path = repo_root / "gen" / slug / ".provenance.json"
    if not path.is_file():
        return _miss("no manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return _miss("spec_bundle_hash differs")
    if manifest.get("gate_versions") != gate_versions:
        return _miss("gate_versions differ")
    current, reason = _current_assets(repo_root, slug, strict=True)
    if current is None:
        return _miss(reason)
    recorded = manifest.get("assets") or []
    if recorded != current:
        return _miss(_assets_reason(recorded, current))
    report = manifest.get("verification_report")
    criteria = (report or {}).get("criteria") or []
    if not _trust_judge() and any(c.get("kind") == "llm-judge" for c in criteria):
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
    assembler = _load_dependency(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    compiler = _load_dependency(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
    compiler_version = compiler.GATE_VERSION
    author = _load_dependency(repo_root, "gen/test-author", "test_author")
    author_version = author.GATE_VERSION
    verifier = _load_dependency(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    verifier_version = verifier.GATE_VERSION
    license_scanner = _load_dependency(repo_root, "gen/license-scanner", "license_scanner")
    license_version = license_scanner.gate_version(repo_root)
    secret_scanner = _load_dependency(repo_root, "gen/secret-scanner", "secret_scanner")
    secret_version = secret_scanner.gate_version(repo_root)
    generator = _load_dependency(repo_root, "gen/generator", "generator")
    generator_version = f"{generator.GATE_VERSION}+{generator.PROMPT_VERSION}"
    assets, _ = _current_assets(repo_root, _slug(component_id), strict=False)
    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_versions={
            "compiler": compiler_version,
            "generated_test": author_version,
            "verifier": verifier_version,
            "license_scanner": license_version,
            "secret_scanner": secret_version,
            "generator": generator_version,
        },
        assets=assets,
    )


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _valid_owners(value):
    return isinstance(value, list) and len(value) > 0 and all(_matches(_OWNER_RE, o) for o in value)


def _valid_source_path(value):
    return _matches(_SOURCE_PATH_RE, value) and value.split("/")[0] != "gen"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _source_hash(base):
    files = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".sealed-provenance.json":
                full = Path(dirpath, name)
                files.append((full.relative_to(base).as_posix(), full))
    digest = hashlib.sha256()
    for rel, full in sorted(files):
        digest.update(rel.encode("utf-8") + b"\0" + full.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    lines = _frontmatter(repo_root, _slug(component_id))
    if not _is_sealed(lines):
        return None
    owners_line = _field(lines, "owners:")
    if owners_line is None:
        raise ValueError("component.md frontmatter has no owners line")
    owners = _bracket_items(owners_line)
    if not _valid_owners(owners):
        raise ValueError(f"invalid owners: {owners_line}")
    source_path = _field(lines, "source_path:")
    if source_path is None:
        raise ValueError("component.md frontmatter has no source_path line")
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid source_path: {source_path}")
    source_hash = _source_hash(repo_root / source_path)
    verifier = _load_dependency(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier.GATE_VERSION,
    )


def _valid_sealed_manifest(m):
    if not isinstance(m, dict) or set(m) != _SEALED_KEYS:
        return False
    c = m["characterization"]
    if not isinstance(c, dict) or set(c) != _CHAR_KEYS:
        return False
    passed, total = c["criteria_passed"], c["criteria_total"]
    if not (_is_int(passed) and _is_int(total) and 0 <= passed <= total):
        return False
    if c["overall"] == "pass":
        if total < 1 or passed != total:
            return False
    elif c["overall"] != "fail":
        return False
    return (
        m["kind"] == "sealed-provenance"
        and _is_int(m["version"])
        and m["version"] == 1
        and _matches(_COMPONENT_ID_RE, m["component_id"])
        and _valid_owners(m["owners"])
        and _valid_source_path(m["source_path"])
        and _matches(_SOURCE_HASH_RE, m["source_hash"])
        and _matches(_VERIFIER_RE, m["verifier_version"])
        and _matches(_WRITTEN_AT_RE, m["written_at"])
    )


def _sealed_result(reason, sealed=True, manifest=None):
    hit = reason is None
    return {
        "hit": hit,
        "sealed": sealed,
        "reason": reason,
        "verification_report": {"overall": manifest["characterization"]["overall"]} if hit else None,
        "license_scan": None,
        "secret_scan": None,
        "owners": manifest["owners"] if hit else None,
        "source_hash": manifest["source_hash"] if hit else None,
        "written_at": manifest["written_at"] if hit else None,
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
    return _sealed_result(None, manifest=manifest)


# ---------------------------------------------------------------- CLI

class _UsageError(Exception):
    pass


def _parse(argv):
    if not argv or argv[0] != "check":
        raise _UsageError("expected subcommand 'check'")
    values = {"--repo-root": ".", "--format": "text"}
    positionals = []
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _FLAGS:
                raise _UsageError(f"unknown argument: {token}")
            if not eq:
                i += 1
                if i == len(argv):
                    raise _UsageError(f"{name} requires a value")
                value = argv[i]
            values[name] = value
        else:
            positionals.append(token)
        i += 1
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument: {positionals[1]}")
    if not positionals:
        raise _UsageError("missing <component-id>")
    component_id = positionals[0]
    if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", component_id) is None:
        raise _UsageError(f"invalid component id: {component_id}")
    if "--spec-bundle-hash" not in values:
        raise _UsageError("missing --spec-bundle-hash")
    if re.fullmatch(r"sha256:[0-9a-f]+", values["--spec-bundle-hash"]) is None:
        raise _UsageError("invalid --spec-bundle-hash")
    if "--gate-versions" not in values:
        raise _UsageError("missing --gate-versions")
    try:
        gate_versions = json.loads(values["--gate-versions"])
    except ValueError:
        raise _UsageError("--gate-versions is not valid JSON")
    if not isinstance(gate_versions, dict) or not all(isinstance(v, str) for v in gate_versions.values()):
        raise _UsageError("--gate-versions must be a JSON object of strings")
    if values["--format"] not in ("json", "text"):
        raise _UsageError(f"invalid --format: {values['--format']}")
    return component_id, values["--spec-bundle-hash"], gate_versions, values["--repo-root"], values["--format"]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        component_id, spec_bundle_hash, gate_versions, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    result = check_provenance(component_id, spec_bundle_hash, gate_versions, Path(repo_root))
    if fmt == "json":
        print(json.dumps(result))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
