"""Provenance Writer: assembles and writes `.provenance.json` and the sealed
counterpart `.sealed-provenance.json`. Collects, never invents."""

import dataclasses
import enum
import json
import math
import pathlib
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "v1"

USAGE = "usage: hotdocs provenance write <component-id> [--repo-root=<dir>]"

_ATTEMPT_KEYS = (
    "number",
    "outcome",
    "retry_feedback",
    "error_category",
    "failed_requirements",
    "transcript_sha256",
)

_REQUIRED = (
    "component_id",
    "generation_result",
    "license_scan_result",
    "secret_scan_result",
    "provenance_hit",
    "attempts",
    "gate_versions",
)

_SEALED_FIELDS = (
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "verification_report",
)


class MissingInputError(Exception):
    """A required upstream result was absent."""


class InvalidSealedInputError(ValueError):
    """The sealed inputs would not yield a valid sealed provenance manifest."""


@dataclasses.dataclass
class ProvenanceInputs:
    component_id: object = None
    generation_result: object = None
    verification_report: object = None
    license_scan_result: object = None
    secret_scan_result: object = None
    provenance_hit: object = None
    attempts: object = None
    attempt_history: object = None
    gate_versions: object = None


@dataclasses.dataclass
class SealedProvenanceInputs:
    component_id: object = None
    owners: object = None
    source_path: object = None
    source_hash: object = None
    verifier_version: object = None
    verification_report: object = None


def _get(obj, name):
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def to_json(value):
    """Convert `value` to a json.dumps-acceptable value (json-values.md)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(component_id):
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def build_manifest(inputs):
    """Build the provenance manifest dict from `inputs` (dict or object)."""
    for name in _REQUIRED:
        if _get(inputs, name) is None:
            raise MissingInputError(f"missing required input: {name}")
    gr = _get(inputs, "generation_result")
    vr = _get(inputs, "verification_report")
    if vr is None and _get(gr, "files"):
        raise MissingInputError(
            "missing required input: verification_report "
            "(generation_result.files is non-empty)"
        )
    gate_versions = _get(inputs, "gate_versions")
    attempts = _get(inputs, "attempts")
    component_id = _get(inputs, "component_id")
    mode = _get(gr, "mode")
    history = _get(inputs, "attempt_history")
    if history is None:
        history = []
    assets = None if vr is None else _get(vr, "assets")
    if assets is None:
        assets = []
    manifest = {
        "spec_bundle_hash": _get(gr, "spec_bundle_hash"),
        "model_pin": _get(gr, "model"),
        "prompt_version": _get(gr, "prompt_version"),
        "retry_feedback": _get(gr, "retry_feedback"),
        "generation": {
            "mode": "single" if mode is None else mode,
            "generator_version": _get(gate_versions, "generator"),
            "transcript_sha256": _get(gr, "transcript_sha256"),
            "turns": _get(gr, "turns"),
            "tool_calls": _get(gr, "tool_calls"),
            "isolation": _get(gr, "isolation"),
        },
        "attempts": attempts,
        "attempt_history": [
            {key: _get(entry, key) for key in _ATTEMPT_KEYS} for entry in history
        ],
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": gate_versions,
        "provenance_hit": _get(inputs, "provenance_hit"),
        "generated_at": _now(),
        "verification_run_id": f"{_slug(component_id)}-attempt-{attempts}",
        "verification_report": vr,
        "license_scan": _get(inputs, "license_scan_result"),
        "secret_scan": _get(inputs, "secret_scan_result"),
        "assets": assets,
    }
    return to_json(manifest)


def write_provenance(component_id, inputs, repo_root):
    manifest = build_manifest(inputs)
    text = json.dumps(manifest, indent=2) + "\n"
    slug = _slug(component_id)
    root = Path(repo_root)
    for base in ("gen", "verification"):
        directory = root / base / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".provenance.json").write_text(text, encoding="utf-8")


_COMPONENT_ID_RE = r"^comp-[a-z0-9]+(-[a-z0-9]+)*$"
_OWNER_RE = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_SOURCE_PATH_RE = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?$"
_SOURCE_HASH_RE = r"^sha256:[0-9a-f]{64}$"
_VERIFIER_RE = r"^verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+$"


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _valid_sealed(manifest):
    owners = manifest["owners"]
    if not isinstance(owners, list) or not owners:
        return False
    if not all(_matches(_OWNER_RE, owner) for owner in owners):
        return False
    source_path = manifest["source_path"]
    if not _matches(_SOURCE_PATH_RE, source_path):
        return False
    if source_path.split("/")[0] == "gen":
        return False
    return (
        _matches(_COMPONENT_ID_RE, manifest["component_id"])
        and _matches(_SOURCE_HASH_RE, manifest["source_hash"])
        and _matches(_VERIFIER_RE, manifest["verifier_version"])
    )


def write_sealed_provenance(component_id, inputs, repo_root):
    values = {name: _get(inputs, name) for name in _SEALED_FIELDS}
    for name, value in values.items():
        if value is None:
            raise InvalidSealedInputError(f"missing sealed input: {name}")
    if component_id != values["component_id"]:
        raise InvalidSealedInputError(
            "component_id does not match inputs.component_id"
        )
    report = values["verification_report"]
    criteria = _get(report, "criteria")
    if not isinstance(criteria, (list, tuple)) or not criteria:
        raise InvalidSealedInputError("verification_report has no criteria")
    results = [_get(entry, "result") for entry in criteria]
    if any(result not in ("pass", "fail", "skipped") for result in results):
        raise InvalidSealedInputError("criterion result not pass/fail/skipped")
    overall = _get(report, "overall")
    if overall not in ("pass", "fail"):
        raise InvalidSealedInputError("verification_report overall not pass/fail")
    total = len(results)
    passed = sum(1 for result in results if result == "pass")
    if overall == "pass" and passed != total:
        raise InvalidSealedInputError("overall pass with non-passing criteria")
    manifest = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": to_json(values["component_id"]),
        "owners": to_json(values["owners"]),
        "source_path": to_json(values["source_path"]),
        "source_hash": to_json(values["source_hash"]),
        "verifier_version": to_json(values["verifier_version"]),
        "characterization": {
            "overall": overall,
            "criteria_passed": passed,
            "criteria_total": total,
        },
        "written_at": _now(),
    }
    if not _valid_sealed(manifest):
        raise InvalidSealedInputError("inputs do not yield a valid sealed manifest")
    directory = Path(repo_root) / manifest["source_path"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".sealed-provenance.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:2] != ["provenance", "write"]:
        return _usage_error("expected 'provenance write'")
    repo_root = "."
    positionals = []
    rest = argv[2:]
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--repo-root="):
            repo_root = token[len("--repo-root="):]
        elif token == "--repo-root":
            if i + 1 >= len(rest):
                return _usage_error("--repo-root requires a value")
            repo_root = rest[i + 1]
            i += 1
        elif token.startswith("--"):
            return _usage_error(f"unrecognized argument: {token}")
        else:
            positionals.append(token)
        i += 1
    if len(positionals) != 1:
        return _usage_error("expected exactly one <component-id>")
    try:
        inputs = json.loads(sys.stdin.read())
    except ValueError as exc:
        return _usage_error(f"malformed JSON on stdin: {exc}")
    try:
        write_provenance(positionals[0], inputs, Path(repo_root))
    except MissingInputError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
