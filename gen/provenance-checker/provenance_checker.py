"""Decides whether a committed .provenance.json proves an exact spec state."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceCheckResult:
    hit: bool
    verification_report: Any
    license_scan: Any
    secret_scan: Any

    def to_dict(self) -> dict:
        return {
            "hit": self.hit,
            "verification_report": self.verification_report,
            "license_scan": self.license_scan,
            "secret_scan": self.secret_scan,
        }


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
# Small helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id: str) -> str:
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _full_id(component_id: str) -> str:
    return f"comp-{_slug(component_id)}"


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("could not determine tool root: no ancestor directory named 'gen'")


def _load_module(module_name: str, dep_dir_rel: str, repo_root: Path):
    repo_base = Path(repo_root) / dep_dir_rel
    tool_base = _tool_root() / dep_dir_rel
    base = repo_base if repo_base.is_dir() else tool_base

    pkg_init = base / module_name / "__init__.py"
    flat = base / f"{module_name}.py"
    if pkg_init.is_file():
        path = pkg_init
        search_locations = [str(base / module_name)]
    elif flat.is_file():
        path = flat
        search_locations = None
    else:
        raise ModuleNotFoundError(f"cannot locate module '{module_name}' under '{base}'")

    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _trust_judge_provenance() -> bool:
    val = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
    if val is None or val == "":
        return True
    return val.strip().lower() != "false"


# ---------------------------------------------------------------------------
# check_provenance / current_provenance_key
# ---------------------------------------------------------------------------

def check_provenance(
    component_id: str,
    spec_bundle_hash: str,
    gate_versions: dict,
    repo_root: Path,
) -> ProvenanceCheckResult:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    manifest_path = repo_root / "gen" / slug / ".provenance.json"

    miss = ProvenanceCheckResult(
        hit=False, verification_report=None, license_scan=None, secret_scan=None
    )

    if not manifest_path.is_file():
        return miss

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return miss

    if not isinstance(manifest, dict):
        return miss

    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return miss
    if manifest.get("gate_versions") != gate_versions:
        return miss

    verification_report = manifest.get("verification_report")
    has_llm_judge = False
    if isinstance(verification_report, dict):
        for criterion in verification_report.get("criteria") or []:
            if isinstance(criterion, dict) and criterion.get("kind") == "llm-judge":
                has_llm_judge = True
                break

    if has_llm_judge and not _trust_judge_provenance():
        return miss

    return ProvenanceCheckResult(
        hit=True,
        verification_report=verification_report,
        license_scan=manifest.get("license_scan"),
        secret_scan=manifest.get("secret_scan"),
    )


def current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey:
    repo_root = Path(repo_root)

    assembler = _load_module("spec_bundle_assembler", "gen/spec-bundle-assembler/", repo_root)
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")

    compiler = _load_module("criterion_compiler", "pipeline/criterion-compiler/", repo_root)
    test_author_mod = _load_module("test_author", "gen/test-author/", repo_root)
    verifier_mod = _load_module("verifier_orchestrator", "gen/verifier-orchestrator/", repo_root)
    license_mod = _load_module("license_scanner", "gen/license-scanner/", repo_root)
    secret_mod = _load_module("secret_scanner", "gen/secret-scanner/", repo_root)

    gate_versions = {
        "compiler": compiler.GATE_VERSION,
        "generated_test": test_author_mod.GATE_VERSION,
        "verifier": verifier_mod.GATE_VERSION,
        "license_scanner": license_mod.gate_version(repo_root),
        "secret_scanner": secret_mod.gate_version(repo_root),
    }

    return ProvenanceKey(spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions)


# ---------------------------------------------------------------------------
# Sealed components
# ---------------------------------------------------------------------------

_OWNER_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_SOURCE_PATH_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?$")
_COMPONENT_ID_RE = re.compile(r"^comp-[a-z0-9]+(-[a-z0-9]+)*$")
_SOURCE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERIFIER_VERSION_RE = re.compile(r"^verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+$")
_WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_MANIFEST_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}
_CHAR_KEYS = {"overall", "criteria_passed", "criteria_total"}


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def _parse_owners(raw: str) -> list:
    raw = raw.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        raise ValueError(f"invalid owners frontmatter: {raw!r}")
    inner = raw[1:-1].strip()
    if not inner:
        raise ValueError("owners list must be non-empty")
    owners = [o.strip() for o in inner.split(",")]
    for owner in owners:
        if not _OWNER_RE.match(owner):
            raise ValueError(f"invalid owner: {owner!r}")
    return owners


def _validate_source_path(raw: str) -> None:
    raw = raw.strip()
    if not _SOURCE_PATH_RE.match(raw):
        raise ValueError(f"invalid source_path: {raw!r}")
    if raw.split("/")[0] == "gen":
        raise ValueError("source_path must not begin with 'gen'")


def _hash_source(source_dir: Path) -> str:
    digest = hashlib.sha256()
    if source_dir.is_dir():
        files = []
        for candidate in source_dir.rglob("*"):
            if candidate.is_dir():
                continue
            rel = candidate.relative_to(source_dir)
            if "__pycache__" in rel.parts:
                continue
            if candidate.name == ".sealed-provenance.json":
                continue
            files.append(candidate)
        files.sort(key=lambda p: p.relative_to(source_dir).as_posix())
        for f in files:
            rel = f.relative_to(source_dir).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\x00")
            digest.update(f.read_bytes())
            digest.update(b"\x00")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id: str, repo_root: Path) -> SealedKey | None:
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_md.is_file():
        return None

    frontmatter = _read_frontmatter(component_md)
    if frontmatter.get("sealed") != "true":
        return None

    owners_raw = frontmatter.get("owners")
    source_path_raw = frontmatter.get("source_path")
    if owners_raw is None or source_path_raw is None:
        raise ValueError(f"sealed component {component_id!r} missing owners or source_path")

    owners = _parse_owners(owners_raw)
    source_path = source_path_raw.strip()
    _validate_source_path(source_path)

    source_hash = _hash_source(repo_root / source_path)

    verifier_mod = _load_module("verifier_orchestrator", "gen/verifier-orchestrator/", repo_root)
    verifier_version = verifier_mod.GATE_VERSION

    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier_version,
    )


def _is_int_not_bool(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_sealed_manifest(doc) -> bool:
    if not isinstance(doc, dict) or set(doc.keys()) != _MANIFEST_KEYS:
        return False
    if doc.get("kind") != "sealed-provenance":
        return False
    if not (_is_int_not_bool(doc.get("version")) and doc.get("version") == 1):
        return False

    component_id = doc.get("component_id")
    if not isinstance(component_id, str) or not _COMPONENT_ID_RE.match(component_id):
        return False

    owners = doc.get("owners")
    if not isinstance(owners, list) or not owners:
        return False
    for owner in owners:
        if not isinstance(owner, str) or not _OWNER_RE.match(owner):
            return False

    source_path = doc.get("source_path")
    if not isinstance(source_path, str) or not _SOURCE_PATH_RE.match(source_path):
        return False
    if source_path.split("/")[0] == "gen":
        return False

    source_hash = doc.get("source_hash")
    if not isinstance(source_hash, str) or not _SOURCE_HASH_RE.match(source_hash):
        return False

    verifier_version = doc.get("verifier_version")
    if not isinstance(verifier_version, str) or not _VERIFIER_VERSION_RE.match(verifier_version):
        return False

    characterization = doc.get("characterization")
    if not isinstance(characterization, dict) or set(characterization.keys()) != _CHAR_KEYS:
        return False
    overall = characterization.get("overall")
    if overall not in ("pass", "fail"):
        return False
    passed = characterization.get("criteria_passed")
    total = characterization.get("criteria_total")
    if not (_is_int_not_bool(passed) and _is_int_not_bool(total)):
        return False
    if not (0 <= passed <= total):
        return False
    if overall == "pass" and not (total >= 1 and passed == total):
        return False

    written_at = doc.get("written_at")
    if not isinstance(written_at, str) or not _WRITTEN_AT_RE.match(written_at):
        return False

    return True


def check_sealed_provenance(component_id: str, repo_root: Path) -> dict:
    repo_root = Path(repo_root)

    key = current_sealed_key(component_id, repo_root)
    if key is None:
        return {
            "hit": False,
            "sealed": False,
            "reason": "not_sealed",
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
            "owners": None,
            "source_hash": None,
            "written_at": None,
        }

    def _miss(reason: str) -> dict:
        return {
            "hit": False,
            "sealed": True,
            "reason": reason,
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
            "owners": None,
            "source_hash": None,
            "written_at": None,
        }

    manifest_path = repo_root / key.source_path / ".sealed-provenance.json"
    if not manifest_path.is_file():
        return _miss("manifest_missing")

    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _miss("manifest_invalid")

    if not _validate_sealed_manifest(doc):
        return _miss("manifest_invalid")

    expected_component_id = _full_id(component_id)
    if doc["component_id"] != expected_component_id or doc["source_path"] != key.source_path:
        return _miss("component_mismatch")

    if doc["source_hash"] != key.source_hash:
        return _miss("source_changed")

    if doc["owners"] != key.owners:
        return _miss("owners_changed")

    if doc["verifier_version"] != key.verifier_version:
        return _miss("verifier_changed")

    characterization = doc["characterization"]
    if characterization["overall"] != "pass":
        return _miss("characterization_failed")

    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": characterization["overall"]},
        "license_scan": None,
        "secret_scan": None,
        "owners": doc["owners"],
        "source_hash": doc["source_hash"],
        "written_at": doc["written_at"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_COMPONENT_ID_CLI_RE = re.compile(r"^(comp-)?[a-z0-9]+(-[a-z0-9]+)*$")
_SPEC_HASH_CLI_RE = re.compile(r"^sha256:[0-9a-f]+$")


def _usage_error(message: str = "usage error") -> int:
    print(message, file=sys.stderr)
    return 2


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)

    if not argv or argv[0] != "check":
        return _usage_error("expected 'check' subcommand")

    args = argv[1:]

    component_id = None
    spec_bundle_hash = None
    gate_versions_raw = None
    repo_root_raw = "."
    fmt = "text"

    i = 0
    n = len(args)
    while i < n:
        token = args[i]
        if token.startswith("--"):
            if "=" in token:
                key, _, value = token.partition("=")
            else:
                key = token
                if i + 1 >= n:
                    return _usage_error(f"flag {key!r} given with no value")
                value = args[i + 1]
                i += 1

            if key == "--spec-bundle-hash":
                spec_bundle_hash = value
            elif key == "--gate-versions":
                gate_versions_raw = value
            elif key == "--repo-root":
                repo_root_raw = value
            elif key == "--format":
                fmt = value
            else:
                return _usage_error(f"unknown argument: {key}")
        else:
            if component_id is None:
                component_id = token
            else:
                return _usage_error(f"unexpected argument: {token}")
        i += 1

    if component_id is None:
        return _usage_error("missing <component-id>")
    if spec_bundle_hash is None:
        return _usage_error("missing --spec-bundle-hash")
    if gate_versions_raw is None:
        return _usage_error("missing --gate-versions")

    if not _COMPONENT_ID_CLI_RE.match(component_id):
        return _usage_error(f"invalid <component-id>: {component_id!r}")

    if not _SPEC_HASH_CLI_RE.match(spec_bundle_hash):
        return _usage_error(f"invalid --spec-bundle-hash: {spec_bundle_hash!r}")

    try:
        gate_versions = json.loads(gate_versions_raw)
    except ValueError:
        return _usage_error("invalid --gate-versions: not valid JSON")

    if not isinstance(gate_versions, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in gate_versions.items()
    ):
        return _usage_error("invalid --gate-versions: must be a JSON object of strings")

    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt!r}")

    result = check_provenance(component_id, spec_bundle_hash, gate_versions, Path(repo_root_raw))

    if fmt == "json":
        print(json.dumps(result.to_dict()))
    else:
        print(f"{'hit' if result.hit else 'miss'} {component_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())