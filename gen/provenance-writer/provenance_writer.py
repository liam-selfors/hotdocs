"""Provenance writer: assembles and writes `.provenance.json` and
`.sealed-provenance.json` from other components' already-produced results.

Collects, never invents.
"""

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

_REQUIRED_INPUTS = (
    "component_id",
    "generation_result",
    "license_scan_result",
    "secret_scan_result",
    "provenance_hit",
    "attempts",
    "gate_versions",
)

_SEALED_INPUT_FIELDS = (
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "verification_report",
)

_COMPONENT_ID_RE = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SOURCE_PATH_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
)
_SOURCE_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VERIFIER_VERSION_RE = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")


class MissingInputError(Exception):
    """A required upstream result was absent."""


class InvalidSealedInputError(Exception):
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
    """Convert `value` per specs/architecture/json-values.md."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v) for k, v in value.items()
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
            f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


def _slug(component_id):
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(component_id, inputs):
    """Return the provenance manifest dict for `inputs` (raises MissingInputError)."""
    for name in _REQUIRED_INPUTS:
        if _get(inputs, name) is None:
            raise MissingInputError(f"missing required input: {name}")

    gr = _get(inputs, "generation_result")
    vr = _get(inputs, "verification_report")
    if vr is None and _get(gr, "files"):
        raise MissingInputError(
            "missing required input: verification_report "
            "(generation_result.files is non-empty)"
        )

    license_scan = _get(inputs, "license_scan_result")
    secret_scan = _get(inputs, "secret_scan_result")
    provenance_hit = _get(inputs, "provenance_hit")
    attempts = _get(inputs, "attempts")
    gate_versions = _get(inputs, "gate_versions")
    history = _get(inputs, "attempt_history")
    inputs_component_id = _get(inputs, "component_id")

    mode = _get(gr, "mode")
    generation = {
        "mode": "single" if mode is None else mode,
        "generator_version": _get(gate_versions, "generator"),
        "transcript_sha256": _get(gr, "transcript_sha256"),
        "turns": _get(gr, "turns"),
        "tool_calls": _get(gr, "tool_calls"),
        "isolation": _get(gr, "isolation"),
    }

    attempt_history = [
        {key: _get(entry, key) for key in _ATTEMPT_KEYS} for entry in (history or [])
    ]

    assets = _get(vr, "assets") if vr is not None else None

    manifest = {
        "spec_bundle_hash": _get(gr, "spec_bundle_hash"),
        "model_pin": _get(gr, "model"),
        "prompt_version": _get(gr, "prompt_version"),
        "retry_feedback": _get(gr, "retry_feedback"),
        "generation": generation,
        "attempts": attempts,
        "attempt_history": attempt_history,
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": gate_versions,
        "provenance_hit": provenance_hit,
        "generated_at": _now(),
        "verification_run_id": f"{_slug(inputs_component_id)}-attempt-{attempts}",
        "verification_report": vr,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
        "assets": [] if assets is None else assets,
    }
    return to_json(manifest)


def write_provenance(component_id, inputs, repo_root):
    manifest = build_manifest(component_id, inputs)
    text = json.dumps(manifest, indent=2) + "\n"
    slug = _slug(component_id)
    root = Path(repo_root)
    for base in ("gen", "verification"):
        directory = root / base / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".provenance.json").write_text(text, encoding="utf-8")


def _invalid(message):
    raise InvalidSealedInputError(message)


def _is_str(value):
    return isinstance(value, str)


def _build_sealed_manifest(component_id, inputs):
    values = {name: _get(inputs, name) for name in _SEALED_INPUT_FIELDS}
    for name, value in values.items():
        if value is None:
            _invalid(f"missing sealed input: {name}")
    if component_id != values["component_id"]:
        _invalid("component_id does not match inputs.component_id")

    vr = values["verification_report"]
    criteria = _get(vr, "criteria")
    if not isinstance(criteria, (list, tuple)) or not criteria:
        _invalid("verification_report has no criteria")
    results = [_get(entry, "result") for entry in criteria]
    if any(r not in ("pass", "fail", "skipped") for r in results):
        _invalid("verification_report criterion result is not pass, fail, or skipped")
    overall = _get(vr, "overall")
    if overall not in ("pass", "fail"):
        _invalid("verification_report overall is not pass or fail")

    cid = values["component_id"]
    if not _is_str(cid) or not _COMPONENT_ID_RE.fullmatch(cid):
        _invalid("invalid component_id")

    owners = values["owners"]
    if not isinstance(owners, (list, tuple)) or not owners:
        _invalid("owners must be a non-empty list")
    for owner in owners:
        if not _is_str(owner) or not _OWNER_RE.fullmatch(owner):
            _invalid("invalid owners entry")

    source_path = values["source_path"]
    if not _is_str(source_path) or not _SOURCE_PATH_RE.fullmatch(source_path):
        _invalid("invalid source_path")
    if source_path.split("/")[0] == "gen":
        _invalid("source_path must not be under gen/")

    source_hash = values["source_hash"]
    if not _is_str(source_hash) or not _SOURCE_HASH_RE.fullmatch(source_hash):
        _invalid("invalid source_hash")

    verifier_version = values["verifier_version"]
    if not _is_str(verifier_version) or not _VERIFIER_VERSION_RE.fullmatch(
        verifier_version
    ):
        _invalid("invalid verifier_version")

    total = len(results)
    passed = sum(1 for r in results if r == "pass")
    if overall == "pass" and passed != total:
        _invalid("overall pass requires every criterion to pass")

    manifest = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": cid,
        "owners": list(owners),
        "source_path": source_path,
        "source_hash": source_hash,
        "verifier_version": verifier_version,
        "characterization": {
            "overall": overall,
            "criteria_passed": passed,
            "criteria_total": total,
        },
        "written_at": _now(),
    }
    return source_path, to_json(manifest)


def write_sealed_provenance(component_id, inputs, repo_root):
    source_path, manifest = _build_sealed_manifest(component_id, inputs)
    directory = Path(repo_root) / source_path
    directory.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2) + "\n"
    (directory / ".sealed-provenance.json").write_text(text, encoding="utf-8")


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

    rest = argv[2:]
    repo_root = "."
    positionals = []
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--repo-root="):
            repo_root = token[len("--repo-root="):]
        elif token == "--repo-root":
            if i + 1 >= len(rest):
                return _usage_error("--repo-root requires a value")
            i += 1
            repo_root = rest[i]
        elif token.startswith("--"):
            return _usage_error(f"unrecognized argument: {token}")
        else:
            positionals.append(token)
        i += 1

    if len(positionals) != 1:
        return _usage_error("expected exactly one <component-id>")

    try:
        inputs = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        return _usage_error(f"malformed JSON on stdin: {exc}")

    try:
        write_provenance(positionals[0], inputs, Path(repo_root))
    except MissingInputError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
