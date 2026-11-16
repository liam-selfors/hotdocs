"""Provenance Writer.

Assembles ``.provenance.json`` (``SPEC_GUIDELINES.md`` section 7) from every
other gate component's own already-produced output and writes it to both
``gen/<slug>/`` and ``verification/<slug>/``. Also writes a sealed
component's ``.sealed-provenance.json`` manifest. Collects, never invents.
"""

import dataclasses
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

PIPELINE_VERSION = "v1"

_REQUIRED_INPUTS = (
    "component_id",
    "generation_result",
    "license_scan_result",
    "secret_scan_result",
    "provenance_hit",
    "attempts",
    "gate_versions",
)

_SEALED_INPUTS = (
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "verification_report",
)

_COMPONENT_ID = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SOURCE_PATH = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
)
_SOURCE_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_VERIFIER_VERSION = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")


class MissingInputError(Exception):
    """A required upstream result was absent; no manifest is written."""


class InvalidSealedInputError(Exception):
    """Sealed inputs that would not yield a valid sealed provenance manifest."""


@dataclasses.dataclass
class ProvenanceInputs:
    component_id: Any
    generation_result: Any
    verification_report: Any
    license_scan_result: Any
    secret_scan_result: Any
    provenance_hit: Any
    attempts: Any
    gate_versions: Any


@dataclasses.dataclass
class SealedProvenanceInputs:
    component_id: Any
    owners: Any
    source_path: Any
    source_hash: Any
    verifier_version: Any
    verification_report: Any


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _to_jsonable(value):
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float)):
        return value
    return {
        key: _to_jsonable(item)
        for key, item in vars(value).items()
        if not key.startswith("_") and not callable(item)
    }


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _serialize(manifest):
    return json.dumps(manifest, indent=2) + "\n"


def build_manifest(inputs):
    for name in _REQUIRED_INPUTS:
        if _get(inputs, name) is None:
            raise MissingInputError(name)
    generation_result = _get(inputs, "generation_result")
    verification_report = _get(inputs, "verification_report")
    if verification_report is None and _get(generation_result, "files"):
        raise MissingInputError("verification_report")
    component_id = _get(inputs, "component_id")
    attempts = _get(inputs, "attempts")
    return {
        "spec_bundle_hash": _get(generation_result, "spec_bundle_hash"),
        "model_pin": _get(generation_result, "model"),
        "prompt_version": _get(generation_result, "prompt_version"),
        "retry_feedback": _to_jsonable(_get(generation_result, "retry_feedback")),
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": _to_jsonable(_get(inputs, "gate_versions")),
        "provenance_hit": _get(inputs, "provenance_hit"),
        "generated_at": _now_iso(),
        "verification_run_id": f"{_slug(component_id)}-attempt-{attempts}",
        "verification_report": _to_jsonable(verification_report),
        "license_scan": _to_jsonable(_get(inputs, "license_scan_result")),
        "secret_scan": _to_jsonable(_get(inputs, "secret_scan_result")),
    }


def write_provenance(component_id, inputs, repo_root):
    text = _serialize(build_manifest(inputs))
    slug = _slug(component_id)
    root = Path(repo_root)
    for top in ("gen", "verification"):
        target = root / top / slug / ".provenance.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _require(ok):
    if not ok:
        raise InvalidSealedInputError("inputs do not yield a valid sealed provenance manifest")


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def write_sealed_provenance(component_id, inputs, repo_root):
    values = {name: _get(inputs, name) for name in _SEALED_INPUTS}
    _require(all(value is not None for value in values.values()))
    _require(component_id == values["component_id"])

    owners = values["owners"]
    source_path = values["source_path"]
    report = values["verification_report"]

    _require(_matches(_COMPONENT_ID, component_id))
    _require(
        isinstance(owners, list)
        and len(owners) > 0
        and all(_matches(_OWNER, owner) for owner in owners)
    )
    _require(
        _matches(_SOURCE_PATH, source_path) and source_path.split("/")[0] != "gen"
    )
    _require(_matches(_SOURCE_HASH, values["source_hash"]))
    _require(_matches(_VERIFIER_VERSION, values["verifier_version"]))

    criteria = _get(report, "criteria")
    overall = _get(report, "overall")
    _require(isinstance(criteria, list) and len(criteria) > 0)
    results = [_get(entry, "result") for entry in criteria]
    _require(all(result in ("pass", "fail", "skipped") for result in results))
    _require(overall in ("pass", "fail"))
    passed = sum(1 for result in results if result == "pass")
    total = len(results)
    _require(overall != "pass" or passed == total)

    manifest = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": values["component_id"],
        "owners": owners,
        "source_path": source_path,
        "source_hash": values["source_hash"],
        "verifier_version": values["verifier_version"],
        "characterization": {
            "overall": overall,
            "criteria_passed": passed,
            "criteria_total": total,
        },
        "written_at": _now_iso(),
    }
    target_dir = Path(repo_root) / source_path
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / ".sealed-provenance.json").write_text(
        _serialize(manifest), encoding="utf-8"
    )


def main(argv):
    argv = list(argv)
    if argv[:2] != ["provenance", "write"]:
        return 2
    rest = argv[2:]
    component_id = None
    repo_root = "."
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg.startswith("--repo-root="):
            repo_root = arg[len("--repo-root="):]
        elif arg == "--repo-root":
            if i + 1 >= len(rest):
                return 2
            i += 1
            repo_root = rest[i]
        elif arg.startswith("--"):
            return 2
        elif component_id is None:
            component_id = arg
        else:
            return 2
        i += 1
    if component_id is None:
        return 2
    try:
        inputs = json.loads(sys.stdin.read())
    except ValueError:
        return 2
    try:
        write_provenance(component_id, inputs, Path(repo_root))
    except MissingInputError:
        return 1
    return 0
