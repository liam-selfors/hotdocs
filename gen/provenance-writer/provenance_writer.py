"""Provenance writer: assembles and writes `.provenance.json` and
`.sealed-provenance.json` from other components' already-produced results."""

import dataclasses
import enum
import json
import math
import pathlib
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
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
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def to_json(value):
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
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(v) for v in value]
        return sorted(items, key=lambda i: json.dumps(i, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return to_json(value.to_dict())
    if dataclasses.is_dataclass(value):
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
    return component_id.removeprefix("comp-")


def build_manifest(inputs):
    component_id = _get(inputs, "component_id")
    gr = _get(inputs, "generation_result")
    vr = _get(inputs, "verification_report")
    lsr = _get(inputs, "license_scan_result")
    ssr = _get(inputs, "secret_scan_result")
    hit = _get(inputs, "provenance_hit")
    attempts = _get(inputs, "attempts")
    history = _get(inputs, "attempt_history")
    gate_versions = _get(inputs, "gate_versions")

    required = {
        "component_id": component_id,
        "generation_result": gr,
        "license_scan_result": lsr,
        "secret_scan_result": ssr,
        "provenance_hit": hit,
        "attempts": attempts,
        "gate_versions": gate_versions,
    }
    for name, value in required.items():
        if value is None:
            raise MissingInputError(f"missing required input: {name}")
    if vr is None and _get(gr, "files"):
        raise MissingInputError(
            "missing required input: verification_report "
            "(generation_result.files is non-empty)"
        )

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
        {k: _get(entry, k) for k in _ATTEMPT_KEYS} for entry in (history or [])
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
        "provenance_hit": hit,
        "generated_at": _now(),
        "verification_run_id": f"{_slug(component_id)}-attempt-{attempts}",
        "verification_report": vr,
        "license_scan": lsr,
        "secret_scan": ssr,
        "assets": [] if assets is None else assets,
    }
    return to_json(manifest)


def write_provenance(component_id, inputs, repo_root):
    manifest = build_manifest(inputs)
    text = json.dumps(manifest, indent=2) + "\n"
    slug = _slug(component_id)
    root = Path(repo_root)
    for top in ("gen", "verification"):
        directory = root / top / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".provenance.json").write_text(text, encoding="utf-8")


_COMPONENT_ID_RE = re.compile(r"comp-[a-z0-9]+(-[a-z0-9]+)*")
_OWNER_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SOURCE_PATH_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
)
_SOURCE_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
_VERIFIER_RE = re.compile(r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+")


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def write_sealed_provenance(component_id, inputs, repo_root):
    names = (
        "component_id",
        "owners",
        "source_path",
        "source_hash",
        "verifier_version",
        "verification_report",
    )
    values = {name: _get(inputs, name) for name in names}
    for name, value in values.items():
        if value is None:
            raise InvalidSealedInputError(f"missing input: {name}")
    if component_id != values["component_id"]:
        raise InvalidSealedInputError("component_id does not match inputs")

    if not _matches(_COMPONENT_ID_RE, values["component_id"]):
        raise InvalidSealedInputError("invalid component_id")
    owners = values["owners"]
    if not isinstance(owners, (list, tuple)) or not owners:
        raise InvalidSealedInputError("owners must be a non-empty list")
    for owner in owners:
        if not _matches(_OWNER_RE, owner):
            raise InvalidSealedInputError("invalid owners entry")
    source_path = values["source_path"]
    if not _matches(_SOURCE_PATH_RE, source_path) or source_path.split("/")[0] == "gen":
        raise InvalidSealedInputError("invalid source_path")
    if not _matches(_SOURCE_HASH_RE, values["source_hash"]):
        raise InvalidSealedInputError("invalid source_hash")
    if not _matches(_VERIFIER_RE, values["verifier_version"]):
        raise InvalidSealedInputError("invalid verifier_version")

    report = values["verification_report"]
    overall = _get(report, "overall")
    criteria = _get(report, "criteria")
    if not criteria:
        raise InvalidSealedInputError("verification_report has no criteria")
    if overall not in ("pass", "fail"):
        raise InvalidSealedInputError("invalid verification_report overall")
    total = 0
    passed = 0
    for entry in criteria:
        result = _get(entry, "result")
        if result not in ("pass", "fail", "skipped"):
            raise InvalidSealedInputError("invalid criterion result")
        total += 1
        if result == "pass":
            passed += 1
    if overall == "pass" and passed != total:
        raise InvalidSealedInputError("overall pass with non-passing criteria")

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
        "written_at": _now(),
    }
    text = json.dumps(to_json(manifest), indent=2) + "\n"
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
    if not positionals:
        return _usage_error("missing <component-id>")
    if len(positionals) > 1:
        return _usage_error(f"unexpected argument: {positionals[1]}")
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
