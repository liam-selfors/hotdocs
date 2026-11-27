"""Provenance writer: assembles and writes `.provenance.json` manifests and
sealed `.sealed-provenance.json` manifests from other components' results.

This module collects, never invents: every field comes from the inputs it is
handed, except `pipeline_version` (a module constant), `generated_at` /
`written_at` (this module's own write time) and `verification_run_id`
(built deterministically from the inputs).
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

_SEALED_FIELDS = (
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
    """A required upstream result was absent; no manifest is written."""


class InvalidSealedInputError(Exception):
    """The sealed inputs would not yield a valid sealed provenance manifest."""


@dataclasses.dataclass
class ProvenanceInputs:
    component_id: str
    generation_result: object
    verification_report: object
    license_scan_result: object
    secret_scan_result: object
    provenance_hit: bool
    attempts: int
    gate_versions: dict
    attempt_history: list = None
    spec_bundle_parts: dict = None


@dataclasses.dataclass
class SealedProvenanceInputs:
    component_id: str
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str
    verification_report: object


def _get(obj, name):
    """Dual dict-or-attribute access; an absent field reads as None."""
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def to_json(value):
    """Convert `value` to a value `json.dumps` accepts (json-values.md)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
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
        return value.decode("utf-8", errors="replace")
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


def write_provenance(component_id, inputs, repo_root):
    values = {name: _get(inputs, name) for name in _REQUIRED_INPUTS}
    for name in _REQUIRED_INPUTS:
        if values[name] is None:
            raise MissingInputError(f"missing required input: {name}")

    generation_result = values["generation_result"]
    verification_report = _get(inputs, "verification_report")
    if verification_report is None and _get(generation_result, "files"):
        raise MissingInputError(
            "missing required input: verification_report "
            "(generation_result.files is non-empty)"
        )

    gate_versions = values["gate_versions"]
    attempts = values["attempts"]
    slug = str(values["component_id"]).removeprefix("comp-")

    mode = _get(generation_result, "mode")
    generation = {
        "mode": "single" if mode is None else mode,
        "generator_version": _get(gate_versions, "generator"),
        "transcript_sha256": _get(generation_result, "transcript_sha256"),
        "turns": _get(generation_result, "turns"),
        "tool_calls": _get(generation_result, "tool_calls"),
        "isolation": _get(generation_result, "isolation"),
    }

    history = _get(inputs, "attempt_history")
    attempt_history = [
        {key: _get(entry, key) for key in _ATTEMPT_KEYS}
        for entry in (history if history is not None else [])
    ]

    assets = _get(verification_report, "assets")
    drivers = _get(verification_report, "drivers")

    manifest = {
        "spec_bundle_hash": _get(generation_result, "spec_bundle_hash"),
        "spec_bundle_parts": _get(inputs, "spec_bundle_parts"),
        "model_pin": _get(generation_result, "model"),
        "prompt_version": _get(generation_result, "prompt_version"),
        "retry_feedback": _get(generation_result, "retry_feedback"),
        "generation": generation,
        "attempts": attempts,
        "attempt_history": attempt_history,
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": gate_versions,
        "provenance_hit": values["provenance_hit"],
        "generated_at": _now(),
        "verification_run_id": f"{slug}-attempt-{to_json(attempts)}",
        "verification_report": verification_report,
        "license_scan": values["license_scan_result"],
        "secret_scan": values["secret_scan_result"],
        "assets": assets if assets is not None else [],
        "drivers": drivers if drivers is not None else [],
    }

    data = (json.dumps(to_json(manifest), indent=2) + "\n").encode("utf-8")
    path_slug = str(component_id).removeprefix("comp-")
    root = Path(repo_root)
    for base in ("gen", "verification"):
        directory = root / base / path_slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".provenance.json").write_bytes(data)


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def write_sealed_provenance(component_id, inputs, repo_root):
    fields = {name: _get(inputs, name) for name in _SEALED_FIELDS}
    for name in _SEALED_FIELDS:
        if fields[name] is None:
            raise InvalidSealedInputError(f"missing input: {name}")
    if component_id != fields["component_id"]:
        raise InvalidSealedInputError(
            "component_id does not match inputs.component_id"
        )

    report = fields["verification_report"]
    criteria = _get(report, "criteria")
    if not criteria:
        raise InvalidSealedInputError("verification_report has no criteria")
    results = [_get(entry, "result") for entry in criteria]
    for result in results:
        if result not in ("pass", "fail", "skipped"):
            raise InvalidSealedInputError(f"invalid criterion result: {result!r}")
    overall = _get(report, "overall")
    if overall not in ("pass", "fail"):
        raise InvalidSealedInputError(f"invalid overall verdict: {overall!r}")
    passed = results.count("pass")
    total = len(results)
    if overall == "pass" and passed != total:
        raise InvalidSealedInputError(
            "overall pass requires every criterion to pass"
        )

    component = to_json(fields["component_id"])
    owners = to_json(fields["owners"])
    source_path = to_json(fields["source_path"])
    source_hash = to_json(fields["source_hash"])
    verifier_version = to_json(fields["verifier_version"])

    if not _matches(_COMPONENT_ID_RE, component):
        raise InvalidSealedInputError("invalid component_id")
    if not (
        isinstance(owners, list)
        and owners
        and all(_matches(_OWNER_RE, owner) for owner in owners)
    ):
        raise InvalidSealedInputError("invalid owners")
    if not _matches(_SOURCE_PATH_RE, source_path) or source_path.split("/")[0] == "gen":
        raise InvalidSealedInputError("invalid source_path")
    if not _matches(_SOURCE_HASH_RE, source_hash):
        raise InvalidSealedInputError("invalid source_hash")
    if not _matches(_VERIFIER_VERSION_RE, verifier_version):
        raise InvalidSealedInputError("invalid verifier_version")

    manifest = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": component,
        "owners": owners,
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

    directory = Path(repo_root) / source_path
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".sealed-provenance.json").write_bytes(
        (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
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

    rest = argv[2:]
    positionals = []
    repo_root = "."
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--repo-root="):
            repo_root = token.split("=", 1)[1]
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
    except ValueError:
        return _usage_error("malformed JSON on stdin")

    try:
        write_provenance(positionals[0], inputs, Path(repo_root))
    except MissingInputError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
