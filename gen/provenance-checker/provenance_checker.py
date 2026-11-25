"""Provenance checker: decides whether a committed provenance manifest still proves
a component verified against the current spec state (R-PROVCHECK-001..010)."""

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

_CLI_COMPONENT_RE = r"(comp-)?[a-z0-9]+(-[a-z0-9]+)*"
_CLI_HASH_RE = r"sha256:[0-9a-f]+"

_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_VERSION_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
_WRITTEN_AT_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"

_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "characterization", "written_at",
}
_CHARACTERIZATION_KEYS = {"overall", "criteria_passed", "criteria_total"}


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


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _slug(component_id):
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _tool_root():
    here = Path(__file__).resolve()
    return next(d.parent for d in here.parents if d.name == "gen")


def _resolve_dir(repo_root, rel):
    candidate = Path(repo_root) / rel
    if candidate.exists():
        return candidate
    return _tool_root() / rel


def _load_dependency(repo_root, rel_dir, module):
    directory = _resolve_dir(repo_root, rel_dir)
    file = directory / f"{module}.py"
    if file.is_file():
        spec = importlib.util.spec_from_file_location(module, file)
    else:
        file = directory / module / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            module, file, submodule_search_locations=[str(file.parent)]
        )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _sha256_file(path):
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def _frontmatter_lines(repo_root, component_id):
    path = Path(repo_root) / "specs" / "components" / _slug(component_id) / "component.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def _frontmatter_value(lines, key):
    prefix = key + ":"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _is_sealed(lines):
    return any(line.strip() == "sealed: true" for line in lines)


def _declared_assets(lines):
    raw = _frontmatter_value(lines, "assets")
    if raw is None:
        return []
    inner = raw.removeprefix("[").removesuffix("]")
    declared = []
    for item in inner.split(","):
        item = item.strip()
        if item:
            kind, _, path = item.partition(":")
            declared.append((kind.strip(), path.strip()))
    return declared


def _adapter_path(repo_root, kind):
    rel = Path("gen") / f"kind-{kind}" / f"kind_{kind.replace('-', '_')}.py"
    candidate = Path(repo_root) / rel
    if candidate.exists():
        return candidate
    candidate = _tool_root() / rel
    if candidate.exists():
        return candidate
    return None


def _load_adapter(path, kind):
    name = f"_provenance_checker_kind_{kind.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def _asset_entries(component_id, repo_root):
    """Yield (entry, ok, reason) per asset of the current value, in order,
    provisioning each distinct kind lazily and once (R-PROVCHECK-009)."""
    repo_root = Path(repo_root)
    lines = _frontmatter_lines(repo_root, component_id)
    if _is_sealed(lines):
        return
    provisioned = {}
    for kind, path in [("python", ".")] + _declared_assets(lines):
        definition = repo_root / "specs" / "architecture" / f"asset-kind-{kind}.md"
        adapter = _adapter_path(repo_root, kind)
        if adapter is None:
            versions, lockfile, ok, reason = {}, None, False, f"unknown asset kind: {kind}"
            adapter_sha = None
        else:
            if kind not in provisioned:
                provisioned[kind] = _load_adapter(adapter, kind).provision(repo_root)
            result = provisioned[kind]
            versions = _field(result, "versions")
            lockfile = _field(result, "lockfile_sha256")
            ok = bool(_field(result, "ok"))
            reason = _field(result, "reason")
            adapter_sha = _sha256_file(adapter)
        entry = {
            "kind": kind,
            "path": path,
            "definition_sha256": _sha256_file(definition),
            "adapter_sha256": adapter_sha,
            "versions": versions,
            "lockfile_sha256": lockfile,
        }
        yield entry, ok, reason


def _only_environment_differs(manifest_assets, current):
    if not isinstance(manifest_assets, list) or len(manifest_assets) != len(current):
        return False
    for theirs, ours in zip(manifest_assets, current):
        if not isinstance(theirs, dict) or set(theirs) != set(ours):
            return False
        for key in ("kind", "path", "definition_sha256", "adapter_sha256"):
            if theirs[key] != ours[key]:
                return False
    return True


def _trust_judge():
    value = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "")
    return value.strip().lower() != "false"


