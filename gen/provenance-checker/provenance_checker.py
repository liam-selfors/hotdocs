"""Provenance checker: decides whether a committed provenance manifest proves
a component was already verified against the current spec state."""

import contextlib
import hashlib
import importlib.util
import itertools
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = (
    "usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
    "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]"
)

_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")
_COMPONENT_ID_RE = r"(comp-)?[a-z0-9]+(-[a-z0-9]+)*"
_HASH_RE = r"sha256:[0-9a-f]+"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}
_CHAR_KEYS = {"overall", "criteria_passed", "criteria_total"}

_adapter_counter = itertools.count()


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict = field(default_factory=dict)
    assets: list = field(default_factory=list)


@dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


class ProvenanceCheckResult(dict):
    """A dict that also exposes its keys as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


class _UsageError(Exception):
    pass


# --------------------------------------------------------------------------
# helpers


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


@contextlib.contextmanager
def _no_bytecode():
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = saved


def _exec_module(name, path, search=None):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=search
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with _no_bytecode():
        spec.loader.exec_module(module)
    return module


def _load_dep(rel_dir, module, repo_root):
    directory = Path(repo_root) / rel_dir
    if not directory.exists():
        directory = _tool_root() / rel_dir
    path = directory / f"{module}.py"
    search = None
    if not path.is_file():
        path = directory / module / "__init__.py"
        search = [str(path.parent)]
    return _exec_module(module, path, search)


def _file_sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _frontmatter(repo_root, slug):
    path = Path(repo_root) / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip() == "---":
            break
        lines.append(line)
    return lines


def _is_sealed(lines):
    return any(line.strip() == "sealed: true" for line in lines)


def _declared_assets(lines):
    for line in lines:
        if line.startswith("assets:"):
            inner = line[line.index("[") + 1:line.index("]")]
            items = [item.strip() for item in inner.split(",")]
            return [tuple(item.split(":", 1)) for item in items if item]
    return []


def _adapter_path(kind, repo_root):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    for root in (Path(repo_root), _tool_root()):
        if (root / rel).is_file():
            return root / rel
    return None


def _kind_info(kind, repo_root):
    definition = Path(repo_root) / "specs" / "architecture" / f"asset-kind-{kind}.md"
    info = {
        "definition_sha256": _file_sha(definition) if definition.is_file() else None,
        "adapter_sha256": None,
        "provision": None,
    }
    adapter = _adapter_path(kind, repo_root)
    if adapter is not None:
        info["adapter_sha256"] = _file_sha(adapter)
        name = f"_provenance_checker_kind_{kind.replace('-', '_')}_{next(_adapter_counter)}"
        module = _exec_module(name, adapter)
        info["provision"] = module.provision(Path(repo_root))
    return info


def _current_assets(component_id, repo_root, stop):
    """Return (assets, miss_reason). With ``stop``, the first kind with no
    adapter or a failed provision ends the computation with a reason."""
    lines = _frontmatter(repo_root, _slug(component_id))
    if _is_sealed(lines):
        return [], None
    infos = {}
    assets = []
    for kind, path in [("python", ".")] + _declared_assets(lines):
        if kind not in infos:
            infos[kind] = _kind_info(kind, repo_root)
        info = infos[kind]
        prov = info["provision"]
        if stop:
            if prov is None:
                return None, f"unknown asset kind: {kind}"
            if not _get(prov, "ok"):
                return None, _get(prov, "reason")
        assets.append({
            "kind": kind,
            "path": path,
            "definition_sha256": info["definition_sha256"],
            "adapter_sha256": info["adapter_sha256"],
            "versions": {} if prov is None else _get(prov, "versions"),
            "lockfile_sha256": None if prov is None else _get(prov, "lockfile_sha256"),
        })
    return assets, None


def _only_environment_differs(old, current):
    return (
        isinstance(old, list)
        and len(old) == len(current)
        and all(
            isinstance(o, dict)
            and set(o) == set(c)
            and all(o[k] == c[k] for k in ("kind", "path", "definition_sha256", "adapter_sha256"))
            for o, c in zip(old, current)
        )
    )


def _trust_judge():
    return os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "").strip().lower() != "false"


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _valid_owners(owners):
    return (
        isinstance(owners, list)
        and len(owners) > 0
        and all(_matches(_OWNER_RE, o) for o in owners)
    )


def _valid_source_path(source_path):
    return _matches(_SOURCE_PATH_RE, source_path) and source_path.split("/")[0] != "gen"


def _is_int(value):
    return type(value) is int


def _valid_sealed_manifest(doc):
    if not isinstance(doc, dict) or set(doc) != _SEALED_KEYS:
        return False
    char = doc["characterization"]
    if not isinstance(char, dict) or set(char) != _CHAR_KEYS:
        return False
    passed = char["criteria_passed"]
    total = char["criteria_total"]
    if not (_is_int(passed) and _is_int(total) and 0 <= passed <= total):
        return False
    if char["overall"] == "pass":
        counts_ok = total >= 1 and passed == total
    else:
        counts_ok = char["overall"] == "fail"
    return (
        counts_ok
        and doc["kind"] == "sealed-provenance"
        and _is_int(doc["version"])
        and doc["version"] == 1
        and _matches(r"comp-[a-z0-9]+(-[a-z0-9]+)*", doc["component_id"])
        and _valid_owners(doc["owners"])
        and _valid_source_path(doc["source_path"])
        and _matches(r"sha256:[0-9a-f]{64}", doc["source_hash"])
        and _matches(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+", doc["verifier_version"])
        and _matches(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", doc["written_at"])
    )


def _source_hash(base):
    files = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".sealed-provenance.json":
                full = Path(dirpath) / name
                files.append((full.relative_to(base).as_posix(), full))
    digest = hashlib.sha256()
    for rel, full in sorted(files, key=lambda item: item[0]):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(full.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


# --------------------------------------------------------------------------
# library


def _miss(reason):
    return ProvenanceCheckResult(
        hit=False, reason=reason, verification_report=None,
        license_scan=None, secret_scan=None,
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    repo_root = Path(repo_root)
    path = repo_root / "gen" / _slug(component_id) / ".provenance.json"
    if not path.is_file():
        return _miss("no manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return _miss("spec_bundle_hash differs")
    if manifest.get("gate_versions") != dict(gate_versions):
        return _miss("gate_versions differ")
    current, reason = _current_assets(component_id, repo_root, stop=True)
    if reason is not None:
        return _miss(reason)
    old = manifest.get("assets") or []
    if old != current:
        if _only_environment_differs(old, current):
            return _miss("environment differs")
        return _miss("assets differ")
    report = manifest.get("verification_report")
    criteria = _get(report, "criteria") or []
    if not _trust_judge() and any(_get(c, "kind") == "llm-judge" for c in criteria):
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
    with _no_bytecode():
        assembler = _load_dep("gen/spec-bundle-assembler", "spec_bundle_assembler", repo_root)
        bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
        spec_bundle_hash = _get(bundle, "spec_bundle_hash")
        compiler = _load_dep("pipeline/criterion-compiler", "criterion_compiler", repo_root)
        compiler_version = compiler.GATE_VERSION
        author = _load_dep("gen/test-author", "test_author", repo_root)
        author_version = author.GATE_VERSION
        verifier = _load_dep("gen/verifier-orchestrator", "verifier_orchestrator", repo_root)
        verifier_version = verifier.GATE_VERSION
        license_mod = _load_dep("gen/license-scanner", "license_scanner", repo_root)
        license_version = license_mod.gate_version(repo_root)
        secret_mod = _load_dep("gen/secret-scanner", "secret_scanner", repo_root)
        secret_version = secret_mod.gate_version(repo_root)
        generator = _load_dep("gen/generator", "generator", repo_root)
        generator_version = f"{generator.GATE_VERSION}+{generator.PROMPT_VERSION}"
        assets, _ = _current_assets(component_id, repo_root, stop=False)
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


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    lines = _frontmatter(repo_root, _slug(component_id))
    if not _is_sealed(lines):
        return None
    owners = None
    source_path = None
    for line in lines:
        if line.startswith("owners:"):
            m = re.fullmatch(r"\[(.*)\]", line[len("owners:"):].strip())
            if m is None:
                raise ValueError("owners must be a one-line list: owners: [a, b]")
            owners = [item.strip() for item in m.group(1).split(",")]
        elif line.startswith("source_path:"):
            source_path = line[len("source_path:"):].strip()
    if not _valid_owners(owners):
        raise ValueError(f"invalid or missing owners: {owners!r}")
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid or missing source_path: {source_path!r}")
    source_hash = _source_hash(repo_root / source_path)
    with _no_bytecode():
        verifier = _load_dep("gen/verifier-orchestrator", "verifier_orchestrator", repo_root)
        verifier_version = verifier.GATE_VERSION
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier_version,
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
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _sealed_result("manifest_invalid")
    if not _valid_sealed_manifest(doc):
        return _sealed_result("manifest_invalid")
    if doc["component_id"] != "comp-" + _slug(component_id) or doc["source_path"] != key.source_path:
        return _sealed_result("component_mismatch")
    if doc["source_hash"] != key.source_hash:
        return _sealed_result("source_changed")
    if doc["owners"] != key.owners:
        return _sealed_result("owners_changed")
    if doc["verifier_version"] != key.verifier_version:
        return _sealed_result("verifier_changed")
    if doc["characterization"]["overall"] != "pass":
        return _sealed_result("characterization_failed")
    return _sealed_result(None, manifest=doc)


# --------------------------------------------------------------------------
# CLI


def _parse(argv):
    if not argv or argv[0] != "check":
        raise _UsageError("expected subcommand 'check'")
    values = {}
    component_id = None
    i = 1
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in _FLAGS:
            if not eq:
                if i + 1 >= len(argv):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif token.startswith("--") or component_id is not None:
            raise _UsageError(f"unknown argument: {token}")
        else:
            component_id = token
        i += 1
    if component_id is None:
        raise _UsageError("missing <component-id>")
    if not re.fullmatch(_COMPONENT_ID_RE, component_id):
        raise _UsageError(f"invalid component id: {component_id}")
    if "--spec-bundle-hash" not in values:
        raise _UsageError("missing --spec-bundle-hash")
    spec_bundle_hash = values["--spec-bundle-hash"]
    if not re.fullmatch(_HASH_RE, spec_bundle_hash):
        raise _UsageError(f"invalid --spec-bundle-hash: {spec_bundle_hash}")
    if "--gate-versions" not in values:
        raise _UsageError("missing --gate-versions")
    try:
        gate_versions = json.loads(values["--gate-versions"])
    except ValueError:
        raise _UsageError("--gate-versions is not valid JSON") from None
    if not isinstance(gate_versions, dict) or not all(
        isinstance(v, str) for v in gate_versions.values()
    ):
        raise _UsageError("--gate-versions must be a JSON object of strings")
    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")
    repo_root = Path(values.get("--repo-root", os.getcwd()))
    return component_id, spec_bundle_hash, gate_versions, repo_root, fmt


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        component_id, spec_bundle_hash, gate_versions, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    result = check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    if fmt == "json":
        print(json.dumps(dict(result), sort_keys=True))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
