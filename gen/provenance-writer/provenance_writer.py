"""Assembles and writes .provenance.json / .sealed-provenance.json manifests.

Collects already-produced results from other gate components into the
canonical schema; never computes or guesses a field's value itself.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PIPELINE_VERSION = "provenance-writer@1.0.0"

_MISSING = object()


class MissingInputError(Exception):
    """Raised when a required upstream result is absent from ProvenanceInputs."""


class InvalidSealedInputError(Exception):
    """Raised when SealedProvenanceInputs would not yield a valid manifest."""


def _get(obj: Any, key: str, default: Any = _MISSING) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        return default
    if hasattr(obj, key):
        return getattr(obj, key)
    return default


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "__dict__"):
        return {
            k: _to_jsonable(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return value


def _slug(component_id: str) -> str:
    if isinstance(component_id, str) and component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ProvenanceInputs:
    component_id: str
    generation_result: Any
    verification_report: Any
    license_scan_result: Any
    secret_scan_result: Any
    provenance_hit: bool
    attempts: int
    gate_versions: Dict[str, str]


@dataclass
class SealedProvenanceInputs:
    component_id: str
    owners: List[str]
    source_path: str
    source_hash: str
    verifier_version: str
    verification_report: Any


def build_manifest(inputs: Any, *, now: Optional[str] = None) -> Dict[str, Any]:
    generation_result = _get(inputs, "generation_result", _MISSING)
    if generation_result is _MISSING or generation_result is None:
        raise MissingInputError("generation_result missing")

    spec_bundle_hash = _get(generation_result, "spec_bundle_hash", _MISSING)
    model_pin = _get(generation_result, "model", _MISSING)
    prompt_version = _get(generation_result, "prompt_version", _MISSING)
    if spec_bundle_hash is _MISSING or model_pin is _MISSING or prompt_version is _MISSING:
        raise MissingInputError("generation_result missing a required field")
    retry_feedback = _get(generation_result, "retry_feedback", None)
    files = _get(generation_result, "files", {}) or {}

    verification_report = _get(inputs, "verification_report", _MISSING)
    if verification_report is _MISSING:
        raise MissingInputError("verification_report missing")
    if files and verification_report is None:
        raise MissingInputError(
            "verification_report required when generation produced files"
        )

    license_scan_result = _get(inputs, "license_scan_result", _MISSING)
    if license_scan_result is _MISSING or license_scan_result is None:
        raise MissingInputError("license_scan_result missing")

    secret_scan_result = _get(inputs, "secret_scan_result", _MISSING)
    if secret_scan_result is _MISSING or secret_scan_result is None:
        raise MissingInputError("secret_scan_result missing")

    provenance_hit = _get(inputs, "provenance_hit", _MISSING)
    if provenance_hit is _MISSING or provenance_hit is None:
        raise MissingInputError("provenance_hit missing")

    attempts = _get(inputs, "attempts", _MISSING)
    if attempts is _MISSING or attempts is None:
        raise MissingInputError("attempts missing")

    gate_versions = _get(inputs, "gate_versions", _MISSING)
    if gate_versions is _MISSING or gate_versions is None:
        raise MissingInputError("gate_versions missing")

    component_id = _get(inputs, "component_id", _MISSING)
    if component_id is _MISSING or component_id is None:
        raise MissingInputError("component_id missing")

    verification_run_id = f"{_slug(component_id)}-attempt-{attempts}"
    generated_at = now or _utc_now_iso()

    return {
        "spec_bundle_hash": spec_bundle_hash,
        "model_pin": model_pin,
        "prompt_version": prompt_version,
        "retry_feedback": retry_feedback,
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": _to_jsonable(gate_versions),
        "provenance_hit": provenance_hit,
        "generated_at": generated_at,
        "verification_run_id": verification_run_id,
        "verification_report": _to_jsonable(verification_report),
        "license_scan": _to_jsonable(license_scan_result),
        "secret_scan": _to_jsonable(secret_scan_result),
    }


def write_provenance(component_id: str, inputs: Any, repo_root: Path) -> None:
    repo_root = Path(repo_root)
    manifest = build_manifest(inputs)
    slug = _slug(component_id)
    content = json.dumps(manifest, indent=2) + "\n"
    for rel in (
        Path("gen") / slug / ".provenance.json",
        Path("verification") / slug / ".provenance.json",
    ):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


_COMPONENT_ID_RE = re.compile(r"^comp-[a-z0-9]+(-[a-z0-9]+)*$")
_OWNER_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_SOURCE_PATH_RE = re.compile(
    r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?$"
)
_SOURCE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERIFIER_VERSION_RE = re.compile(r"^verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+$")


def build_sealed_manifest(
    component_id: str, inputs: Any, *, now: Optional[str] = None
) -> Dict[str, Any]:
    input_component_id = _get(inputs, "component_id", _MISSING)
    owners = _get(inputs, "owners", _MISSING)
    source_path = _get(inputs, "source_path", _MISSING)
    source_hash = _get(inputs, "source_hash", _MISSING)
    verifier_version = _get(inputs, "verifier_version", _MISSING)
    verification_report = _get(inputs, "verification_report", _MISSING)

    for value in (
        input_component_id,
        owners,
        source_path,
        source_hash,
        verifier_version,
        verification_report,
    ):
        if value is _MISSING or value is None:
            raise InvalidSealedInputError("a required sealed input is missing")

    if input_component_id != component_id:
        raise InvalidSealedInputError("component_id does not match inputs.component_id")

    if not isinstance(input_component_id, str) or not _COMPONENT_ID_RE.match(
        input_component_id
    ):
        raise InvalidSealedInputError("component_id invalid")

    if (
        not isinstance(owners, list)
        or not owners
        or not all(isinstance(o, str) and _OWNER_RE.match(o) for o in owners)
    ):
        raise InvalidSealedInputError("owners invalid")

    if (
        not isinstance(source_path, str)
        or not _SOURCE_PATH_RE.match(source_path)
        or source_path.split("/")[0] == "gen"
    ):
        raise InvalidSealedInputError("source_path invalid")

    if not isinstance(source_hash, str) or not _SOURCE_HASH_RE.match(source_hash):
        raise InvalidSealedInputError("source_hash invalid")

    if not isinstance(verifier_version, str) or not _VERIFIER_VERSION_RE.match(
        verifier_version
    ):
        raise InvalidSealedInputError("verifier_version invalid")

    report_overall = _get(verification_report, "overall", _MISSING)
    report_criteria = _get(verification_report, "criteria", _MISSING)
    if (
        report_overall not in ("pass", "fail")
        or report_criteria is _MISSING
        or not isinstance(report_criteria, list)
        or not report_criteria
    ):
        raise InvalidSealedInputError("verification_report invalid")

    criteria_total = 0
    criteria_passed = 0
    for entry in report_criteria:
        result = _get(entry, "result", _MISSING)
        if result not in ("pass", "fail", "skipped"):
            raise InvalidSealedInputError("criterion result invalid")
        criteria_total += 1
        if result == "pass":
            criteria_passed += 1

    if report_overall == "pass" and (
        criteria_total < 1 or criteria_passed != criteria_total
    ):
        raise InvalidSealedInputError(
            "characterization overall pass inconsistent with criteria"
        )

    characterization = {
        "overall": report_overall,
        "criteria_passed": criteria_passed,
        "criteria_total": criteria_total,
    }

    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": input_component_id,
        "owners": list(owners),
        "source_path": source_path,
        "source_hash": source_hash,
        "verifier_version": verifier_version,
        "characterization": characterization,
        "written_at": now or _utc_now_iso(),
    }


def write_sealed_provenance(component_id: str, inputs: Any, repo_root: Path) -> None:
    repo_root = Path(repo_root)
    manifest = build_sealed_manifest(component_id, inputs)
    target_dir = repo_root / manifest["source_path"]
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / ".sealed-provenance.json"
    content = json.dumps(manifest, indent=2) + "\n"
    path.write_text(content, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 3 or argv[0] != "provenance" or argv[1] != "write":
        return 2

    component_id = argv[2]
    if component_id.startswith("--"):
        return 2

    rest = argv[3:]
    repo_root = "."
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--repo-root":
            if i + 1 >= len(rest):
                return 2
            repo_root = rest[i + 1]
            i += 2
        elif arg.startswith("--repo-root="):
            repo_root = arg[len("--repo-root="):]
            i += 1
        else:
            return 2

    try:
        raw = sys.stdin.read()
        inputs = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 2

    try:
        write_provenance(component_id, inputs, Path(repo_root))
    except MissingInputError:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())