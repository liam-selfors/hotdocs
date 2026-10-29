"""Assembles and writes `.provenance.json` manifests (`SPEC_GUIDELINES.md` §7)."""

from __future__ import annotations

import dataclasses
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PIPELINE_VERSION = "v1"

_MISSING = object()


class MissingInputError(Exception):
    """A required upstream result was absent from `ProvenanceInputs`."""


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


def _get(obj: Any, name: str, default: Any = _MISSING) -> Any:
    if isinstance(obj, dict):
        if name in obj:
            return obj[name]
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    return default


def _get_required(obj: Any, name: str) -> Any:
    value = _get(obj, name)
    if value is _MISSING:
        raise MissingInputError(f"missing required field: {name!r}")
    return value


def _slug(component_id: str) -> str:
    prefix = "comp-"
    return component_id[len(prefix):] if component_id.startswith(prefix) else component_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _to_jsonable(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    try:
        items = list(vars(value).items())
    except TypeError:
        items = [
            (name, getattr(value, name))
            for name in dir(value)
            if not name.startswith("_")
        ]
    result: Dict[str, Any] = {}
    for key, val in items:
        if key.startswith("_") or callable(val):
            continue
        result[key] = _to_jsonable(val)
    return result


def build_manifest(inputs: Any) -> Dict[str, Any]:
    component_id = _get_required(inputs, "component_id")
    generation_result = _get_required(inputs, "generation_result")
    license_scan_result = _get_required(inputs, "license_scan_result")
    secret_scan_result = _get_required(inputs, "secret_scan_result")
    provenance_hit = _get_required(inputs, "provenance_hit")
    attempts = _get_required(inputs, "attempts")
    gate_versions = _get_required(inputs, "gate_versions")
    verification_report = _get(inputs, "verification_report", None)

    spec_bundle_hash = _get_required(generation_result, "spec_bundle_hash")
    model_pin = _get_required(generation_result, "model")
    prompt_version = _get_required(generation_result, "prompt_version")
    retry_feedback = _get(generation_result, "retry_feedback", None)

    slug = _slug(component_id)
    verification_run_id = f"{slug}-attempt-{attempts}"

    return {
        "spec_bundle_hash": spec_bundle_hash,
        "model_pin": model_pin,
        "prompt_version": prompt_version,
        "retry_feedback": _to_jsonable(retry_feedback),
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": _to_jsonable(gate_versions),
        "provenance_hit": bool(provenance_hit),
        "generated_at": _now_iso(),
        "verification_run_id": verification_run_id,
        "verification_report": _to_jsonable(verification_report),
        "license_scan": _to_jsonable(license_scan_result),
        "secret_scan": _to_jsonable(secret_scan_result),
    }


def write_provenance(component_id: str, inputs: Any, repo_root: Path) -> None:
    manifest = build_manifest(inputs)
    repo_root = Path(repo_root)
    slug = _slug(component_id)
    content = json.dumps(manifest, indent=2) + "\n"
    for base in ("gen", "verification"):
        path = repo_root / base / slug / ".provenance.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = list(argv)
    if len(args) < 2 or args[0] != "provenance" or args[1] != "write":
        return 2
    rest = args[2:]
    positional = []
    repo_root = Path(".")
    for arg in rest:
        if arg.startswith("--repo-root="):
            repo_root = Path(arg.split("=", 1)[1])
        elif arg.startswith("--"):
            return 2
        else:
            positional.append(arg)
    if len(positional) != 1:
        return 2
    component_id = positional[0]
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 2
    try:
        write_provenance(component_id, data, repo_root)
    except MissingInputError:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())