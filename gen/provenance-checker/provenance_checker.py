"""Provenance checker: decides whether a committed provenance manifest
proves a component was already verified against the current spec state."""

from __future__ import annotations

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

_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
_WRITTEN_AT_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}
_CHAR_KEYS = {"overall", "criteria_passed", "criteria_total"}


# ---------------------------------------------------------------- data types

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
    spec_bundle_parts: dict
    gate_versions: dict
    assets: list
    drivers: list


@dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


# ---------------------------------------------------------------- helpers

def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _slug(component_id: str) -> str:
    return component_id.removeprefix("comp-")


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(rel: str, module: str, repo_root: Path):
    directory = Path(repo_root) / rel
    if not directory.is_dir():
        directory = _tool_root() / rel
    path = directory / f"{module}.py"
    if not path.is_file():
        path = directory / module / "__init__.py"
    spec = importlib.util.spec_from_file_location(module, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def _load_gen(slug: str, repo_root: Path):
    return _load(f"gen/{slug}", slug.replace("-", "_"), repo_root)


def _frontmatter(slug: str, repo_root: Path):
    path = Path(repo_root) / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    fm = []
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            fm.append(line.strip())
    return fm


def _is_sealed(slug: str, repo_root: Path) -> bool:
    fm = _frontmatter(slug, repo_root)
    return fm is not None and "sealed: true" in fm


def _fm_value(fm: list, name: str):
    prefix = f"{name}:"
    for line in fm:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    raise ValueError(f"component.md frontmatter has no {name} line")


def _match(pattern: str, value) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _valid_owners(owners) -> bool:
    return (
        isinstance(owners, list)
        and len(owners) > 0
        and all(_match(_OWNER_RE, o) for o in owners)
    )


def _valid_source_path(source_path) -> bool:
    return _match(_SOURCE_PATH_RE, source_path) and source_path.split("/")[0] != "gen"


def _assets_and_drivers(component_id: str, repo_root: Path):
    """Returns (failure_message_or_None, assets, drivers)."""
    if _is_sealed(_slug(component_id), repo_root):
        return None, [], []
    run_environment = _load_gen("run-environment", repo_root)
    env = run_environment.prepare(component_id, repo_root)
    _get(env, "close")()
    if not _get(env, "ok"):
        return _get(env, "failure_message"), None, None
    assets = [dict(a) for a in _get(env, "assets")]
    drivers = [dict(d) for d in _get(env, "drivers")]
    return None, assets, drivers


def _env_only(old, new) -> bool:
    return len(old) == len(new) and all(
        isinstance(o, dict)
        and set(o) == set(n)
        and all(o[k] == n[k] for k in n if k not in ("versions", "lockfile_sha256"))
        for o, n in zip(old, new)
    )


def _environment_reason(component_id: str, repo_root: Path, manifest: dict):
    failure, assets, drivers = _assets_and_drivers(component_id, repo_root)
    if failure is not None:
        return failure
    m_assets = manifest.get("assets") or []
    m_drivers = manifest.get("drivers") or []
    if m_assets == assets and m_drivers == drivers:
        return None
    if _env_only(m_assets, assets) and _env_only(m_drivers, drivers):
        return "environment differs"
    if m_assets != assets:
        return "assets differ"
    return "drivers differ"


def _trust_judge() -> bool:
    return os.environ.get("VAR_TRUST_JUDGE_PROVENANCE", "").strip().lower() != "false"


def _miss(reason: str) -> ProvenanceCheckResult:
    return ProvenanceCheckResult(
        hit=False, reason=reason,
        verification_report=None, license_scan=None, secret_scan=None,
    )


# ---------------------------------------------------------------- library

def current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey:
    repo_root = Path(repo_root)
    assembler = _load_gen("spec-bundle-assembler", repo_root)
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    spec_bundle_parts = dict(_get(bundle, "spec_bundle_parts"))
    compiler = _load("pipeline/criterion-compiler", "criterion_compiler", repo_root)
    compiler_version = _get(compiler, "GATE_VERSION")
    test_author = _load_gen("test-author", repo_root)
    test_version = _get(test_author, "GATE_VERSION")
    verifier = _load_gen("verifier-orchestrator", repo_root)
    verifier_version = _get(verifier, "GATE_VERSION")
    license_scanner = _load_gen("license-scanner", repo_root)
    license_version = license_scanner.gate_version(repo_root)
    secret_scanner = _load_gen("secret-scanner", repo_root)
    secret_version = secret_scanner.gate_version(repo_root)
    generator = _load_gen("generator", repo_root)
    generator_version = f"{_get(generator, 'GATE_VERSION')}+{_get(generator, 'PROMPT_VERSION')}"
    _, assets, drivers = _assets_and_drivers(component_id, repo_root)
    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash,
        spec_bundle_parts=spec_bundle_parts,
        gate_versions={
            "compiler": compiler_version,
            "generated_test": test_version,
            "verifier": verifier_version,
            "license_scanner": license_version,
            "secret_scanner": secret_version,
            "generator": generator_version,
        },
        assets=assets if assets is not None else [],
        drivers=drivers if drivers is not None else [],
    )


