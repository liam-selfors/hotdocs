"""Provenance checker: decides whether a component's committed
.provenance.json already proves it was verified against the exact
spec state currently being checked.

Pure, read-only, deterministic. No network access, no model calls.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

COMPONENT_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SPEC_BUNDLE_HASH_RE = re.compile(r"^sha256:[0-9a-f]+$")


@dataclass
class ProvenanceCheckResult:
    hit: bool
    verification_report: Optional[dict] = None
    license_scan: Optional[dict] = None
    secret_scan: Optional[dict] = None


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict = field(default_factory=dict)


def _get(obj, key, default=None):
    """Dual dict-or-attribute access for a value that may be either shape."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_dependency(repo_root: Path, dep_dir: str, module_name: str):
    base = Path(repo_root) / dep_dir
    flat = base / f"{module_name}.py"
    pkg = base / module_name / "__init__.py"
    if flat.is_file():
        path = flat
    elif pkg.is_file():
        path = pkg
    else:
        raise ModuleNotFoundError(
            f"cannot locate dependency module '{module_name}' under {base}"
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    # Must be registered in sys.modules before exec_module: dataclasses
    # defined in the loaded module look up sys.modules[cls.__module__]
    # while their class body executes.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _component_slug(component_id: str) -> str:
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _miss() -> ProvenanceCheckResult:
    return ProvenanceCheckResult(
        hit=False, verification_report=None, license_scan=None, secret_scan=None
    )


def _has_llm_judge_criterion(verification_report) -> bool:
    criteria = _get(verification_report, "criteria") or []
    for criterion in criteria:
        if _get(criterion, "kind") == "llm-judge":
            return True
    return False


def _trust_judge_provenance() -> bool:
    raw = os.environ.get("VAR_TRUST_JUDGE_PROVENANCE")
    if raw is None or raw == "":
        return True
    return raw.strip().lower() != "false"


def check_provenance(
    component_id: str,
    spec_bundle_hash: str,
    gate_versions: dict,
    repo_root: Path,
) -> ProvenanceCheckResult:
    repo_root = Path(repo_root)
    slug = _component_slug(component_id)
    manifest_path = repo_root / "gen" / slug / ".provenance.json"

    if not manifest_path.is_file():
        return _miss()

    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return _miss()

    manifest_hash = _get(manifest, "spec_bundle_hash")
    if manifest_hash != spec_bundle_hash:
        return _miss()

    manifest_gate_versions = _get(manifest, "gate_versions")
    if manifest_gate_versions != gate_versions:
        return _miss()

    verification_report = _get(manifest, "verification_report")
    license_scan = _get(manifest, "license_scan")
    secret_scan = _get(manifest, "secret_scan")

    if _has_llm_judge_criterion(verification_report) and not _trust_judge_provenance():
        return _miss()

    return ProvenanceCheckResult(
        hit=True,
        verification_report=verification_report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )


def current_provenance_key(component_id: str, repo_root: Path) -> ProvenanceKey:
    repo_root = Path(repo_root)

    assembler = _load_dependency(
        repo_root, "gen/spec-bundle-assembler", "spec_bundle_assembler"
    )
    bundle = assembler.assemble(component_id, repo_root=repo_root, mode="cold")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")

    criterion_compiler = _load_dependency(
        repo_root, "pipeline/criterion-compiler", "criterion_compiler"
    )
    compiler_version = getattr(criterion_compiler, "GATE_VERSION")

    test_author = _load_dependency(repo_root, "gen/test-author", "test_author")
    generated_test_version = getattr(test_author, "GATE_VERSION")

    verifier_orchestrator = _load_dependency(
        repo_root, "gen/verifier-orchestrator", "verifier_orchestrator"
    )
    verifier_version = getattr(verifier_orchestrator, "GATE_VERSION")

    license_scanner = _load_dependency(
        repo_root, "gen/license-scanner", "license_scanner"
    )
    license_version = license_scanner.gate_version(repo_root)

    secret_scanner = _load_dependency(
        repo_root, "gen/secret-scanner", "secret_scanner"
    )
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


def _usage_error(message: str) -> int:
    sys.stderr.write(f"usage error: {message}\n")
    return 2


def main(argv: Optional[list] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] != "check":
        return _usage_error("expected 'check' subcommand")

    args = argv[1:]

    component_id = None
    spec_bundle_hash = None
    gate_versions_raw = None
    repo_root = "."
    fmt = "text"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            if "=" in arg:
                flag, value = arg[2:].split("=", 1)
            else:
                flag = arg[2:]
                if i + 1 >= len(args):
                    return _usage_error(f"flag --{flag} given with no value")
                i += 1
                value = args[i]

            if flag == "spec-bundle-hash":
                spec_bundle_hash = value
            elif flag == "gate-versions":
                gate_versions_raw = value
            elif flag == "repo-root":
                repo_root = value
            elif flag == "format":
                fmt = value
            else:
                return _usage_error(f"unknown flag --{flag}")
        else:
            if component_id is None:
                component_id = arg
            else:
                return _usage_error(f"unexpected argument '{arg}'")
        i += 1

    if component_id is None:
        return _usage_error("missing <component-id>")
    if spec_bundle_hash is None:
        return _usage_error("missing --spec-bundle-hash")
    if gate_versions_raw is None:
        return _usage_error("missing --gate-versions")

    if not COMPONENT_ID_RE.match(component_id):
        return _usage_error("invalid <component-id>")
    if not SPEC_BUNDLE_HASH_RE.match(spec_bundle_hash):
        return _usage_error("invalid --spec-bundle-hash")

    try:
        gate_versions = json.loads(gate_versions_raw)
    except json.JSONDecodeError:
        return _usage_error("invalid --gate-versions: not valid JSON")

    if not isinstance(gate_versions, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in gate_versions.items()
    ):
        return _usage_error("invalid --gate-versions: must be a JSON object of strings")

    if fmt not in ("json", "text"):
        return _usage_error("invalid --format")

    result = check_provenance(
        component_id, spec_bundle_hash, gate_versions, Path(repo_root)
    )

    if fmt == "json":
        print(json.dumps(dataclasses.asdict(result)))
    else:
        print(("hit" if result.hit else "miss") + " " + component_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())