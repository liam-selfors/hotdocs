"""Provenance writer: assembles and writes `.provenance.json` and the
sealed counterpart `.sealed-provenance.json` from already-produced
upstream results. Collects, never invents."""

import collections.abc
import dataclasses
import datetime
import enum
import json
import math
import pathlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PIPELINE_VERSION = "v1"

USAGE = "usage: hotdocs provenance write <component-id> [--repo-root=<dir>]"


class MissingInputError(Exception):
    """A required upstream result was absent."""


class InvalidSealedInputError(Exception):
    """Sealed provenance inputs would not yield a valid manifest."""


@dataclass
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


@dataclass
class SealedProvenanceInputs:
    component_id: object = None
    owners: object = None
    source_path: object = None
    source_hash: object = None
    verifier_version: object = None
    verification_report: object = None


def _get(obj, name):
    if isinstance(obj, collections.abc.Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, collections.abc.Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(item) for item in value]
        return sorted(items, key=lambda i: json.dumps(i, sort_keys=True))
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


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


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


def build_manifest(inputs):
    values = {name: _get(inputs, name) for name in _REQUIRED}
    for name in _REQUIRED:
        if values[name] is None:
            raise MissingInputError(f"missing required input: {name}")
    gr = values["generation_result"]
    report = _get(inputs, "verification_report")
    if report is None and _get(gr, "files"):
        raise MissingInputError(
            "missing required input: verification_report "
            "(generation_result.files is non-empty)"
        )
    gate_versions = values["gate_versions"]
    mode = _get(gr, "mode")
    generation = {
        "mode": "single" if mode is None else mode,
        "generator_version": _get(gate_versions, "generator"),
        "transcript_sha256": _get(gr, "transcript_sha256"),
        "turns": _get(gr, "turns"),
        "tool_calls": _get(gr, "tool_calls"),
        "isolation": _get(gr, "isolation"),
    }
    history = _get(inputs, "attempt_history") or []
    attempt_history = [
        {key: _get(entry, key) for key in _ATTEMPT_KEYS} for entry in history
    ]
    assets = None if report is None else _get(report, "assets")
    attempts = values["attempts"]
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
        "provenance_hit": values["provenance_hit"],
        "generated_at": _now(),
        "verification_run_id": (
            f"{_slug(values['component_id'])}-attempt-{attempts}"
        ),
        "verification_report": report,
        "license_scan": values["license_scan_result"],
        "secret_scan": values["secret_scan_result"],
        "assets": [] if assets is None else assets,
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


_COMPONENT_ID_RE = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SOURCE_PATH_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
)
_SOURCE_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VERIFIER_RE = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")

_SEALED_FIELDS = (
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "verification_report",
)


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def write_sealed_provenance(component_id, inputs, repo_root):
    values = {name: _get(inputs, name) for name in _SEALED_FIELDS}
    for name in _SEALED_FIELDS:
        if values[name] is None:
            raise InvalidSealedInputError(f"missing input: {name}")
    if component_id != values["component_id"]:
        raise InvalidSealedInputError(
            "component_id differs from inputs.component_id"
        )
    report = values["verification_report"]
    overall = _get(report, "overall")
    if overall not in ("pass", "fail"):
        raise InvalidSealedInputError("verification_report overall invalid")
    criteria = _get(report, "criteria")
    if not criteria:
        raise InvalidSealedInputError("verification_report has no criteria")
    passed = 0
    for entry in criteria:
        result = _get(entry, "result")
        if result not in ("pass", "fail", "skipped"):
            raise InvalidSealedInputError(f"invalid criterion result: {result!r}")
        if result == "pass":
            passed += 1
    total = len(criteria)
    if overall == "pass" and passed != total:
        raise InvalidSealedInputError("overall pass but not every criterion passed")

    manifest = to_json(
        {
            "kind": "sealed-provenance",
            "version": 1,
            "component_id": values["component_id"],
            "owners": values["owners"],
            "source_path": values["source_path"],
            "source_hash": values["source_hash"],
            "verifier_version": values["verifier_version"],
            "characterization": {
                "overall": overall,
                "criteria_passed": passed,
                "criteria_total": total,
            },
            "written_at": _now(),
        }
    )

    if not _matches(_COMPONENT_ID_RE, manifest["component_id"]):
        raise InvalidSealedInputError("invalid component_id")
    owners = manifest["owners"]
    if not isinstance(owners, list) or not owners:
        raise InvalidSealedInputError("owners must be a non-empty list")
    for owner in owners:
        if not _matches(_OWNER_RE, owner):
            raise InvalidSealedInputError(f"invalid owner: {owner!r}")
    source_path = manifest["source_path"]
    if not _matches(_SOURCE_PATH_RE, source_path) or source_path.split("/")[0] == "gen":
        raise InvalidSealedInputError("invalid source_path")
    if not _matches(_SOURCE_HASH_RE, manifest["source_hash"]):
        raise InvalidSealedInputError("invalid source_hash")
    if not _matches(_VERIFIER_RE, manifest["verifier_version"]):
        raise InvalidSealedInputError("invalid verifier_version")

    text = json.dumps(manifest, indent=2) + "\n"
    directory = Path(repo_root) / source_path
    directory.mkdir(parents=True, exist_ok=True)
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
    except ValueError as exc:
        return _usage_error(f"malformed JSON on stdin: {exc}")
    try:
        write_provenance(positionals[0], inputs, Path(repo_root))
    except MissingInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