def _miss(reason):
    return ProvenanceCheckResult(
        hit=False, reason=reason, verification_report=None, license_scan=None, secret_scan=None
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

    current = []
    for entry, ok, reason in _asset_entries(component_id, repo_root):
        if not ok:
            return _miss(reason)
        current.append(entry)
    manifest_assets = manifest.get("assets")
    if manifest_assets is None:
        manifest_assets = []
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
    assembler = _load_dependency(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _field(bundle, "spec_bundle_hash")

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

    gate_versions = {
        "compiler": compiler_version,
        "generated_test": author_version,
        "verifier": verifier_version,
        "license_scanner": license_version,
        "secret_scanner": secret_version,
        "generator": generator_version,
    }
    assets = [entry for entry, _ok, _reason in _asset_entries(component_id, repo_root)]
    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions, assets=assets
    )


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _is_int(value):
    return type(value) is int


def _valid_owners(value):
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(_matches(_OWNER_RE, owner) for owner in value)
    )


def _valid_source_path(value):
    return _matches(_SOURCE_PATH_RE, value) and value.split("/")[0] != "gen"


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


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    lines = _frontmatter_lines(repo_root, component_id)
    if not _is_sealed(lines):
        return None
    match = re.fullmatch(r"\[(.*)\]", _frontmatter_value(lines, "owners") or "")
    owners = [o.strip() for o in match.group(1).split(",")] if match else None
    if not _valid_owners(owners):
        raise ValueError("component.md frontmatter owners is missing or invalid")
    source_path = _frontmatter_value(lines, "source_path")
    if not _valid_source_path(source_path):
        raise ValueError("component.md frontmatter source_path is missing or invalid")
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
    if not isinstance(c, dict) or set(c) != _CHARACTERIZATION_KEYS:
        return False
    passed, total = c["criteria_passed"], c["criteria_total"]
    if not (_is_int(passed) and _is_int(total) and 0 <= passed <= total):
        return False
    return (
        m["kind"] == "sealed-provenance"
        and _is_int(m["version"])
        and m["version"] == 1
        and _matches(_COMPONENT_ID_RE, m["component_id"])
        and _valid_owners(m["owners"])
        and _valid_source_path(m["source_path"])
        and _matches(_SOURCE_HASH_RE, m["source_hash"])
        and _matches(_VERIFIER_VERSION_RE, m["verifier_version"])
        and _matches(_WRITTEN_AT_RE, m["written_at"])
        and c["overall"] in ("pass", "fail")
        and (c["overall"] != "pass" or (total >= 1 and passed == total))
    )


def _sealed_miss(reason, sealed=True):
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
        return _sealed_miss("not_sealed", sealed=False)
    path = repo_root / key.source_path / ".sealed-provenance.json"
    if not path.exists():
        return _sealed_miss("manifest_missing")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = None
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
        "owners": manifest["owners"],
        "source_hash": manifest["source_hash"],
        "written_at": manifest["written_at"],
    }


# ---------------------------------------------------------------- CLI


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv:
        return _usage_error("missing subcommand")
    if argv[0] != "check":
        return _usage_error(f"unknown subcommand: {argv[0]}")

    flags = {
        "--spec-bundle-hash": None,
        "--gate-versions": None,
        "--repo-root": None,
        "--format": None,
    }
    positional = []
    i = 1
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in flags:
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = argv[i]
            flags[name] = value
        elif token.startswith("-") or positional:
            return _usage_error(f"unknown argument: {token}")
        else:
            positional.append(token)
        i += 1

    if not positional:
        return _usage_error("missing <component-id>")
    component_id = positional[0]
    if not re.fullmatch(_CLI_COMPONENT_RE, component_id):
        return _usage_error(f"invalid component id: {component_id}")

    spec_bundle_hash = flags["--spec-bundle-hash"]
    if spec_bundle_hash is None:
        return _usage_error("missing --spec-bundle-hash")
    if not re.fullmatch(_CLI_HASH_RE, spec_bundle_hash):
        return _usage_error(f"invalid --spec-bundle-hash: {spec_bundle_hash}")

    raw_gate_versions = flags["--gate-versions"]
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

    fmt = "text" if flags["--format"] is None else flags["--format"]
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt}")

    repo_root = Path.cwd() if flags["--repo-root"] is None else Path(flags["--repo-root"])

    result = check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    if fmt == "json":
        print(json.dumps(result))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {component_id}")
    return 0