def check_provenance(
    component_id: str,
    spec_bundle_hash: str,
    gate_versions: dict,
    repo_root: Path,
    spec_bundle_parts: dict | None = None,
) -> ProvenanceCheckResult:
    repo_root = Path(repo_root)
    path = repo_root / "gen" / _slug(component_id) / ".provenance.json"
    if not path.exists():
        return _miss("no manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    hash_ok = manifest.get("spec_bundle_hash") == spec_bundle_hash
    gates_ok = manifest.get("gate_versions") == gate_versions
    m_parts = manifest.get("spec_bundle_parts")
    parts_test = (
        not hash_ok
        and spec_bundle_parts is not None
        and isinstance(m_parts, dict)
        and m_parts.get("spec") == spec_bundle_parts.get("spec")
        and m_parts.get("dependency_code") != spec_bundle_parts.get("dependency_code")
    )
    if not hash_ok and not (parts_test and gates_ok):
        return _miss("spec_bundle_hash differs")
    if not gates_ok:
        return _miss("gate_versions differ")
    env_reason = _environment_reason(component_id, repo_root, manifest)
    if not hash_ok:
        if env_reason is None:
            return _miss("dependency code differs")
        return _miss("spec_bundle_hash differs")
    if env_reason is not None:
        return _miss(env_reason)
    report = manifest.get("verification_report")
    criteria = (report or {}).get("criteria") or []
    if any(c.get("kind") == "llm-judge" for c in criteria) and not _trust_judge():
        return _miss("llm-judge results not trusted")
    return ProvenanceCheckResult(
        hit=True,
        reason=None,
        verification_report=report,
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_sealed_key(component_id: str, repo_root: Path) -> SealedKey | None:
    repo_root = Path(repo_root)
    fm = _frontmatter(_slug(component_id), repo_root)
    if fm is None or "sealed: true" not in fm:
        return None
    owners_text = _fm_value(fm, "owners")
    bracketed = re.fullmatch(r"\[(.*)\]", owners_text)
    if bracketed is None:
        raise ValueError(f"invalid owners: {owners_text}")
    owners = [item.strip() for item in bracketed.group(1).split(",")]
    if not _valid_owners(owners):
        raise ValueError(f"invalid owners: {owners_text}")
    source_path = _fm_value(fm, "source_path")
    if not _valid_source_path(source_path):
        raise ValueError(f"invalid source_path: {source_path}")

    root = repo_root / source_path
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".sealed-provenance.json":
                full = Path(dirpath) / name
                entries.append((full.relative_to(root).as_posix(), full))
    entries.sort(key=lambda e: e[0])
    digest = hashlib.sha256()
    for rel, full in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(full.read_bytes())
        digest.update(b"\0")

    verifier = _load_gen("verifier-orchestrator", repo_root)
    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash="sha256:" + digest.hexdigest(),
        verifier_version=_get(verifier, "GATE_VERSION"),
    )


def _valid_sealed_manifest(doc) -> bool:
    if not isinstance(doc, dict) or set(doc) != _SEALED_KEYS:
        return False
    ch = doc["characterization"]
    if not isinstance(ch, dict) or set(ch) != _CHAR_KEYS:
        return False
    passed = ch["criteria_passed"]
    total = ch["criteria_total"]
    counts_ok = (
        type(passed) is int and type(total) is int and 0 <= passed <= total
    )
    return (
        doc["kind"] == "sealed-provenance"
        and type(doc["version"]) is int
        and doc["version"] == 1
        and _match(_COMPONENT_ID_RE, doc["component_id"])
        and _valid_owners(doc["owners"])
        and _valid_source_path(doc["source_path"])
        and _match(_SOURCE_HASH_RE, doc["source_hash"])
        and _match(_VERIFIER_RE, doc["verifier_version"])
        and ch["overall"] in ("pass", "fail")
        and counts_ok
        and (ch["overall"] != "pass" or (total >= 1 and passed == total))
        and _match(_WRITTEN_AT_RE, doc["written_at"])
    )


def _sealed_result(reason, sealed=True, doc=None) -> dict:
    hit = reason is None
    return {
        "hit": hit,
        "sealed": sealed,
        "reason": reason,
        "verification_report": (
            {"overall": doc["characterization"]["overall"]} if hit else None
        ),
        "license_scan": None,
        "secret_scan": None,
        "owners": doc["owners"] if hit else None,
        "source_hash": doc["source_hash"] if hit else None,
        "written_at": doc["written_at"] if hit else None,
    }


def check_sealed_provenance(component_id: str, repo_root: Path) -> dict:
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
    if (
        doc["component_id"] != "comp-" + _slug(component_id)
        or doc["source_path"] != key.source_path
    ):
        return _sealed_result("component_mismatch")
    if doc["source_hash"] != key.source_hash:
        return _sealed_result("source_changed")
    if doc["owners"] != key.owners:
        return _sealed_result("owners_changed")
    if doc["verifier_version"] != key.verifier_version:
        return _sealed_result("verifier_changed")
    if doc["characterization"]["overall"] != "pass":
        return _sealed_result("characterization_failed")
    return _sealed_result(None, doc=doc)


# ---------------------------------------------------------------- CLI

class _UsageError(Exception):
    pass


_FLAGS = ("--spec-bundle-hash", "--gate-versions", "--repo-root", "--format")


def _parse(argv: list) -> dict:
    if not argv or argv[0] != "check":
        raise _UsageError("unknown or missing subcommand")
    values = {}
    component_id = None
    i = 1
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _FLAGS:
                raise _UsageError(f"unknown argument {token}")
            if not eq:
                if i + 1 >= len(argv):
                    raise _UsageError(f"{name} needs a value")
                i += 1
                value = argv[i]
            values[name] = value
        elif component_id is None:
            component_id = token
        else:
            raise _UsageError(f"unknown argument {token}")
        i += 1

    if component_id is None:
        raise _UsageError("missing <component-id>")
    if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", component_id) is None:
        raise _UsageError(f"invalid component id {component_id}")
    if "--spec-bundle-hash" not in values:
        raise _UsageError("missing --spec-bundle-hash")
    if re.fullmatch(r"sha256:[0-9a-f]+", values["--spec-bundle-hash"]) is None:
        raise _UsageError("invalid --spec-bundle-hash")
    if "--gate-versions" not in values:
        raise _UsageError("missing --gate-versions")
    try:
        gate_versions = json.loads(values["--gate-versions"])
    except ValueError:
        raise _UsageError("--gate-versions is not JSON") from None
    if not isinstance(gate_versions, dict) or not all(
        isinstance(v, str) for v in gate_versions.values()
    ):
        raise _UsageError("--gate-versions must be a JSON object of strings")
    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format {fmt}")
    return {
        "component_id": component_id,
        "spec_bundle_hash": values["--spec-bundle-hash"],
        "gate_versions": gate_versions,
        "repo_root": Path(values["--repo-root"]) if "--repo-root" in values else Path.cwd(),
        "format": fmt,
    }


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    result = check_provenance(
        args["component_id"], args["spec_bundle_hash"],
        args["gate_versions"], args["repo_root"],
    )
    if args["format"] == "json":
        print(json.dumps(dict(result)))
    else:
        print(f"{'hit' if result['hit'] else 'miss'} {args['component_id']}")
    return 0
