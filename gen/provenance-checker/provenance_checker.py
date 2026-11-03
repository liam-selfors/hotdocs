"""Decides whether a committed .provenance.json proves prior verification
against a caller-supplied current spec-bundle-hash / gate-versions key."""

import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict = field(default_factory=dict)


@dataclass
class SealedKey:
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str


_COMPONENT_ID_CLI_RE = re.compile(r"^(comp-)?[a-z0-9]+(-[a-z0-9]+)*$")
_SPEC_HASH_RE = re.compile(r"^sha256:[0-9a-f]+$")

_SEALED_FRONTMATTER_SEALED_TRUE = "true"

_COMPONENT_ID_RE = re.compile(r"^comp-[a-z0-9]+(-[a-z0-9]+)*$")
_OWNER_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_SOURCE_PATH_RE = re.compile(
    r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?$"
)
_SOURCE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERIFIER_VERSION_RE = re.compile(r"^verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+$")
_WRITTEN_AT_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)

_SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}
_CHAR_KEYS = {"overall", "criteria_passed", "criteria_total"}

_SEALED_REASONS = (
    "not_sealed", "manifest_missing", "manifest_invalid", "component_mismatch",
    "source_changed", "owners_changed", "verifier_changed", "characterization_failed",
)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_dependency(repo_root, dep_relpath, module_name):
    base = Path(repo_root) / dep_relpath
    pkg_init = base / module_name / "__init__.py"
    flat = base / (module_name + ".py")
    if pkg_init.exists():
        file_path = pkg_init
        search_locations = [str(base / module_name)]
    elif flat.exists():
        file_path = flat
        search_locations = None
    else:
        raise ImportError(f"cannot locate module {module_name!r} under {base}")

    spec = importlib.util.spec_from_file_location(
        module_name, file_path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _trust_judge_provenance():
    raw = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() != "false"


def _has_llm_judge(verification_report):
    if verification_report is None:
        return False
    criteria = _get(verification_report, "criteria")
    if not criteria:
        return False
    for criterion in criteria:
        if _get(criterion, "kind") == "llm-judge":
            return True
    return False


def current_provenance_key(component_id, repo_root):
    repo_root = Path(repo_root)

    assembler = _load_dependency(repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")

    criterion_compiler = _load_dependency(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
    compiler_version = getattr(criterion_compiler, "GATE_VERSION", None)

    test_author = _load_dependency(repo_root, "gen/test-author", "test_author")
    generated_test_version = getattr(test_author, "GATE_VERSION", None)

    verifier_orchestrator = _load_dependency(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    verifier_version = getattr(verifier_orchestrator, "GATE_VERSION", None)

    license_scanner = _load_dependency(repo_root, "gen/license-scanner", "license_scanner")
    license_version = license_scanner.gate_version(repo_root)

    secret_scanner = _load_dependency(repo_root, "gen/secret-scanner", "secret_scanner")
    secret_version = secret_scanner.gate_version(repo_root)

    return ProvenanceKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_versions={
            "compiler": compiler_version,
            "generated_test": generated_test_version,
            "verifier": verifier_version,
            "license_scanner": license_version,
            "secret_scanner": secret_version,
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    manifest_path = repo_root / "gen" / slug / ".provenance.json"

    miss = {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}

    if not manifest_path.exists():
        return miss

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        return miss

    manifest_hash = _get(manifest, "spec_bundle_hash")
    manifest_gate_versions = _get(manifest, "gate_versions")

    if manifest_hash != spec_bundle_hash:
        return miss

    if not isinstance(manifest_gate_versions, dict):
        return miss

    if manifest_gate_versions != gate_versions:
        return miss

    verification_report = _get(manifest, "verification_report")
    license_scan = _get(manifest, "license_scan")
    secret_scan = _get(manifest, "secret_scan")

    if _has_llm_judge(verification_report) and not _trust_judge_provenance():
        return miss

    return {
        "hit": True,
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    result = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
        i += 1
    return result


def _parse_owners(raw):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [item.strip() for item in inner.split(",") if item.strip()]
    return [raw] if raw else []


def _hash_source_dir(source_dir):
    digest = hashlib.sha256()
    if source_dir.exists():
        files = []
        for path in source_dir.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(source_dir)
            if "__pycache__" in rel.parts:
                continue
            if path.name == ".sealed-provenance.json":
                continue
            files.append(path)
        files.sort(key=lambda p: p.relative_to(source_dir).as_posix())
        for path in files:
            rel_posix = path.relative_to(source_dir).as_posix()
            digest.update(rel_posix.encode("utf-8"))
            digest.update(b"\x00")
            digest.update(path.read_bytes())
            digest.update(b"\x00")
    return "sha256:" + digest.hexdigest()


def current_sealed_key(component_id, repo_root):
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    component_md = repo_root / "specs" / "components" / slug / "component.md"
    if not component_md.exists():
        return None

    text = component_md.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)
    if frontmatter is None:
        return None

    sealed_value = frontmatter.get("sealed", "").strip().lower()
    if sealed_value != _SEALED_FRONTMATTER_SEALED_TRUE:
        return None

    owners_raw = frontmatter.get("owners")
    source_path_raw = frontmatter.get("source_path")
    if owners_raw is None or source_path_raw is None:
        raise ValueError(
            f"sealed component {component_id!r} is missing owners or source_path in frontmatter"
        )

    owners = _parse_owners(owners_raw)
    if not owners or not all(_OWNER_RE.match(owner) for owner in owners):
        raise ValueError(f"sealed component {component_id!r} has invalid owners: {owners_raw!r}")

    source_path = source_path_raw.strip()
    if not _SOURCE_PATH_RE.match(source_path) or source_path.split("/")[0] == "gen":
        raise ValueError(
            f"sealed component {component_id!r} has invalid source_path: {source_path_raw!r}"
        )

    verifier_orchestrator = _load_dependency(repo_root, "gen/verifier-orchestrator", "verifier_orchestrator")
    verifier_version = getattr(verifier_orchestrator, "GATE_VERSION", None)

    source_hash = _hash_source_dir(repo_root / source_path)

    return SealedKey(
        owners=owners,
        source_path=source_path,
        source_hash=source_hash,
        verifier_version=verifier_version,
    )


def _is_int_not_bool(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_sealed_manifest(manifest):
    if not isinstance(manifest, dict):
        return False
    if set(manifest.keys()) != _SEALED_KEYS:
        return False
    if manifest.get("kind") != "sealed-provenance":
        return False
    if not _is_int_not_bool(manifest.get("version")) or manifest.get("version") != 1:
        return False

    component_id_value = manifest.get("component_id")
    if not isinstance(component_id_value, str) or not _COMPONENT_ID_RE.match(component_id_value):
        return False

    owners = manifest.get("owners")
    if not isinstance(owners, list) or not owners:
        return False
    for owner in owners:
        if not isinstance(owner, str) or not _OWNER_RE.match(owner):
            return False

    source_path = manifest.get("source_path")
    if not isinstance(source_path, str) or not _SOURCE_PATH_RE.match(source_path):
        return False
    if source_path.split("/")[0] == "gen":
        return False

    source_hash = manifest.get("source_hash")
    if not isinstance(source_hash, str) or not _SOURCE_HASH_RE.match(source_hash):
        return False

    verifier_version = manifest.get("verifier_version")
    if not isinstance(verifier_version, str) or not _VERIFIER_VERSION_RE.match(verifier_version):
        return False

    characterization = manifest.get("characterization")
    if not isinstance(characterization, dict) or set(characterization.keys()) != _CHAR_KEYS:
        return False
    overall = characterization.get("overall")
    if overall not in ("pass", "fail"):
        return False
    passed = characterization.get("criteria_passed")
    total = characterization.get("criteria_total")
    if not _is_int_not_bool(passed) or not _is_int_not_bool(total):
        return False
    if not (0 <= passed <= total):
        return False
    if overall == "pass" and not (total >= 1 and passed == total):
        return False

    written_at = manifest.get("written_at")
    if not isinstance(written_at, str) or not _WRITTEN_AT_RE.match(written_at):
        return False

    return True


def _sealed_result(reason):
    return {
        "hit": reason is None,
        "sealed": reason != "not_sealed",
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
        return _sealed_result("not_sealed")

    source_path = key.source_path
    manifest_path = repo_root / source_path / ".sealed-provenance.json"
    if not manifest_path.exists():
        return _sealed_result("manifest_missing")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        return _sealed_result("manifest_invalid")

    if not _is_valid_sealed_manifest(manifest):
        return _sealed_result("manifest_invalid")

    normalized_component_id = (
        component_id if component_id.startswith("comp-") else "comp-" + component_id
    )
    if manifest.get("component_id") != normalized_component_id or manifest.get("source_path") != source_path:
        return _sealed_result("component_mismatch")

    if manifest.get("source_hash") != key.source_hash:
        return _sealed_result("source_changed")

    if manifest.get("owners") != key.owners:
        return _sealed_result("owners_changed")

    if manifest.get("verifier_version") != key.verifier_version:
        return _sealed_result("verifier_changed")

    characterization = manifest.get("characterization") or {}
    if characterization.get("overall") != "pass":
        return _sealed_result("characterization_failed")

    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": characterization.get("overall")},
        "license_scan": None,
        "secret_scan": None,
        "owners": manifest.get("owners"),
        "source_hash": manifest.get("source_hash"),
        "written_at": manifest.get("written_at"),
    }


def _usage_error():
    print("usage: hotdocs provenance check <component-id> --spec-bundle-hash=<h> "
          "--gate-versions=<json> [--repo-root=<dir>] [--format=json|text]", file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)

    if not args or args[0] != "check":
        return _usage_error()
    args = args[1:]

    positionals = []
    spec_bundle_hash = None
    gate_versions_raw = None
    repo_root_raw = None
    format_raw = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            if "=" in arg:
                key, _, value = arg.partition("=")
            else:
                key = arg
                if i + 1 >= len(args):
                    return _usage_error()
                value = args[i + 1]
                i += 1
            if key == "--spec-bundle-hash":
                spec_bundle_hash = value
            elif key == "--gate-versions":
                gate_versions_raw = value
            elif key == "--repo-root":
                repo_root_raw = value
            elif key == "--format":
                format_raw = value
            else:
                return _usage_error()
        else:
            positionals.append(arg)
        i += 1

    if len(positionals) != 1:
        return _usage_error()
    component_id = positionals[0]

    if not _COMPONENT_ID_CLI_RE.match(component_id):
        return _usage_error()

    if spec_bundle_hash is None or gate_versions_raw is None:
        return _usage_error()

    if not _SPEC_HASH_RE.match(spec_bundle_hash):
        return _usage_error()

    try:
        gate_versions = json.loads(gate_versions_raw)
    except ValueError:
        return _usage_error()

    if not isinstance(gate_versions, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in gate_versions.items()
    ):
        return _usage_error()

    fmt = format_raw if format_raw is not None else "text"
    if fmt not in ("json", "text"):
        return _usage_error()

    repo_root = Path(repo_root_raw) if repo_root_raw else Path.cwd()

    result = check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root)
    hit = _get(result, "hit")

    if fmt == "json":
        print(json.dumps(result))
    else:
        print(f"{'hit' if hit else 'miss'} {component_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())